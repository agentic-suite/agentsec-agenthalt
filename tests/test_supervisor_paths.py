"""2.7 (#569): failure paths and privilege handling, with the system calls faked where needed."""

from __future__ import annotations

import os
import signal
import sys
from pathlib import Path

import pytest

import agenthalt.supervisor as sup
from agenthalt.journal import Journal
from agenthalt.observe import ObserveError, SystemObserver
from agenthalt.supervisor import EnrollmentError, SpawnRefusedError, Supervisor, UserSpec
from tests.lineage_helpers import FakeObserver, make_registry
from tests.test_supervisor import fake_cgroup, graph, script, supervisor

PY = sys.executable


def test_invoking_ids_prefers_the_sudo_user_only_under_root() -> None:
    env = {"SUDO_UID": "42", "SUDO_GID": "43"}
    assert sup.invoking_ids(env, euid=0) == (42, 43)
    own = (os.getuid(), os.getgid())
    assert sup.invoking_ids(env, euid=501) == own
    assert sup.invoking_ids({"SUDO_UID": "x"}, euid=0) == own


def test_effective_ids_are_changed_and_restored(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, int]] = []
    monkeypatch.setattr(os, "geteuid", lambda: 0)
    monkeypatch.setattr(os, "getegid", lambda: 0)
    monkeypatch.setattr(os, "seteuid", lambda v: calls.append(("uid", v)))
    monkeypatch.setattr(os, "setegid", lambda v: calls.append(("gid", v)))
    with pytest.raises(RuntimeError), sup._effective(7, 8):
        raise RuntimeError
    assert calls == [("uid", 0), ("gid", 8), ("uid", 7), ("uid", 0), ("gid", 0), ("uid", 0)]


def test_run_as_another_user_records_it(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The forked child inherits the faked calls; the real drop runs in the Linux root test."""
    spec = UserSpec("agentbot", os.getuid(), os.getgid(), (), "/home/agentbot")
    monkeypatch.setattr(sup, "resolve_user", lambda name, home: spec)
    for name in ("setgroups", "setgid", "setuid", "seteuid", "setegid"):
        monkeypatch.setattr(os, name, lambda *_: None)
    body = "sys.exit(0 if os.environ['HOME'] == '/home/agentbot' else 3)\n"
    base, own = fake_cgroup(tmp_path)
    home = tmp_path / "h"
    runner = supervisor(home, containment="cgroup", cgroup_root=base)
    real = sup.prepare_cgroup
    monkeypatch.setattr(
        sup, "prepare_cgroup", lambda run_id, root: real(run_id, root=root, self_cgroup=own)
    )
    result = runner.run(script(tmp_path, body), user="agentbot")
    assert result.exit_code == 0
    meta = graph(home).meta[result.run_id]
    assert meta["user"] == "agentbot" and meta["cgroup"].endswith(result.run_id)
    written = next((base / "user.slice").glob("agenthalt-*/cgroup.procs"))
    assert written.read_text().isdigit()


def test_an_empty_command_and_a_bad_parent_hint_are_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(EnrollmentError, match="no command"):
        supervisor(tmp_path / "h").run([])
    monkeypatch.setenv("AGENTHALT_RUN_ID", "../../etc")
    with pytest.raises(SpawnRefusedError, match="not a run id"):
        supervisor(tmp_path / "h").run([PY, "-c", "pass"])


@pytest.mark.parametrize("seen", [FakeObserver(fail=True), FakeObserver()])
def test_if_the_process_cannot_be_observed_it_never_runs(
    tmp_path: Path, seen: FakeObserver
) -> None:
    marker = tmp_path / "ran"
    with pytest.raises(EnrollmentError):
        supervisor(tmp_path / "h", observer=seen).run(
            script(tmp_path, f"open({str(marker)!r}, 'w')\n")
        )
    assert not marker.exists()


def test_a_damaged_journal_stops_run_and_attach(tmp_path: Path) -> None:
    home, marker = tmp_path / "h", tmp_path / "ran"
    (home / "journal").mkdir(parents=True)
    (home / "journal" / "seg-000001.jsonl").write_text("garbage\n")
    with pytest.raises(EnrollmentError):
        supervisor(home).run(script(tmp_path, f"open({str(marker)!r}, 'w')\n"))
    assert not marker.exists()
    with pytest.raises(EnrollmentError, match="attach failed"):
        supervisor(home).attach(os.getpid())


def test_observation_failing_mid_run_does_not_stop_the_agent(tmp_path: Path) -> None:
    class GoesBlind(SystemObserver):
        calls = 0

        def snapshot(self, timeout_s: float = 5.0):  # type: ignore[no-untyped-def]
            self.calls += 1
            if self.calls > 1:
                raise ObserveError("gone")
            return super().snapshot(timeout_s)

    result = supervisor(tmp_path / "h", observer=GoesBlind()).run(
        script(tmp_path, "time.sleep(0.3)\n")
    )
    assert result.exit_code == 0


def test_a_stopped_agent_is_waited_for(tmp_path: Path) -> None:
    body = (
        "subprocess.Popen([sys.executable, '-c',"
        " f'import os, signal, time; time.sleep(0.6); os.kill({os.getpid()}, signal.SIGCONT)'])\n"
        "os.kill(os.getpid(), signal.SIGSTOP)\n"
        "sys.exit(4)\n"
    )
    assert supervisor(tmp_path / "h").run(script(tmp_path, body)).exit_code == 4


def test_terminal_is_handed_over_only_when_interactive(monkeypatch: pytest.MonkeyPatch) -> None:
    given: list[int] = []
    monkeypatch.setattr(os, "isatty", lambda fd: True)
    monkeypatch.setattr(os, "tcgetpgrp", lambda fd: os.getpgrp())
    monkeypatch.setattr(os, "tcsetpgrp", lambda fd, group: given.append(group))
    before = signal.getsignal(signal.SIGTTOU)
    terminal = sup._Terminal()
    terminal.give(123)
    terminal.take_back()
    assert given == [123, os.getpgrp()]
    assert signal.getsignal(signal.SIGTTOU) == before
    monkeypatch.setattr(os, "isatty", lambda fd: False)
    sup._Terminal().give(5)
    assert len(given) == 2


def test_default_containment(monkeypatch: pytest.MonkeyPatch) -> None:
    for platform, expected in (("linux", "cgroup"), ("darwin", "pgroup")):
        monkeypatch.setattr(sys, "platform", platform)
        assert sup.default_containment() == expected
    assert Supervisor("h").containment == "pgroup"


# --------------------------------------------------------------------------- registry failure paths


def test_registry_refusals(tmp_path: Path) -> None:
    from agenthalt.lineage import LineageError
    from tests.lineage_helpers import adapters, edge, root

    with pytest.raises(ValueError):
        make_registry(tmp_path, segment_max_entries=1)
    reg = make_registry(tmp_path)
    cred = adapters(reg)["process"]
    reg.append_edges(cred, [root("run_a")])
    assert reg.append_edges(cred, []) == []
    segment = tmp_path / "lineage" / "seg-000001.jsonl"
    segment.write_text(segment.read_text().replace("run_a", "run_b"))
    with pytest.raises(LineageError, match="does not verify"):
        reg.append_edges(cred, [edge("run_b", "run_c")])
    (tmp_path / "keys" / "lineage" / "process-adapter.key").write_text("nonsense")
    with pytest.raises(LineageError, match="unreadable"):
        reg.register_adapter("process-adapter", "process")
    assert "forged_record" in {f.problem for f in reg.read().findings}


def test_registry_reports_unreadable_foreign_and_unterminated_records(tmp_path: Path) -> None:
    import json

    from tests.lineage_helpers import adapters, root

    reg = make_registry(tmp_path)
    creds = adapters(reg)
    reg.append_edges(creds["process"], [root("run_a")])
    segment = tmp_path / "lineage" / "seg-000001.jsonl"
    original = segment.read_text()

    segment.write_text(original + '{"schema": "other"}')  # unterminated and not a record
    assert {f.problem for f in reg.read().findings} == {"unreadable_record"}

    # a hook adapter's key signing a record that claims to be process-observed
    from agenthalt.lineage import AdapterCredential

    impostor = AdapterCredential(creds["hook"].name, "process", creds["hook"].key)
    record = reg._record(
        impostor,
        "edge",
        {"parent_run": "run_a", "child_run": "run_h", "spawn_source": "process", "child": {}},
        2,
        json.loads(original)["chain_hash"],
    )
    segment.write_text(original + json.dumps(record) + "\n")
    read = reg.read()
    assert [e.child_run for e in read.edges] == ["run_a"]
    assert any("another source" in f.detail for f in read.findings)

    segment.unlink()
    segment.mkdir()  # cannot be read as a file
    assert "unreadable_record" in {f.problem for f in reg.read().findings}


def test_a_tamper_finding_survives_an_unwritable_journal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tests.lineage_helpers import adapters, root

    reg = make_registry(tmp_path)
    reg.append_edges(adapters(reg)["process"], [root("run_a")])
    (tmp_path / "lineage" / "seg-000001.jsonl").unlink()

    def fail(*args: object, **kwargs: object) -> None:
        raise OSError("read-only")

    monkeypatch.setattr(Journal, "append", fail)
    assert reg.check_tamper(actor="t")
