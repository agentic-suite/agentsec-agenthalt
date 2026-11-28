"""2.CR (#434): one regression test per review finding."""

from __future__ import annotations

import fcntl
import json
import os
import pwd
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pytest

import agenthalt.supervisor as sup
from agenthalt.journal import Journal
from agenthalt.observe import ObserveError, SystemObserver, parse_ps, parse_stat
from agenthalt.store import Store
from agenthalt.subtree import Graph, Resolver, check_lineage, lineage_target
from agenthalt.supervisor import EnrollmentError, SpawnRefusedError, resolve_user
from tests.lineage_helpers import FakeObserver, adapters, edge, make_registry, proc, root
from tests.test_supervisor import graph, halt, script, supervisor

PY = sys.executable


def seeded(home: Path, *edges: dict):  # type: ignore[type-arg,no-untyped-def]
    reg = make_registry(home)
    cred = adapters(reg)["process"]
    reg.append_edges(cred, list(edges) or [root("run_a")])
    return reg, cred


# 1 ------------------------------------------------------------------ malformed input


@pytest.mark.parametrize(
    "change",
    [{"mac": "é"}, {"data": "\ud800"}, {"data": []}, {"seq": []}, {"kind": 3}, {"adapter": None}],
)
def test_a_malformed_record_is_a_finding_not_a_crash(tmp_path: Path, change: dict) -> None:  # type: ignore[type-arg]
    reg, _ = seeded(tmp_path)
    segment = tmp_path / "lineage" / "seg-000001.jsonl"
    record = {**json.loads(segment.read_text()), **change, "seq": change.get("seq", 2)}
    with segment.open("a") as handle:
        handle.write(json.dumps(record) + "\n")
    read = reg.read()
    assert read.findings and [e.child_run for e in read.edges] == ["run_a"]


@pytest.mark.parametrize(
    "junk", [b"\xff\xfe\n", b'{"action": "lineage", "payload": []}\n', b"[1]\n"]
)
def test_junk_in_the_journal_is_a_finding_not_a_crash(tmp_path: Path, junk: bytes) -> None:
    reg, _ = seeded(tmp_path)
    with (tmp_path / "journal" / "seg-000001.jsonl").open("ab") as handle:
        handle.write(junk)
    assert reg.check_tamper(actor="t")


# 2 ------------------------------------------------------------------ attach laundering


def test_attach_inside_a_run_stays_inside_it(tmp_path: Path) -> None:
    home = tmp_path / "h"
    reg = make_registry(home)
    me = SystemObserver().snapshot()[os.getpid()]
    reg.append_edges(
        adapters(reg)["process"], [root("run_outer", "outer", pid=me.pid, start=me.start)]
    )
    child = subprocess.Popen([PY, "-c", "import time; time.sleep(20)"])
    try:
        time.sleep(0.5)
        halt(home, "agent:outer")
        result = supervisor(home).attach(child.pid, name="fresh")
        assert "run_outer" in graph(home).ancestors(result.run_id)
        store = Store(home)
        from agenthalt.choke import RuntimeChoke

        assert not check_lineage(RuntimeChoke(store), graph(home), result.run_id).allow
    finally:
        child.kill()
        child.wait()


# 3 ------------------------------------------------------------------ deleted store


def test_a_deleted_store_is_not_recreated_empty(tmp_path: Path) -> None:
    home, marker = tmp_path / "h", tmp_path / "ran"
    halt(home, "all")
    (home / "store" / "state.json").unlink()
    with pytest.raises(SpawnRefusedError):
        supervisor(home).run(script(tmp_path, f"open({str(marker)!r}, 'w')\n"))
    assert not marker.exists()


def test_a_store_edited_to_drop_halts_is_not_trusted(tmp_path: Path) -> None:
    home = tmp_path / "h"
    halt(home, "all")
    path = home / "store" / "state.json"
    path.write_text(json.dumps({**json.loads(path.read_text()), "halts": []}))
    with pytest.raises(SpawnRefusedError, match="store"):
        supervisor(home).run([PY, "-c", "pass"])


# 4 ------------------------------------------------------------------ time zones


def test_process_start_does_not_depend_on_the_time_zone(monkeypatch: pytest.MonkeyPatch) -> None:
    line = "10 1 10 501 S Fri Nov 27 08:57:21 2026"
    seen = []
    for zone in ("UTC0", "JST-9"):
        monkeypatch.setenv("TZ", zone)
        time.tzset()
        seen.append(parse_ps(line, sid_of=lambda _: 1)[10].start)
    monkeypatch.undo()
    time.tzset()
    assert seen[0] == seen[1]
    first = SystemObserver().snapshot()[os.getpid()].start
    monkeypatch.setenv("TZ", "JST-9")
    time.tzset()
    try:
        assert SystemObserver().snapshot()[os.getpid()].start == first
    finally:
        monkeypatch.undo()
        time.tzset()


def test_linux_start_includes_the_boot_time() -> None:
    line = "12 (x) S 1 12 12 " + "0 " * 15 + "77 0"
    assert parse_stat(line, 0, boot=1).start != parse_stat(line, 0, boot=2).start  # type: ignore[union-attr]


# 5 ------------------------------------------------------------------ damaged lineage


def test_damaged_lineage_refuses_spawns_while_a_halt_is_armed(tmp_path: Path) -> None:
    home = tmp_path / "h"
    seeded(home)
    (home / "lineage" / "seg-000001.jsonl").unlink()
    halt(home, "run:run_a")
    with pytest.raises(SpawnRefusedError, match="lineage_gap"):
        supervisor(home).run([PY, "-c", "pass"])


def test_damaged_lineage_alone_does_not_stop_enrollment(tmp_path: Path) -> None:
    home = tmp_path / "h"
    seeded(home)
    (home / "lineage" / "seg-000001.jsonl").unlink()
    assert supervisor(home).run([PY, "-c", "pass"]).exit_code == 0


# 6 / 7 -------------------------------------------------------------- false positives


def test_a_dead_run_does_not_adopt_a_reused_process_group(tmp_path: Path) -> None:
    reg, _ = seeded(
        tmp_path, root("run_a", pid=5000, start="10", pgid=5000, uid=501, containment="pgroup")
    )
    seen = FakeObserver()
    seen.add(proc(5000, 1, start=999), proc(5001, 5000, pgid=5000))
    assert Resolver(reg, seen).resolve("run", "run_a").members == ("run_a",)


@pytest.mark.parametrize(("uid", "start"), [(999, 200), (501, 1)])
def test_a_marker_on_an_unrelated_process_is_ignored(tmp_path: Path, uid: int, start: int) -> None:
    reg, _ = seeded(tmp_path, root("run_a", pid=10, start="100", uid=501, marker="run_a"))
    seen = FakeObserver(markers={77: "run_a"})
    seen.add(proc(77, 1, uid=uid, start=start))
    assert Resolver(reg, seen).resolve("run", "run_a").members == ("run_a",)


def test_macos_marker_ignores_arguments(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        argv = "40 sh -c x AGENTHALT_RUN_ID=run_argv"
        out = argv + (" HOME=/x" if "-axEww" in args else "") + "\n"
        return subprocess.CompletedProcess(args, 0, out, "")

    monkeypatch.setattr(subprocess, "run", fake)
    assert SystemObserver(platform="darwin").run_markers() == {}


# 8 ------------------------------------------------------------------ parentage


def test_a_real_parent_outranks_a_supervisor_placeholder(tmp_path: Path) -> None:
    reg, _ = seeded(
        tmp_path,
        root("run_child", "c", pid=11, start="110", containment="observed"),
        root("run_parent", "p", pid=10, start="100", containment="observed"),
    )
    seen = FakeObserver()
    seen.add(proc(10, 1), proc(11, 10))
    resolver = Resolver(reg, seen)
    for _ in range(3):
        resolver.resolve("run", "run_parent")
    assert "run_parent" in Graph(reg.read().edges).ancestors("run_child")
    assert len(reg.read().edges) == 3, "recorded once"


# 9 ------------------------------------------------------------------ sessions


def test_session_halts_are_inherited(tmp_path: Path) -> None:
    reg, _ = seeded(tmp_path, root("run_a", session="s1"), edge("run_a", "run_b"))
    g = Graph(reg.read().edges)
    assert lineage_target(g, "run_b").session == "s1"
    from agenthalt.choke import RuntimeChoke

    halt(tmp_path, "session:s1")
    assert not check_lineage(RuntimeChoke(Store(tmp_path)), g, "run_b").allow


# 10 ----------------------------------------------------------------- lost gaps


def test_blindness_is_reported_and_journaled(tmp_path: Path) -> None:
    class GoesBlind(SystemObserver):
        calls = 0

        def snapshot(self, timeout_s: float = 5.0):  # type: ignore[no-untyped-def]
            self.calls += 1
            if self.calls > 1:
                raise ObserveError("gone")
            return super().snapshot(timeout_s)

    home = tmp_path / "h"
    result = supervisor(home, observer=GoesBlind()).run(script(tmp_path, "time.sleep(0.3)\n"))
    assert any("degraded" in why for why in result.gaps)
    assert [e for e in Journal(home).entries() if e["payload"].get("finding") == "lineage_gap"]


def test_a_transient_write_failure_is_retried(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "h"
    runner = supervisor(home)
    real = runner.registry.append_edges
    failed: list[bool] = []

    def flaky(credential, edges):
        if credential.name == "process-observer" and not failed:
            failed.append(True)
            raise OSError("transient")
        return real(credential, edges)

    monkeypatch.setattr(runner.registry, "append_edges", flaky)
    body = "subprocess.run([sys.executable, '-c', 'import time; time.sleep(1)'])\n"
    result = runner.run(script(tmp_path, body))
    assert failed and len(graph(home).walk([result.run_id])[0]) == 2


def test_a_broken_journal_chain_is_a_lineage_finding(tmp_path: Path) -> None:
    reg, _ = seeded(tmp_path)
    journal = tmp_path / "journal" / "seg-000001.jsonl"
    Journal(tmp_path).append("finding", actor="t", payload={"finding": "x"})
    journal.write_text(journal.read_text().replace('"actor":"t"', '"actor":"u"'))
    assert "journal_unreadable" in {f.problem for f in reg.read().findings}


# 11 ----------------------------------------------------------------- sudo


def test_resolve_user_checks_every_ancestor_and_group_write(tmp_path: Path) -> None:
    inner = tmp_path / "a" / "b"
    inner.mkdir(parents=True)
    (tmp_path / "a").chmod(0o770)
    gid = (tmp_path / "a").stat().st_gid
    entry = pwd.struct_passwd(("bot", "x", 888, gid, "", "/home/bot", "/bin/sh"))
    with pytest.raises(EnrollmentError, match="state directory"):
        resolve_user(
            "bot",
            inner / "h",
            euid=0,
            invoking_uid=1,
            lookup=lambda _: entry,
            groups=lambda *_: [gid],
        )


@pytest.mark.parametrize("action", ["run", "attach"])
def test_under_sudo_state_is_written_as_the_invoking_user(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, action: str
) -> None:
    used: list[tuple[int, int]] = []
    real = sup._effective

    def spy(uid: int, gid: int):  # type: ignore[no-untyped-def]
        used.append((uid, gid))
        return real(os.geteuid(), os.getegid())

    monkeypatch.setattr(sup, "_effective", spy)
    monkeypatch.setattr(sup, "invoking_ids", lambda: (4242, 4243))
    runner = supervisor(tmp_path / "h")
    if action == "run":
        runner.run([PY, "-c", "pass"])
    else:
        monkeypatch.setattr(sup, "invoking_ids", lambda: (os.getuid(), 4243))
        runner.attach(os.getpid())
    assert any(gid == 4243 for _, gid in used)


# 12 ----------------------------------------------------------------- locks and deadlines


def test_a_held_lock_cannot_hang_the_resolver(tmp_path: Path) -> None:
    reg, _ = seeded(tmp_path)
    fd = os.open(tmp_path / "lineage" / ".lock", os.O_RDWR)
    fcntl.flock(fd, fcntl.LOCK_EX)
    try:
        started = time.monotonic()
        tree = Resolver(reg, FakeObserver()).resolve("run", "run_a", deadline_ms=200)
        assert time.monotonic() - started < 3 and not tree.complete
    finally:
        os.close(fd)


# resolver paths ----------------------------------------------------------------


@pytest.mark.parametrize("containment", ["pgroup", "cgroup"])
def test_the_resolver_reports_a_member_that_left(tmp_path: Path, containment: str) -> None:
    meta: dict[str, Any] = {"pid": 10, "start": "100", "pgid": 10, "uid": 501}
    meta["containment"] = containment
    reg, _ = seeded(tmp_path, root("run_a", cgroup="/run_a", **meta))
    seen = FakeObserver(cgroups={10: "/run_a", 11: "/elsewhere"})
    seen.add(proc(10, 1, start=100), proc(11, 10, pgid=11))
    tree = Resolver(reg, seen).resolve("run", "run_a")
    assert tree.gaps and not tree.lineage_verified


def test_a_resolver_that_cannot_record_is_incomplete_not_a_crash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    reg, _ = seeded(tmp_path, root("run_a", pid=10, start="100"))
    seen = FakeObserver()
    seen.add(proc(10, 1, start=100), proc(11, 10))

    def fail(*args: object) -> None:
        raise OSError("read-only")

    monkeypatch.setattr(reg, "append_edges", fail)
    tree = Resolver(reg, seen).resolve("run", "run_a")
    assert not tree.complete and "read-only" in (tree.reason or "")
    assert "proc_11_110" not in tree.members or not tree.lineage_verified


def test_the_resolver_stops_at_its_deadline_between_runs(tmp_path: Path) -> None:
    reg, _ = seeded(tmp_path, root("run_a", pid=10, start="100"))
    ticks = iter([0.0] + [0.0] * 4 + [99.0] * 50)
    tree = Resolver(reg, FakeObserver(), clock=lambda: next(ticks)).resolve("run", "run_a")
    assert not tree.complete
