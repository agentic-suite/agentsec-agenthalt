"""1.5 Idempotency & scope composition (#417): raise/lift, the lifecycle, concurrent halts."""

from __future__ import annotations

import multiprocessing
from pathlib import Path

import pytest

from agenthalt.coordinator import Coordinator, LifecycleError
from agenthalt.exit_codes import ReceiptStatus
from agenthalt.journal import Journal
from agenthalt.scopes import Mode, Scope
from agenthalt.store import HaltLifecycle, Store


def coord(tmp_path: Path) -> Coordinator:
    store = Store(tmp_path / ".agenthalt")
    store.ensure()
    return Coordinator(store)


def actions(tmp_path: Path) -> list[str]:
    return [e["action"] for e in Journal(tmp_path / ".agenthalt").entries()]


def test_raise_runs_the_full_lifecycle_and_stays_enforced(tmp_path: Path) -> None:
    c = coord(tmp_path)
    result = c.raise_halt(Scope.parse("agent:bot"), Mode.KILL, actor="maya", reason="prod mutation")
    assert result.created
    assert result.halt.status is HaltLifecycle.FINISHED
    # M1 has no executor layers: the honest outcome is incomplete, never complete
    assert result.outcome is ReceiptStatus.INCOMPLETE
    assert result.layers == {
        "runtime_choke": "enforced",
        "gateway": "unsupported",
        "process": "unsupported",
        "credentials": "unsupported",
        "sandbox": "unsupported",
    }
    assert (
        c.store.load().get(result.halt.halt_id) is not None
    )  # finished halts stay active until lifted
    assert actions(tmp_path) == ["raise", "execute", "execute", "complete"]


def test_lifecycle_transitions_are_journaled_with_status(tmp_path: Path) -> None:
    c = coord(tmp_path)
    c.raise_halt(Scope.parse("all"), Mode.PAUSE, actor="maya", reason="r")
    statuses = [
        e["payload"]["store"]["halt"]["status"]
        for e in Journal(tmp_path / ".agenthalt").entries()
        if e["action"] != "lift"
    ]
    assert statuses == ["pending", "blocking", "executing", "finished"]
    complete = list(Journal(tmp_path / ".agenthalt").entries())[-1]
    assert complete["payload"]["outcome"] == "incomplete"


def test_duplicate_raise_is_idempotent(tmp_path: Path) -> None:
    c = coord(tmp_path)
    first = c.raise_halt(Scope.parse("agent:bot"), Mode.KILL, actor="maya", reason="a")
    again = c.raise_halt(Scope.parse("agent:bot"), Mode.KILL, actor="ravi", reason="b")
    assert not again.created and again.halt.halt_id == first.halt.halt_id
    assert len(c.store.load().halts) == 1
    entries = list(Journal(tmp_path / ".agenthalt").entries())
    dup = [e for e in entries if e["action"] == "finding"]
    assert len(dup) == 1 and dup[0]["payload"]["finding"] == "duplicate_raise"
    assert dup[0]["actor"] == "ravi" and dup[0]["halt_id"] == first.halt.halt_id


def test_duplicate_during_blocking_returns_the_same_id(tmp_path: Path) -> None:
    c = coord(tmp_path)
    created = c.store.raise_or_get(
        c.new_halt(Scope.parse("agent:bot"), Mode.KILL, actor="maya", reason="r"), actor="maya"
    )[0]
    c.advance(created.halt_id, HaltLifecycle.BLOCKING, actor="haltd")
    again = c.raise_halt(Scope.parse("agent:bot"), Mode.KILL, actor="ravi", reason="r")
    assert not again.created and again.halt.halt_id == created.halt_id
    assert again.halt.status is HaltLifecycle.BLOCKING


def test_different_mode_or_scope_is_a_different_halt(tmp_path: Path) -> None:
    c = coord(tmp_path)
    a = c.raise_halt(Scope.parse("agent:bot"), Mode.PAUSE, actor="m", reason="r")
    b = c.raise_halt(Scope.parse("agent:bot"), Mode.KILL, actor="m", reason="r")
    d = c.raise_halt(Scope.parse("all"), Mode.PAUSE, actor="m", reason="r")
    assert len({a.halt.halt_id, b.halt.halt_id, d.halt.halt_id}) == 3
    assert len(c.store.load().halts) == 3


def test_invalid_transitions_are_refused(tmp_path: Path) -> None:
    c = coord(tmp_path)
    halt, _ = c.store.raise_or_get(
        c.new_halt(Scope.parse("all"), Mode.KILL, actor="m", reason="r"), actor="m"
    )
    with pytest.raises(LifecycleError):
        c.advance(halt.halt_id, HaltLifecycle.EXECUTING, actor="m")  # skips blocking
    with pytest.raises(LifecycleError):
        c.advance(halt.halt_id, HaltLifecycle.LIFTED, actor="m")  # lifting is lift(), not advance()
    with pytest.raises(LifecycleError):
        c.advance("hlt_nope", HaltLifecycle.BLOCKING, actor="m")


def test_transition_table_is_exhaustive() -> None:
    from agenthalt.coordinator import TRANSITIONS

    assert set(TRANSITIONS) == set(HaltLifecycle)
    assert TRANSITIONS[HaltLifecycle.LIFTED] == frozenset()
    assert TRANSITIONS[HaltLifecycle.FINISHED] == frozenset()


def test_lifecycle_and_outcome_are_separate_types() -> None:
    assert not {s.value for s in HaltLifecycle} & {s.value for s in ReceiptStatus}


def test_lift_removes_and_journals(tmp_path: Path) -> None:
    c = coord(tmp_path)
    r = c.raise_halt(Scope.parse("agent:bot"), Mode.KILL, actor="maya", reason="r")
    c.lift(r.halt.halt_id, actor="maya", reason="false alarm")
    assert c.store.load().halts == ()
    assert actions(tmp_path)[-1] == "lift"
    # after a lift the same scope+mode is a new halt
    again = c.raise_halt(Scope.parse("agent:bot"), Mode.KILL, actor="maya", reason="r")
    assert again.created and again.halt.halt_id != r.halt.halt_id


def test_lift_during_executing(tmp_path: Path) -> None:
    c = coord(tmp_path)
    halt, _ = c.store.raise_or_get(
        c.new_halt(Scope.parse("all"), Mode.KILL, actor="m", reason="r"), actor="m"
    )
    c.advance(halt.halt_id, HaltLifecycle.BLOCKING, actor="m")
    c.advance(halt.halt_id, HaltLifecycle.EXECUTING, actor="m")
    c.lift(halt.halt_id, actor="m", reason="operator stood down mid-flight")
    lift = list(Journal(tmp_path / ".agenthalt").entries())[-1]
    assert lift["action"] == "lift" and lift["payload"]["lifted_from"] == "executing"


def test_lift_requires_a_reason_and_a_known_halt(tmp_path: Path) -> None:
    c = coord(tmp_path)
    r = c.raise_halt(Scope.parse("all"), Mode.KILL, actor="m", reason="r")
    with pytest.raises(ValueError):
        c.lift(r.halt.halt_id, actor="m", reason="  ")
    with pytest.raises(LookupError):
        c.lift("hlt_nope", actor="m", reason="x")


def _race(home: str, n: int) -> None:
    c = Coordinator(Store(Path(home)))
    for _ in range(n):
        c.raise_halt(Scope.parse("agent:bot"), Mode.KILL, actor="racer", reason="same alert")


def _distinct(home: str, i: int) -> None:
    c = Coordinator(Store(Path(home)))
    c.raise_halt(Scope.parse(f"agent:a{i}"), Mode.PAUSE, actor="racer", reason="r")


def _run(target: object, args_list: list[tuple[str, int]]) -> None:
    ctx = multiprocessing.get_context("spawn")
    procs = [ctx.Process(target=target, args=a) for a in args_list]  # type: ignore[arg-type]
    for p in procs:
        p.start()
    for p in procs:
        p.join(60)
        assert p.exitcode == 0


def test_concurrent_duplicate_raises_create_one_halt(tmp_path: Path) -> None:
    home = tmp_path / ".agenthalt"
    Store(home).ensure()
    _run(_race, [(str(home), 3)] * 4)
    store = Store(home)
    assert len(store.load().halts) == 1
    assert Journal(home).verify().ok
    assert store.load() == store.replay()


def test_concurrent_different_halts_compose_without_corruption(tmp_path: Path) -> None:
    home = tmp_path / ".agenthalt"
    Store(home).ensure()
    _run(_distinct, [(str(home), i) for i in range(6)])
    store = Store(home)
    assert sorted(str(h.scope) for h in store.load().halts) == [f"agent:a{i}" for i in range(6)]
    assert Journal(home).verify().ok and store.load() == store.replay()


def test_lift_race_with_another_lifter(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    c = coord(tmp_path)
    r = c.raise_halt(Scope.parse("all"), Mode.KILL, actor="m", reason="r")

    def already_gone(*args: object, **kwargs: object) -> None:
        raise KeyError(r.halt.halt_id)

    monkeypatch.setattr(c.store, "remove", already_gone)
    with pytest.raises(LookupError):
        c.lift(r.halt.halt_id, actor="m", reason="x")


def test_a_lift_racing_an_advance_is_never_undone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Review finding: advance() read the halt, then wrote it back outside the lock. A lift landing in
    # between was silently undone (the lifted halt re-inserted). The transition must be atomic.
    c = coord(tmp_path)
    halt, _ = c.store.raise_or_get(
        c.new_halt(Scope.parse("all"), Mode.KILL, actor="m", reason="r"), actor="m"
    )
    real_load = c.store.load
    lifted: list[int] = []

    def load_then_someone_lifts() -> object:
        state = real_load()
        if not lifted:
            lifted.append(1)
            Coordinator(Store(tmp_path / ".agenthalt")).lift(
                halt.halt_id, actor="ravi", reason="stand down"
            )
        return state

    monkeypatch.setattr(c.store, "load", load_then_someone_lifts)
    with pytest.raises(LifecycleError):
        c.advance(halt.halt_id, HaltLifecycle.BLOCKING, actor="agenthalt")
    monkeypatch.setattr(c.store, "load", real_load)
    assert c.store.load().get(halt.halt_id) is None  # the lift stands
    assert c.store.health().status == "ok"


def test_two_advancers_cannot_both_move_a_halt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    c = coord(tmp_path)
    halt, _ = c.store.raise_or_get(
        c.new_halt(Scope.parse("all"), Mode.KILL, actor="m", reason="r"), actor="m"
    )
    real_load = c.store.load
    raced: list[int] = []

    def load_then_another_advances() -> object:
        state = real_load()
        if not raced:
            raced.append(1)
            Coordinator(Store(tmp_path / ".agenthalt")).advance(
                halt.halt_id, HaltLifecycle.BLOCKING, actor="other"
            )
        return state

    monkeypatch.setattr(c.store, "load", load_then_another_advances)
    with pytest.raises(LifecycleError, match="expected pending"):
        c.advance(halt.halt_id, HaltLifecycle.BLOCKING, actor="agenthalt")
