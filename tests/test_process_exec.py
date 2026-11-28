"""3.2 / 3.3: the process executor's safety rules, with a fake process table."""

from __future__ import annotations

import signal
import time
from pathlib import Path
from typing import Any

import pytest

from agenthalt.executors import Context, Member
from agenthalt.observe import ObserveError, Proc
from agenthalt.process_exec import ProcessExecutor, own_cgroup, refusal
from tests.lineage_helpers import FakeObserver, proc


def member(pid: int, **kwargs: Any) -> Member:
    return Member(f"n{pid}", pid, str(pid * 10), "run_a", **kwargs)


def ctx(ms: int = 300, **kwargs: object) -> Context:
    return Context("hlt_1", time.monotonic() + ms / 1000, invoking_uid=501, **kwargs)  # type: ignore[arg-type]


class Table(FakeObserver):
    """Signals change the fake table the way the kernel would."""

    def __init__(self, *procs: Proc) -> None:
        super().__init__()
        self.add(*procs)
        self.sent: list[tuple[int, int]] = []
        self.deaf: set[int] = set()
        self.denied: set[int] = set()

    def kill(self, pid: int, signum: int) -> None:
        if pid in self.denied:
            raise PermissionError
        self.sent.append((pid, signum))
        if pid in self.deaf:
            return
        old = self.procs[pid]
        if signum == signal.SIGKILL:
            del self.procs[pid]
            return
        state = "T" if signum == signal.SIGSTOP else "S"
        self.procs[pid] = Proc(old.pid, old.ppid, old.pgid, old.sid, old.uid, old.start, state)


def executor(table: Table, tmp_path: Path) -> ProcessExecutor:
    return ProcessExecutor(table, kill=table.kill, cgroup_root=tmp_path)


def test_parents_are_stopped_first_and_confirmed_by_observation(tmp_path: Path) -> None:
    table = Table(proc(10, 1), proc(11, 10))
    results = executor(table, tmp_path).suspend([member(11), member(10)], ctx())
    assert [pid for pid, _ in table.sent] == [10, 11]
    assert {r.status for r in results} == {"confirmed"}


def test_a_signal_that_does_nothing_is_only_requested(tmp_path: Path) -> None:
    table = Table(proc(10, 1))
    table.deaf = {10}
    (stopped,) = executor(table, tmp_path).suspend([member(10)], ctx(60))
    (killed,) = executor(table, tmp_path).terminate([member(10)], ctx(60))
    assert stopped.status == "requested" and killed.status == "requested"


def test_a_reused_pid_is_never_signalled(tmp_path: Path) -> None:
    table = Table(proc(10, 1, start=999))
    (stopped,) = executor(table, tmp_path).suspend([member(10)], ctx())
    (killed,) = executor(table, tmp_path).terminate([member(10)], ctx())
    assert table.sent == [] and stopped.status == "confirmed" == killed.status
    assert "gone" in stopped.note


def test_children_found_while_stopping_are_stopped_too(tmp_path: Path) -> None:
    table = Table(proc(10, 1))

    def expand(procs: dict[int, Proc]) -> list[Member]:
        if 11 not in table.procs:
            table.add(proc(11, 10))
            return []
        return [member(11)]

    results = executor(table, tmp_path).suspend([member(10)], ctx(expand=expand))
    assert {r.target for r in results} == {"n10", "n11"} and (11, signal.SIGSTOP) in table.sent


def test_permission_denied_is_failed(tmp_path: Path) -> None:
    table = Table(proc(10, 1))
    table.denied = {10}
    (stopped,) = executor(table, tmp_path).suspend([member(10)], ctx(60))
    (killed,) = executor(table, tmp_path).terminate([member(10)], ctx(60))
    assert stopped.status == killed.status == "failed" and "sudo" in stopped.note


def test_an_unobservable_host_confirms_nothing(tmp_path: Path) -> None:
    table = Table(proc(10, 1))
    table.fail = True
    run = executor(table, tmp_path)
    assert run.suspend([member(10)], ctx())[0].status == "requested"
    assert run.terminate([member(10)], ctx())[0].status == "requested"
    record = [{"pid": 10, "start": "100", "run": "run_a"}]
    assert run.release(record, ctx())[0].status == "failed"
    assert table.sent == []


@pytest.mark.parametrize(
    ("target", "why"),
    [
        (proc(1, 0), "pid 0 and 1"),
        (proc(50, 1), "running this halt"),
        (proc(40, 1), "running this halt"),
        (proc(60, 1, uid=0), "root process"),
    ],
)
def test_processes_that_are_never_signalled(target: Proc, why: str) -> None:
    table = {40: proc(40, 1), 45: proc(45, 40), 50: proc(50, 45), target.pid: target}
    if target.pid == 50:
        table[50] = proc(50, 45)
    assert why in str(refusal(table[target.pid], table, invoking_uid=501, me=50))


def test_root_may_signal_root_processes() -> None:
    assert refusal(proc(60, 1, uid=0), {}, invoking_uid=0, me=50) is None


def test_a_refused_target_is_failed_not_signalled(tmp_path: Path) -> None:
    table = Table(proc(10, 1, uid=0))
    (stopped,) = executor(table, tmp_path).suspend([member(10)], ctx())
    (killed,) = executor(table, tmp_path).terminate([member(10)], ctx())
    assert table.sent == [] and stopped.status == killed.status == "failed"


def test_only_the_runs_own_cgroup_is_ever_touched(tmp_path: Path) -> None:
    group = tmp_path / "user" / "agenthalt-run_a"
    group.mkdir(parents=True)
    assert own_cgroup("/user/agenthalt-run_a", "run_a", tmp_path) == group
    for bad in (None, "/user", "/", "/user/agenthalt-run_b", "/user/../user/agenthalt-run_a"):
        assert own_cgroup(bad, "run_a", tmp_path) is None
    assert own_cgroup("/gone/agenthalt-run_a", "run_a", tmp_path) is None


def fake_group(tmp_path: Path, *pids: int) -> Path:
    group = tmp_path / "agenthalt-run_a"
    group.mkdir()
    (group / "cgroup.procs").write_text("".join(f"{p}\n" for p in pids))
    (group / "cgroup.events").write_text("populated 1\nfrozen 1\n")
    return group


def test_a_run_with_its_own_cgroup_is_frozen_killed_and_thawed(tmp_path: Path) -> None:
    group = fake_group(tmp_path, 10)
    table = Table(proc(10, 1))
    table.deaf = {10}  # the freezer is what stops it
    run = executor(table, tmp_path)
    target = member(10, cgroup="/agenthalt-run_a")
    intended: list[Any] = []
    (stopped,) = run.suspend([target], ctx(record=lambda layer, item: intended.append(item)))
    assert stopped.status == "confirmed" and (group / "cgroup.freeze").read_text() == "1"
    assert {"freeze": "/agenthalt-run_a", "run": "run_a"} in intended and stopped.undo
    run.terminate([target], ctx(60))
    assert (group / "cgroup.kill").read_text() == "1"
    table.deaf = set()
    released = run.release(intended, ctx())
    assert {r.status for r in released} == {"confirmed"}
    assert (group / "cgroup.freeze").read_text() == "0"


def test_a_cgroup_holding_the_halting_process_is_left_alone(tmp_path: Path) -> None:
    import os

    group = fake_group(tmp_path, 10, os.getpid())
    table = Table(proc(10, 1), proc(os.getpid(), 1))
    executor(table, tmp_path).suspend([member(10, cgroup="/agenthalt-run_a")], ctx())
    assert not (group / "cgroup.freeze").exists()


def test_a_process_stopped_before_the_halt_is_not_ours_to_continue(tmp_path: Path) -> None:
    table = Table(proc(10, 1))
    table.kill(10, signal.SIGSTOP)
    run = executor(table, tmp_path)
    (result,) = run.suspend([member(10)], ctx())
    assert result.undo is None
    (held,) = run.suspend([member(10)], ctx(held=lambda: frozenset({(10, "100")})))
    assert held.undo is not None, "stopped by another halt: still ours"


def test_release_of_a_dead_process_is_quiet(tmp_path: Path) -> None:
    run = executor(Table(), tmp_path)
    (result,) = run.release([{"pid": 10, "start": "100", "run": "run_a"}], ctx())
    assert result.status == "confirmed" and "gone" in result.note


def test_signal_failures_are_reported_and_vanished_processes_are_not(tmp_path: Path) -> None:
    table = Table(proc(10, 1))

    def gone(pid: int, signum: int) -> None:
        raise ProcessLookupError

    def broken(pid: int, signum: int) -> None:
        raise OSError("bad")

    assert ProcessExecutor(table, kill=gone)._send(member(10), signal.SIGSTOP) is None
    assert ProcessExecutor(table, kill=broken)._send(member(10), signal.SIGSTOP) == "bad"
    table.fail = True  # an injected kill keeps Linux from opening a pidfd for a made-up pid
    assert "unavailable" in str(ProcessExecutor(table, kill=gone)._send(member(10), signal.SIGSTOP))


def test_cgroup_files_that_vanish_are_tolerated(tmp_path: Path) -> None:
    group = tmp_path / "agenthalt-run_a"
    group.mkdir()  # no cgroup.procs or cgroup.events at all
    table = Table(proc(10, 1))
    (result,) = executor(table, tmp_path).suspend([member(10, cgroup="/agenthalt-run_a")], ctx())
    assert result.status == "confirmed"
    table = Table(proc(10, 1))
    table.deaf = {10}
    (result,) = executor(table, tmp_path).suspend([member(10, cgroup="/agenthalt-run_a")], ctx(60))
    assert result.status == "requested"


@pytest.mark.parametrize("failing", [2, 3])
def test_observation_lost_midway_confirms_nothing(tmp_path: Path, failing: int) -> None:
    table = Table(proc(10, 1))
    table.deaf = {10}  # keeps the loop going long enough
    real, calls = table.snapshot, []

    def snapshot(timeout_s: float = 5.0) -> dict[int, Proc]:
        calls.append(1)
        if len(calls) == failing:
            raise ObserveError("gone")
        return real(timeout_s)

    table.snapshot = snapshot  # type: ignore[method-assign]
    table.probe = lambda pids, timeout_s=5.0: {10: table.procs[10]}  # type: ignore[method-assign]
    assert executor(table, tmp_path).suspend([member(10)], ctx())[0].status == "requested"


def test_observation_lost_after_the_kill_is_requested(tmp_path: Path) -> None:
    table = Table(proc(10, 1))
    real, calls = table.snapshot, []

    def snapshot(timeout_s: float = 5.0) -> dict[int, Proc]:
        calls.append(1)
        if len(calls) > 1:
            raise ObserveError("gone")
        return real(timeout_s)

    table.snapshot = snapshot  # type: ignore[method-assign]
    table.probe = lambda pids, timeout_s=5.0: {10: proc(10, 1)}  # type: ignore[method-assign]
    assert executor(table, tmp_path).terminate([member(10)], ctx())[0].status == "requested"
