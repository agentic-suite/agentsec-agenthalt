"""One test per defect the M3 review reproduced. Fake process table: nothing real is signalled."""

from __future__ import annotations

import fcntl
import os
import signal
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

from agenthalt import journal as journal_module
from agenthalt import store as store_module
from agenthalt.containment import Containment, recorded_uid
from agenthalt.coordinator import Coordinator
from agenthalt.cutlog import CutLog
from agenthalt.egress import EgressExecutor
from agenthalt.executors import Context, ExecutorSigner, Member, Result
from agenthalt.exit_codes import ReceiptStatus
from agenthalt.observe import ObserveError, Proc
from agenthalt.process_exec import ProcessExecutor, refusal
from agenthalt.scopes import Mode, Scope
from agenthalt.store import Store
from agenthalt.supervisor import LIVENESS_GAP
from tests.lineage_helpers import FakeObserver, adapters, edge, make_registry, proc, root


class World(FakeObserver):
    def __init__(self, *procs: Proc) -> None:
        super().__init__()
        self.add(*procs)
        self.sent: list[tuple[int, int]] = []

    def kill(self, pid: int, signum: int) -> None:
        self.sent.append((pid, signum))
        if signum == signal.SIGKILL:
            self.procs.pop(pid, None)
            return
        old = self.procs[pid]
        state = "T" if signum == signal.SIGSTOP else "S"
        self.procs[pid] = Proc(pid, old.ppid, old.pgid, old.sid, old.uid, old.start, state)

    def state(self, pid: int) -> str:
        return self.procs[pid].state


class Wall:
    attestation = "self"

    def __init__(self, release: str = "confirmed") -> None:
        self.outcome = release
        self.released: list[Any] = []

    def block(self, targets: Sequence[Member], ctx: Context) -> list[Result]:
        for run in {m.run for m in targets}:
            ctx.record("sandbox", {"halt": ctx.halt_id, "run": run})
        return [Result(run, "confirmed", "cut") for run in {m.run for m in targets}]

    def release(self, record: Sequence[Any], ctx: Context) -> list[Result]:
        self.released.extend(record)
        return [Result(str(i["run"]), self.outcome, self.outcome) for i in record]


def seeded(home: Path, uid: int = 501) -> None:
    reg = make_registry(home)
    cred = adapters(reg)["process"]
    reg.append_edges(
        cred, [root("run_a", pid=10, start="100", uid=uid, containment="process_group")]
    )
    reg.append_edges(cred, [edge("run_a", "proc_11_110", pid=11, start="110", uid=uid)])


def world() -> World:
    return World(proc(10, 1), proc(11, 10))


def build(
    home: Path, table: World, *, wall: Any = None, executor: Any = None, deadline_ms: int = 2000
) -> Coordinator:
    found: dict[str, Any] = {"process": executor or ProcessExecutor(table, kill=table.kill)}
    if wall is not None:
        found["sandbox"] = wall
    containment = Containment(
        make_registry(home),
        table,
        found,
        signer=ExecutorSigner(home),
        deadline_ms=deadline_ms,
        invoking_uid=501,
    )
    store = Store(home)
    store.ensure()
    return Coordinator(store, containment)


@pytest.fixture
def home(tmp_path: Path) -> Path:
    seeded(tmp_path / "h")
    return tmp_path / "h"


def halt(c: Coordinator, mode: Mode = Mode.PAUSE, scope: str = "agent:bot") -> Any:
    return c.raise_halt(Scope.parse(scope), mode, actor="op", reason="r")


def lift(c: Coordinator, result: Any) -> Any:
    return c.lift(result.halt.halt_id, actor="op", reason="r")


def running(table: World) -> bool:
    return all(p.state != "T" for p in table.procs.values())


@pytest.mark.parametrize("mode", [Mode.PAUSE, Mode.KILL])
def test_a_deadline_already_past_still_signals_and_stays_liftable(home: Path, mode: Mode) -> None:
    table = world()
    c = build(home, table, deadline_ms=1)
    result = halt(c, mode)
    assert {s for _, s in table.sent} >= {signal.SIGSTOP}
    if mode is Mode.PAUSE:
        lift(c, result)
        assert running(table)
    else:
        assert not table.procs


def test_observation_lost_midway_still_kills_and_keeps_the_record(home: Path) -> None:
    table = world()
    real, calls = table.snapshot, []

    def snapshot(timeout_s: float = 5.0) -> dict[int, Proc]:
        calls.append(1)
        if len(calls) == 4:
            raise ObserveError("gone")
        return real(timeout_s)

    table.snapshot = snapshot  # type: ignore[method-assign]
    result = halt(build(home, table), Mode.KILL)
    assert signal.SIGKILL in {s for _, s in table.sent} and result.outcome is not None


def test_a_child_that_appears_at_the_last_look_is_frozen_too(home: Path) -> None:
    table = world()

    class Late(ProcessExecutor):
        def suspend(self, targets: Sequence[Member], ctx: Context) -> list[Result]:
            results = super().suspend(targets, ctx)
            if 12 not in table.procs:
                table.add(Proc(12, 10, 10, 10, 501, "120", "S"))
            return results

    result = halt(build(home, table, executor=Late(table, kill=table.kill)))
    assert table.state(12) == "T" and result.cut.survivors == []
    assert 12 in {m["pid"] for m in result.cut.members}


@pytest.mark.parametrize("order", [(0, 1), (1, 0)])
def test_two_overlapping_halts_leave_nothing_stuck(home: Path, order: tuple[int, int]) -> None:
    table = world()
    c = build(home, table)
    halts = [halt(c, Mode.PAUSE), halt(c, Mode.PAUSE, "run:run_a")]
    lift(c, halts[order[0]])
    assert not running(table), "still covered by the other halt"
    lift(c, halts[order[1]])
    assert running(table)


def test_a_failed_release_can_be_retried(home: Path) -> None:
    table, wall = world(), Wall(release="failed")
    c = build(home, table, wall=wall)
    result = halt(c, Mode.QUARANTINE)
    first = lift(c, result)
    assert "failed" in [r.status for r in first.released] and not first.retried
    wall.outcome = "confirmed"
    second = lift(c, result)
    assert second.retried and [r.status for r in second.released] == ["confirmed"]
    with pytest.raises(LookupError):
        lift(c, result)


def test_a_kill_with_an_unseen_survivor_keeps_the_network_cut(home: Path) -> None:
    make_registry(home).record_finding(
        "lineage_gap", {"node": "run_a", "why": LIVENESS_GAP}, actor="t", unique=("node",)
    )
    wall = Wall()
    result = halt(build(home, world(), wall=wall), Mode.KILL)
    assert wall.released == [] and result.cut.undo["sandbox"]


def test_a_kill_that_cannot_remove_its_rules_says_so_and_keeps_them(home: Path) -> None:
    result = halt(build(home, world(), wall=Wall(release="failed")), Mode.KILL)
    assert result.layers["sandbox"] == "failed" and result.outcome is ReceiptStatus.INCOMPLETE
    assert CutLog(home).read(result.halt.halt_id).pending["sandbox"]


def test_damaged_lineage_is_incomplete_and_lift_keeps_covered_processes(home: Path) -> None:
    table = world()
    c = build(home, table)
    first = halt(c, Mode.PAUSE)
    halt(c, Mode.PAUSE, "run:run_a")
    segment = next((home / "lineage").glob("seg-*.jsonl"))
    segment.write_text(segment.read_text().replace('"pid":11', '"pid":99'))
    released = lift(c, first).released
    assert "failed" in [r.status for r in released] or not running(table)
    assert not running(table)
    assert halt(c, Mode.KILL).outcome is ReceiptStatus.INCOMPLETE


def test_a_sibling_that_continues_another_is_stopped_again(home: Path) -> None:
    table = world()
    real = table.kill
    undone: list[int] = []

    def kill(pid: int, signum: int) -> None:
        real(pid, signum)
        if pid == 11 and not undone:
            undone.append(1)
            real(10, signal.SIGCONT)

    result = halt(build(home, table, executor=ProcessExecutor(table, kill=kill)))
    assert table.state(10) == "T" and result.cut.survivors == []


def test_an_abandoned_adapter_has_already_recorded_what_it_did(home: Path) -> None:
    class Hung(Wall):
        grace_s = 0.0

        def block(self, targets: Sequence[Member], ctx: Context) -> list[Result]:
            ctx.record("sandbox", {"halt": ctx.halt_id, "run": "run_a"})
            time.sleep(1.0)
            return []

    result = halt(build(home, world(), wall=Hung(), deadline_ms=100), Mode.QUARANTINE)
    assert result.cut.undo["sandbox"] and result.outcome is ReceiptStatus.INCOMPLETE


def held_lock(path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
    fcntl.flock(fd, fcntl.LOCK_EX)
    return fd


@pytest.mark.parametrize("held", ["journal", "store"])
def test_a_held_state_lock_cannot_hang_or_prevent_the_cut(
    home: Path, monkeypatch: pytest.MonkeyPatch, held: str
) -> None:
    monkeypatch.setattr(journal_module, "LOCK_TIMEOUT_S", 0.05)
    monkeypatch.setattr(store_module, "LOCK_TIMEOUT_S", 0.05)
    table = world()
    c = build(home, table)
    c.store.ensure()
    fd = held_lock(home / held / ".lock")
    try:
        result = halt(c)
        assert result.outcome is ReceiptStatus.FAILED and not running(table)
        assert result.layers["runtime_choke"] == "not established"
    finally:
        os.close(fd)
    assert lift(c, result).retried and running(table)


def test_sudo_never_signals_a_user_the_run_was_not_launched_as(tmp_path: Path) -> None:
    other = proc(20, 1, uid=88)
    assert "another user" in str(refusal(other, {}, invoking_uid=501, me=50))
    assert refusal(other, {}, invoking_uid=501, me=50, also=88) is None
    assert refusal(other, {}, invoking_uid=0, me=50) is None
    record = tmp_path / "keys" / "users" / "run_a"
    record.parent.mkdir(parents=True)
    record.write_text("run_a 88")
    assert recorded_uid(tmp_path, "run_a", owner=os.getuid()) == 88
    assert recorded_uid(tmp_path, "run_a", owner=os.getuid() + 1) is None, "not written by root"
    assert recorded_uid(tmp_path, "run_b", owner=os.getuid()) is None
    record.write_text("run_z 88")
    assert recorded_uid(tmp_path, "run_a", owner=os.getuid()) is None
    assert recorded_uid(tmp_path, "../x", owner=os.getuid()) is None


def test_a_group_frozen_before_the_halt_stays_frozen_after_lift(tmp_path: Path) -> None:
    group = tmp_path / "agenthalt-run_a"
    group.mkdir()
    (group / "cgroup.procs").write_text("10\n")
    (group / "cgroup.freeze").write_text("1")
    (group / "cgroup.events").write_text("frozen 1\n")
    table, intended = World(proc(10, 1)), []
    context = Context(
        "hlt_1",
        time.monotonic() + 0.3,
        invoking_uid=501,
        record=lambda layer, item: intended.append(item),
    )
    target = Member("n10", 10, "100", "run_a", cgroup="/agenthalt-run_a")
    ProcessExecutor(table, cgroup_root=tmp_path, kill=table.kill).suspend([target], context)
    assert [i for i in intended if "freeze" in i] == []


def test_a_halting_process_in_a_nested_group_prevents_the_freeze(tmp_path: Path) -> None:
    group = tmp_path / "agenthalt-run_a"
    group.mkdir()
    table = World(proc(10, 1))
    table.cgroups[os.getpid()] = "/agenthalt-run_a/sub"
    executor = ProcessExecutor(table, cgroup_root=tmp_path, kill=table.kill)
    target = Member("n10", 10, "100", "run_a", cgroup="/agenthalt-run_a")
    executor.suspend([target], Context("hlt_1", time.monotonic() + 0.3, invoking_uid=501))
    assert not (group / "cgroup.freeze").exists()


def test_egress_release_deletes_its_own_rules_when_others_move(tmp_path: Path) -> None:
    mine, theirs = "agenthalt:hlt_1:run_a", "agenthalt:hlt_2:run_a"
    rules = [f'-A OUTPUT -m comment --comment "{mine}" -j REJECT', "-A OUTPUT -j ACCEPT"]

    def runner(command: Sequence[str]) -> tuple[int, str]:
        tool, _, op, _, *rest = command
        if tool != "iptables":
            return 0, ""
        if op == "-S":
            listing = "\n".join(rules)
            if not any(theirs in r for r in rules):  # someone inserts right after we look
                rules.insert(0, f"-A OUTPUT -m comment --comment {theirs} -j REJECT")
            return 0, listing
        assert op == "-D" and mine in rest
        rules.remove(next(r for r in rules if mine in r))
        return 0, ""

    executor = EgressExecutor(FakeObserver(), runner=runner)
    context = Context("hlt_1", time.monotonic() + 1)
    (result,) = executor.release([{"halt": "hlt_1", "run": "run_a"}], context)
    assert result.status == "confirmed" and len(rules) == 2 and theirs in rules[0]


def test_the_cut_record_survives_torn_lines_and_refuses_odd_names(tmp_path: Path) -> None:
    log = CutLog(tmp_path)
    writer = log.writer({"halt_id": "hlt_1"})
    writer.cut("process", {"pid": 1, "start": "2", "run": "r"})
    writer.close()
    with (log.dir / "hlt_1.jsonl").open("a") as handle:
        handle.write('{"op": "do\n{"op": "cut", "layer": "elsewhere", "item": {}}\n')
    assert len(log.read("hlt_1").pending["process"]) == 1
    assert not log.read("../hlt_1") and log.held(besides="hlt_2") == {(1, "2")}
    (tmp_path / "file").write_text("")
    broken = CutLog(tmp_path / "file").writer({"halt_id": "hlt_1"})
    broken.cut("process", {})
    assert broken.failed


# the fallbacks behind the fixes -----------------------------------------------


def flaky(table: World, failures: int) -> None:
    real, left = table.snapshot, [failures]
    probe_table = dict(table.procs)

    def snapshot(timeout_s: float = 5.0) -> dict[int, Proc]:
        if left[0]:
            left[0] -= 1
            raise ObserveError("busy")
        return real(timeout_s)

    def probe(pids: Sequence[int], timeout_s: float = 5.0) -> dict[int, Proc]:
        probe_table.update(table.procs)
        return {pid: probe_table[pid] for pid in pids if pid in probe_table}

    table.snapshot = snapshot  # type: ignore[method-assign]
    table.probe = probe  # type: ignore[method-assign]


@pytest.mark.parametrize("phase", ["suspend", "terminate"])
def test_with_no_full_listing_the_targets_are_still_signalled(phase: str) -> None:
    table = world()
    table.add(Proc(os.getpid(), 1, 1, 1, 501, "1", "S"))
    flaky(table, 2)
    context = Context("hlt_1", time.monotonic() + 0.3, invoking_uid=501)
    executor = ProcessExecutor(table, kill=table.kill)
    getattr(executor, phase)([Member("n10", 10, "100", "run_a")], context)
    assert [pid for pid, _ in table.sent] == [10]


@pytest.mark.parametrize("phase", ["suspend", "terminate"])
def test_with_no_way_to_look_nothing_is_signalled(phase: str) -> None:
    table = world()
    table.fail = True
    context = Context("hlt_1", time.monotonic() + 0.3, invoking_uid=501)
    executor = ProcessExecutor(table, kill=table.kill)
    (result,) = getattr(executor, phase)([Member("n10", 10, "100", "run_a")], context)
    assert result.status == "requested" and "nothing sent" in result.note and not table.sent


def test_refused_targets_and_failing_cgroup_writes_are_reported(tmp_path: Path) -> None:
    table = World(proc(10, 1, uid=0))
    executor = ProcessExecutor(table, cgroup_root=tmp_path, kill=table.kill)
    context = Context("hlt_1", time.monotonic() + 0.1, invoking_uid=501)
    target = Member("n10", 10, "100", "run_a")
    assert executor.terminate([target], context)[0].status == "failed" and not table.sent
    group = tmp_path / "agenthalt-run_a"
    (group / "cgroup.freeze").mkdir(parents=True)  # cannot be read or written as a file
    (thaw,) = executor.release([{"freeze": "/agenthalt-run_a", "run": "run_a"}], context)
    assert thaw.status == "failed"
    (gone,) = executor.release([{"freeze": "/agenthalt-run_b", "run": "run_b"}], context)
    assert gone.status == "confirmed"
    mine = Member("n10", 10, "100", "run_a", uid=0, cgroup="/agenthalt-run_a")
    executor.suspend([mine], context)
    assert table.sent == [], "still a root process"


def test_a_lift_that_blows_up_after_removal_is_reported(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    c = build(home, world())
    result = halt(c)

    def boom(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(c.containment, "release", boom)
    (item,) = lift(c, result).released
    assert item.status == "failed" and "boom" in item.note


def test_without_executors_a_busy_store_is_an_error(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(store_module, "LOCK_TIMEOUT_S", 0.05)
    store = Store(home)
    store.ensure()
    fd = held_lock(home / "store" / ".lock")
    try:
        with pytest.raises(store_module.StoreBusyError):
            Coordinator(store).raise_halt(
                Scope.parse("agent:bot"), Mode.PAUSE, actor="o", reason="r"
            )
    finally:
        os.close(fd)


@pytest.mark.parametrize("header", ['{"halt_id": "hlt_x"}', '{"halt_id": "other"}'])
def test_a_forged_cut_record_cannot_be_lifted(home: Path, header: str) -> None:
    c = build(home, world())
    (home / "cuts").mkdir(parents=True, exist_ok=True)
    item = '{"op": "cut", "layer": "process", "item": {"pid": 10, "start": "100", "run": "run_a"}}'
    (home / "cuts" / "hlt_x.jsonl").write_text(f'{{"halt": {header}}}\n{item}\n')
    with pytest.raises(LookupError):
        c.lift("hlt_x", actor="op", reason="r")


def test_a_cut_record_that_cannot_be_written_is_incomplete(home: Path) -> None:
    (home / "cuts").write_text("not a directory")
    table = world()
    result = halt(build(home, table))
    assert not running(table) and result.outcome is ReceiptStatus.INCOMPLETE
    assert "record" in str(result.cut.reason)
    assert not CutLog(home).held(besides="x")
    writer = CutLog(home / "other").writer({"halt_id": "hlt_1"})
    os.close(writer._fd)  # type: ignore[arg-type]
    writer.cut("process", {})
    assert writer.failed
    writer.close()
