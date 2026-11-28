"""3.4 / 3.5 / 3.T: halting real process trees, end to end.

Every process signalled here was started by the test itself and enrolled in a temporary home.
"""

from __future__ import annotations

import contextlib
import json
import os
import signal
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from agenthalt.cli import main
from agenthalt.containment import Containment
from agenthalt.coordinator import Coordinator
from agenthalt.egress import EgressExecutor
from agenthalt.executors import ExecutorSigner, Result
from agenthalt.exit_codes import ReceiptStatus
from agenthalt.journal import Journal
from agenthalt.lineage import LineageRegistry
from agenthalt.observe import Proc, SystemObserver
from agenthalt.process_exec import ProcessExecutor
from agenthalt.scopes import Mode, Scope
from agenthalt.store import HaltLifecycle, Store
from agenthalt.supervisor import LIVENESS_GAP, Supervisor

PY = sys.executable
OBSERVER = SystemObserver()

# a parent and a child that each append to their own file for as long as they are running
AGENT = """
import os, subprocess, sys, time, signal
out, depth = sys.argv[1], int(sys.argv[2])
signal.signal(signal.SIGTERM, signal.SIG_IGN)
if depth:
    subprocess.Popen([sys.executable, __file__, out, str(depth - 1)])
while True:
    open(f"{out}.{depth}", "a").write(".")
    time.sleep(0.02)
"""


def state(pid: int) -> str:
    proc = OBSERVER.snapshot().get(pid)
    return "" if proc is None else proc.state[:1]


def sizes(out: Path) -> list[int]:
    return [p.stat().st_size for p in sorted(out.parent.glob(out.name + ".*"))]


def acting(out: Path) -> bool:
    before = sizes(out)
    time.sleep(0.2)
    return sizes(out) != before


def wait_for(check: Any, timeout: float = 15.0) -> None:
    end = time.monotonic() + timeout
    while not check():
        assert time.monotonic() < end, "timed out"
        time.sleep(0.05)


class Agent:
    def __init__(self, tmp_path: Path, name: str, depth: int = 1) -> None:
        script = tmp_path / "agent.py"
        script.write_text(AGENT)
        self.out = tmp_path / name
        self.home = tmp_path / "h"
        self.proc = subprocess.Popen([PY, str(script), str(self.out), str(depth)])
        wait_for(lambda: len(sizes(self.out)) == depth + 1)
        attached = Supervisor(self.home, containment="pgroup").attach(self.proc.pid, name=name)
        self.run = attached.run_id

    def mine(self) -> list[int]:
        table = OBSERVER.snapshot()
        found = {self.proc.pid}
        for _ in range(4):
            found |= {p.pid for p in table.values() if p.ppid in found}
        return sorted(found)

    def stop(self) -> None:
        for pid in self.mine()[::-1]:
            with contextlib.suppress(OSError):
                os.kill(pid, signal.SIGKILL)
        self.proc.wait(timeout=10)


@pytest.fixture
def agents(tmp_path: Path) -> Iterator[Any]:
    made: list[Agent] = []

    def make(name: str = "bot", depth: int = 1) -> Agent:
        made.append(Agent(tmp_path, name, depth))
        return made[-1]

    yield make
    for agent in made:
        agent.stop()


def containment(home: Path, **kwargs: Any) -> Containment:
    observer = SystemObserver()
    adapters: dict[str, Any] = {
        "process": ProcessExecutor(observer),
        "sandbox": EgressExecutor(observer, unsupported=lambda: "not here"),
    }
    kwargs.setdefault("adapters", adapters)
    kwargs.setdefault("signer", ExecutorSigner(home))
    kwargs.setdefault("deadline_ms", 5000)
    return Containment(LineageRegistry(home, journal=Journal(home)), observer, **kwargs)


def coordinator(home: Path, **kwargs: Any) -> Coordinator:
    store = Store(home)
    store.ensure()
    return Coordinator(store, containment(home, **kwargs))


def halt(c: Coordinator, scope: str, mode: Mode) -> Any:
    return c.raise_halt(Scope.parse(scope), mode, actor="op", reason="r")


def test_kill_stops_the_whole_tree(agents: Any) -> None:
    agent = agents(depth=2)
    pids = agent.mine()
    assert len(pids) == 3 and acting(agent.out)
    result = halt(coordinator(agent.home), "agent:bot", Mode.KILL)
    assert not any(state(pid) for pid in pids), "zero survivors"
    assert not acting(agent.out)
    assert result.cut.survivors == [] and result.layers["process"] == "confirmed"
    assert result.layers["sandbox"] == "unsupported" == result.layers["gateway"]
    assert result.outcome is ReceiptStatus.PARTIAL_LAYER
    assert result.halt.status is HaltLifecycle.FINISHED
    signer = ExecutorSigner(agent.home)
    done = [c for c in result.cut.confirmations if c.status == "confirmed"]
    assert done and all(c.attestation == "self" for c in done)
    assert all(signer.verify(result.halt.halt_id, c) for c in done)
    assert Journal(agent.home).verify().ok
    assert Store(agent.home).health().status == "ok"


def test_pause_freezes_and_lift_continues(agents: Any) -> None:
    agent = agents()
    c = coordinator(agent.home)
    result = halt(c, "agent:bot", Mode.PAUSE)
    pids = agent.mine()
    assert [state(p) for p in pids] == ["T", "T"] and not acting(agent.out)
    assert "sandbox" not in result.layers and "credentials" not in result.layers
    released = c.lift(result.halt.halt_id, actor="op", reason="false alarm").released
    assert [r.status for r in released] == ["confirmed", "confirmed"]
    wait_for(lambda: acting(agent.out))


def test_lift_keeps_frozen_what_another_halt_covers(agents: Any) -> None:
    agent = agents()
    c = coordinator(agent.home)
    first = halt(c, "agent:bot", Mode.PAUSE)
    second = halt(c, f"run:{agent.run}", Mode.PAUSE)
    kept = c.lift(first.halt.halt_id, actor="op", reason="r").released
    assert kept and all(second.halt.halt_id in r.note for r in kept)
    assert not acting(agent.out)
    c.lift(second.halt.halt_id, actor="op", reason="r")
    wait_for(lambda: acting(agent.out))


def test_lift_leaves_what_was_already_stopped(agents: Any) -> None:
    agent = agents(depth=0)
    os.kill(agent.proc.pid, signal.SIGSTOP)
    c = coordinator(agent.home)
    result = halt(c, "agent:bot", Mode.PAUSE)
    assert c.lift(result.halt.halt_id, actor="op", reason="r").released == ()
    assert state(agent.proc.pid) == "T"


def test_lifting_a_kill_continues_nothing(agents: Any) -> None:
    agent = agents(depth=0)
    c = coordinator(agent.home)
    result = halt(c, "agent:bot", Mode.KILL)
    assert c.lift(result.halt.halt_id, actor="op", reason="r").released == ()


def test_other_agents_are_untouched(agents: Any) -> None:
    target, bystander = agents("bot"), agents("other")
    halt(coordinator(target.home), "agent:bot", Mode.KILL)
    assert acting(bystander.out)


def test_fleet_and_session_scopes(agents: Any) -> None:
    one, two = agents("one", 0), agents("two", 0)
    result = halt(coordinator(one.home), "session:nobody", Mode.PAUSE)
    assert result.outcome is ReceiptStatus.INCOMPLETE and acting(one.out)
    halt(coordinator(one.home), "all", Mode.KILL)
    assert not acting(one.out) and not acting(two.out)


def test_raising_again_cuts_again_under_the_same_id(agents: Any) -> None:
    agent = agents(depth=0)
    c = coordinator(agent.home)
    first = halt(c, "agent:bot", Mode.PAUSE)
    os.kill(agent.proc.pid, signal.SIGCONT)  # the agent got loose
    wait_for(lambda: acting(agent.out))
    again = halt(c, "agent:bot", Mode.PAUSE)
    assert not again.created and again.halt.halt_id == first.halt.halt_id
    assert not acting(agent.out) and len(c.executions(first.halt.halt_id)) == 2


def test_the_block_precedes_every_signal_and_evidence_precedes_the_kill(agents: Any) -> None:
    agent = agents(depth=0)
    seen: list[Any] = []

    def kill(pid: int, signum: int) -> None:
        seen.append((signum, len(Store(agent.home).load().halts)))
        os.kill(pid, signum)

    observer = SystemObserver()
    c = coordinator(
        agent.home,
        adapters={"process": ProcessExecutor(observer, kill=kill)},
        evidence=lambda halt_id, members: seen.append(("evidence", state(members[0].pid))),
    )
    result = halt(c, "agent:bot", Mode.KILL)
    assert seen == [(signal.SIGSTOP, 1), ("evidence", "T"), (signal.SIGKILL, 1)]
    assert result.layers["sandbox"] == "unsupported", "no sandbox adapter at all"


def test_without_a_signer_nothing_is_confirmed(agents: Any) -> None:
    agent = agents(depth=0)
    result = halt(coordinator(agent.home, signer=None), "agent:bot", Mode.KILL)
    assert result.layers["process"] == "requested"
    assert result.outcome is ReceiptStatus.INCOMPLETE and result.cut.survivors


def test_a_hung_adapter_cannot_hold_the_halt(agents: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    agent = agents(depth=0)
    monkeypatch.setattr("agenthalt.containment.GRACE_S", 0.2)

    class Hung:
        attestation = "self"

        def block(self, targets: Any, ctx: Any) -> list[Result]:
            time.sleep(30)
            return []

    adapters = {"process": ProcessExecutor(SystemObserver()), "sandbox": Hung()}
    started = time.monotonic()
    result = halt(
        coordinator(agent.home, adapters=adapters, deadline_ms=1500),
        "agent:bot",
        Mode.QUARANTINE,
    )
    assert time.monotonic() - started < 10
    assert result.layers["sandbox"] == "requested" and state(agent.proc.pid) == "T"
    assert result.outcome is ReceiptStatus.INCOMPLETE


def test_a_missed_deadline_is_requested_but_still_signalled(agents: Any) -> None:
    agent = agents(depth=0)
    result = halt(coordinator(agent.home, deadline_ms=1), "agent:bot", Mode.KILL)
    assert result.outcome is ReceiptStatus.INCOMPLETE
    wait_for(lambda: not acting(agent.out))


def test_a_network_cut_is_released_after_a_confirmed_kill_and_kept_by_quarantine(
    agents: Any,
) -> None:
    agent = agents(depth=0)
    released: list[Any] = []

    class Wall:
        attestation = "self"

        def block(self, targets: Any, ctx: Any) -> list[Result]:
            return [Result(m.run, "confirmed", "cut", {"run": m.run}) for m in targets]

        def release(self, record: Any, ctx: Any) -> list[Result]:
            released.append(list(record))
            return [Result(str(i["run"]), "confirmed", "removed") for i in record]

    adapters = {"process": ProcessExecutor(SystemObserver()), "sandbox": Wall()}
    c = coordinator(agent.home, adapters=adapters)
    quarantined = halt(c, "agent:bot", Mode.QUARANTINE)
    assert released == [] and quarantined.layers["sandbox"] == "confirmed"
    killed = halt(c, "agent:bot", Mode.KILL)
    assert released == [[{"run": agent.run}]] and killed.cut.undo["sandbox"] == []
    out = c.lift(quarantined.halt.halt_id, actor="op", reason="r").released
    assert len(released) == 2 and "removed" in [r.note for r in out]


@pytest.mark.parametrize("scope", ["tool:deploy", "writes-disabled", "tenant:t1"])
def test_a_scope_that_names_no_process_signals_nothing(agents: Any, scope: str) -> None:
    agent = agents(depth=0)
    result = halt(coordinator(agent.home), scope, Mode.KILL)
    assert result.layers["process"] == "unsupported" and acting(agent.out)


def test_damaged_lineage_is_incomplete_not_a_crash(agents: Any) -> None:
    agent = agents(depth=0)
    (agent.home / "lineage" / "seg-000001.jsonl").write_bytes(b"\xff\n")
    result = halt(coordinator(agent.home), "agent:bot", Mode.KILL)
    assert result.outcome is ReceiptStatus.INCOMPLETE and acting(agent.out)
    assert result.layers["runtime_choke"] == "enforced"


def test_cli_kill_status_and_lift(agents: Any, capsys: pytest.CaptureFixture[str]) -> None:
    agent = agents()
    home = ["--home", str(agent.home)]
    code = main([*home, "pause", "--agent", "bot", "--deadline-ms", "5000", "--json"])
    data = json.loads(capsys.readouterr().out)
    assert code == 2 and data["outcome"] == "partial-layer" and data["survivors"] == []
    assert len(data["members"]) == 2 and not acting(agent.out)
    assert main([*home, "lift", "--halt", data["halt_id"], "--reason", "ok"]) == 0
    assert "continued" in capsys.readouterr().out
    code = main([*home, "kill", "--agent", "bot", "--reason", "prod", "--deadline-ms", "5000"])
    out = capsys.readouterr().out
    assert code == 2 and "2 of 2 confirmed killed" in out and "outcome: partial-layer" in out
    assert not acting(agent.out)


# an agent that never looks at the halt store: no hook, no library
def test_zero_hook_agent_stops_acting(agents: Any) -> None:
    agent = agents(depth=0)
    assert "agenthalt" not in AGENT
    halt(coordinator(agent.home), "agent:bot", Mode.PAUSE)
    assert not acting(agent.out)


def test_a_run_under_the_supervisor_is_killed(tmp_path: Path) -> None:
    home, out = tmp_path / "h", tmp_path / "bot"
    script = tmp_path / "agent.py"
    script.write_text(AGENT)
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}
    launch = [PY, "-m", "agenthalt", "--home", str(home), "run", "--name", "bot", "--"]
    supervisor = subprocess.Popen(
        [*launch, PY, str(script), str(out), "1"],
        env=env,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        if sys.platform == "linux" and supervisor.poll() == 5:
            pytest.skip("no cgroup delegation here")
        wait_for(lambda: len(sizes(out)) == 2 or supervisor.poll() is not None)
        if supervisor.poll() is not None:
            pytest.skip(f"run refused: {supervisor.communicate()[1][-200:]}")
        pause = coordinator(home)
        first = halt(pause, "agent:bot", Mode.PAUSE)
        assert not acting(out) and first.cut.survivors == []
        pause.lift(first.halt.halt_id, actor="op", reason="r")
        wait_for(lambda: acting(out))
        result = halt(pause, "agent:bot", Mode.KILL)
        _, err = supervisor.communicate(timeout=20)
        assert supervisor.returncode == 128 + signal.SIGKILL, err
        assert "is frozen" in err
        assert result.cut.survivors == [] and not acting(out)
    finally:
        if supervisor.poll() is None:
            supervisor.kill()
            supervisor.wait()


# bookkeeping failures --------------------------------------------------------


def test_a_journal_that_fails_after_the_block_does_not_stop_the_cut(
    agents: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    agent = agents(depth=0)
    c = coordinator(agent.home)
    real = c.store.journal.append

    def append(action: str, **kwargs: Any) -> Any:
        if action in ("execute", "complete"):
            raise OSError("disk full")
        return real(action, **kwargs)

    monkeypatch.setattr(c.store.journal, "append", append)
    result = halt(c, "agent:bot", Mode.KILL)
    assert not acting(agent.out)
    assert result.outcome is ReceiptStatus.INCOMPLETE and "could not be journaled" in str(
        result.cut.reason
    )


def test_a_block_that_cannot_be_written_is_exit_3(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def fail(*args: Any, **kwargs: Any) -> None:
        raise OSError("read-only file system")

    monkeypatch.setattr(Store, "raise_or_get", fail)
    monkeypatch.setattr(Store, "remove", fail)
    home = ["--home", str(tmp_path / "h")]
    assert main([*home, "kill", "--agent", "bot", "--reason", "r"]) == 3
    assert "HALT FAILED" in capsys.readouterr().err
    monkeypatch.setattr(Coordinator, "lift", fail)
    assert main([*home, "lift", "--halt", "hlt_x", "--reason", "r"]) == 3


def test_a_broken_plugin_does_not_stop_the_kill_switch(
    agents: Any, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    agent = agents(depth=0)

    class Point:
        name = "broken"

        def load(self) -> Any:
            raise ImportError("missing dependency")

    monkeypatch.setattr("importlib.metadata.entry_points", lambda group: [Point()])
    home = ["--home", str(agent.home)]
    code = main([*home, "kill", "--agent", "bot", "--reason", "r", "--deadline-ms", "5000"])
    assert code == 2 and "using the built-in executors" in capsys.readouterr().err
    assert not acting(agent.out)
    main([*home, "doctor"])
    assert "broken" in capsys.readouterr().out


# paths that only misbehaviour reaches ----------------------------------------


def test_a_child_forked_during_the_stop_is_cut_and_recorded(agents: Any) -> None:
    agent = agents(depth=0)
    blocked: list[list[str]] = []

    class Wall:
        attestation = "self"

        def block(self, targets: Any, ctx: Any) -> list[Result]:
            blocked.append(sorted(m.node for m in targets))
            return [Result(m.run, "confirmed", "cut") for m in targets]

    observer = SystemObserver()
    c = coordinator(agent.home, adapters={"process": ProcessExecutor(observer), "sandbox": Wall()})
    real = c.containment.observer.snapshot  # type: ignore[union-attr]
    extra: list[int] = []

    def snapshot(timeout_s: float = 5.0) -> Any:
        table = real(timeout_s)
        if extra:
            table[extra[0]] = Proc(extra[0], agent.proc.pid, extra[0], 0, os.getuid(), "9" * 12)
        if not extra:
            extra.append(2**22 + 7)  # appears only after the first listing
        return table

    c.containment.observer.snapshot = snapshot  # type: ignore[union-attr, method-assign]
    result = halt(c, "agent:bot", Mode.QUARANTINE)
    assert len(result.cut.members) == 2 and len(blocked) == 2 and len(blocked[1]) == 2
    nodes = {
        e.child_run for e in LineageRegistry(agent.home, journal=Journal(agent.home)).read().edges
    }
    assert f"proc_{extra[0]}_{'9' * 12}" in nodes


def test_something_holding_the_liveness_handle_means_incomplete(agents: Any) -> None:
    agent = agents(depth=0)
    LineageRegistry(agent.home, journal=Journal(agent.home)).record_finding(
        "lineage_gap",
        {"run": agent.run, "node": agent.run, "why": LIVENESS_GAP},
        actor="t",
        unique=("run",),
    )
    result = halt(coordinator(agent.home), "agent:bot", Mode.KILL)
    assert result.outcome is ReceiptStatus.INCOMPLETE and result.cut.reason == LIVENESS_GAP


def test_an_unexpected_error_in_the_cut_is_reported(agents: Any) -> None:
    agent = agents(depth=0)
    c = coordinator(agent.home)
    c.containment.observer = None  # type: ignore[union-attr]
    result = halt(c, "agent:bot", Mode.KILL)
    assert result.outcome is ReceiptStatus.INCOMPLETE and result.cut.reason


def test_no_process_executor_is_unsupported(agents: Any) -> None:
    agent = agents(depth=0)
    result = halt(coordinator(agent.home, adapters={}), "agent:bot", Mode.QUARANTINE)
    assert result.layers["process"] == "unsupported" and acting(agent.out)


@pytest.mark.parametrize("broken", [True, False])
def test_a_release_that_cannot_happen_is_reported(agents: Any, broken: bool) -> None:
    agent = agents(depth=0)
    c = coordinator(agent.home)
    result = halt(c, "agent:bot", Mode.PAUSE)

    class Broken:
        def release(self, record: Any, ctx: Any) -> list[Result]:
            raise RuntimeError("boom")

    c.containment.adapters = {"process": Broken()} if broken else {}  # type: ignore[union-attr]
    released = c.lift(result.halt.halt_id, actor="op", reason="r").released
    assert [r.status for r in released] == ["failed"]


def test_a_halt_lifted_while_cutting_is_not_left_frozen(agents: Any) -> None:
    agent = agents(depth=0)
    store = Store(agent.home)

    class Slow(ProcessExecutor):
        def suspend(self, targets: Any, ctx: Any) -> list[Result]:
            results = super().suspend(targets, ctx)
            store.remove(ctx.halt_id, actor="op", reason="stand down")
            return results

    c = coordinator(agent.home, adapters={"process": Slow(SystemObserver())})
    halt(c, "agent:bot", Mode.PAUSE)
    wait_for(lambda: acting(agent.out))
    assert store.load().halts == ()


def test_the_probe_sees_only_the_asked_processes() -> None:
    me = os.getpid()
    assert list(OBSERVER.probe([me])) == [me]
    assert OBSERVER.probe([2**22 + 11]) == {}


def test_demo_1_runs(tmp_path: Path) -> None:
    script = Path(__file__).resolve().parents[1] / "examples" / "demo1_replit_stop.py"
    done = subprocess.run(
        [PY, str(script)], capture_output=True, text=True, timeout=90, check=False
    )
    assert done.returncode == 0 and "demo passed" in done.stdout, done.stdout + done.stderr
