"""1.1 Halt store (#413): authoritative, persisted, journal-first, rebuildable."""

from __future__ import annotations

import json
import stat
import threading
from pathlib import Path

import pytest

from agenthalt.journal import Journal
from agenthalt.scopes import Mode, Scope, Target
from agenthalt.store import (
    HaltLifecycle,
    HaltState,
    Store,
    StoreCorruptError,
    StoreUnavailableError,
)


def store(tmp_path: Path) -> Store:
    s = Store(tmp_path / ".agenthalt")
    s.ensure()
    return s


def halt(halt_id: str = "hlt_1", scope: str = "agent:bot", mode: Mode = Mode.KILL) -> HaltState:
    return HaltState.new(
        halt_id=halt_id, scope=Scope.parse(scope), mode=mode, actor="maya", reason="prod mutation"
    )


def test_ensure_creates_an_empty_generation_zero(tmp_path: Path) -> None:
    s = store(tmp_path)
    state = s.load()
    assert state.generation == 0 and state.halts == ()
    assert stat.S_IMODE(s.path.stat().st_mode) == 0o600
    assert stat.S_IMODE(s.dir.stat().st_mode) == 0o700
    s.ensure()  # idempotent
    assert s.load().generation == 0


def test_missing_store_is_unavailable(tmp_path: Path) -> None:
    with pytest.raises(StoreUnavailableError):
        Store(tmp_path / ".agenthalt").load()


def test_corrupt_store(tmp_path: Path) -> None:
    s = store(tmp_path)
    s.path.write_text("{not json", encoding="utf-8")
    with pytest.raises(StoreCorruptError):
        s.load()
    s.path.write_text(json.dumps({"schema": "agenthalt.store.v9"}), encoding="utf-8")
    with pytest.raises(StoreCorruptError):
        s.load()
    s.path.write_text(
        json.dumps({"schema": "agenthalt.store.v1", "generation": "x"}), encoding="utf-8"
    )
    with pytest.raises(StoreCorruptError):
        s.load()


def test_upsert_persists_across_restart(tmp_path: Path) -> None:
    s = store(tmp_path)
    s.upsert(halt(), action="raise", actor="maya")
    again = Store(tmp_path / ".agenthalt")  # a new process / restart
    state = again.load()
    assert state.generation == 1
    (h,) = state.halts
    assert h.halt_id == "hlt_1" and h.mode is Mode.KILL and str(h.scope) == "agent:bot"
    assert h.status is HaltLifecycle.PENDING


def test_every_mutation_is_journal_first(tmp_path: Path) -> None:
    s = store(tmp_path)
    s.upsert(halt(), action="raise", actor="maya")
    s.remove("hlt_1", actor="maya", reason="false alarm")
    entries = list(Journal(tmp_path / ".agenthalt").entries())
    assert [e["action"] for e in entries] == ["raise", "lift"]
    assert entries[0]["payload"]["store"]["op"] == "upsert"
    assert entries[0]["payload"]["store"]["generation"] == 1
    assert entries[1]["payload"]["store"] == {"op": "remove", "generation": 2, "halt_id": "hlt_1"}
    state = s.load()
    assert state.generation == 2 and state.halts == ()
    assert state.journal_seq == entries[1]["seq"] and state.journal_head == entries[1]["entry_hash"]


def test_reason_is_redacted_in_the_store(tmp_path: Path) -> None:
    s = store(tmp_path)
    h = HaltState.new(
        halt_id="hlt_1",
        scope=Scope.parse("all"),
        mode=Mode.KILL,
        actor="maya",
        reason="key AKIAIOSFODNN7EXAMPLE leaked",
    )
    s.upsert(h, action="raise", actor="maya")
    assert "AKIAIOSFODNN7EXAMPLE" not in s.path.read_text(encoding="utf-8")


def test_remove_unknown_halt(tmp_path: Path) -> None:
    with pytest.raises(KeyError):
        store(tmp_path).remove("hlt_nope", actor="maya", reason="x")


def test_scope_resolution(tmp_path: Path) -> None:
    s = store(tmp_path)
    s.upsert(halt("hlt_a", "agent:bot", Mode.PAUSE), action="raise", actor="maya")
    s.upsert(halt("hlt_b", "subtree:r1", Mode.KILL), action="raise", actor="maya")
    s.upsert(halt("hlt_c", "agent:other", Mode.KILL), action="raise", actor="maya")
    state = s.load()

    def ids(t: Target) -> list[str]:
        return sorted(h.halt_id for h in state.matching(t))

    assert ids(Target(agent="bot")) == ["hlt_a"]
    assert ids(Target(agent="bot", run="r5", ancestors=("r1",))) == ["hlt_a", "hlt_b"]
    assert ids(Target(agent="nobody")) == []


def test_upsert_replaces_same_halt_id(tmp_path: Path) -> None:
    s = store(tmp_path)
    h = halt()
    s.upsert(h, action="raise", actor="maya")
    s.upsert(h.with_status(HaltLifecycle.BLOCKING), action="execute", actor="haltd")
    (only,) = s.load().halts
    assert only.status is HaltLifecycle.BLOCKING


def test_rebuild_from_the_journal_matches(tmp_path: Path) -> None:
    s = store(tmp_path)
    s.upsert(halt("hlt_a"), action="raise", actor="maya")
    s.upsert(halt("hlt_b", "all", Mode.PAUSE), action="raise", actor="maya")
    s.remove("hlt_a", actor="maya", reason="done")
    before = s.load()
    s.path.unlink()
    rebuilt = s.rebuild()
    assert rebuilt == before
    assert s.load() == before


def test_writes_are_atomic_for_readers(tmp_path: Path) -> None:
    s = store(tmp_path)
    errors: list[Exception] = []
    stop = threading.Event()

    def reader() -> None:
        reader_store = Store(tmp_path / ".agenthalt")
        while not stop.is_set():
            try:
                reader_store.load()
            except Exception as exc:  # pragma: no cover - only on failure
                errors.append(exc)

    t = threading.Thread(target=reader)
    t.start()
    try:
        for i in range(60):
            s.upsert(halt(f"hlt_{i}"), action="raise", actor="maya")
    finally:
        stop.set()
        t.join()
    assert errors == []
    assert not list(s.dir.glob("*.tmp"))
    assert s.load().generation == 60


def test_halt_state_validation() -> None:
    with pytest.raises(ValueError):
        HaltState.new(
            halt_id="../x", scope=Scope.parse("all"), mode=Mode.KILL, actor="m", reason=None
        )
    with pytest.raises(ValueError):
        HaltState.new(
            halt_id="hlt_1", scope=Scope.parse("all"), mode=Mode.KILL, actor="", reason=None
        )


def test_new_halt_ids_are_unique_and_safe() -> None:
    from agenthalt.ids import new_halt_id, validate_id

    ids = {new_halt_id() for _ in range(500)}
    assert len(ids) == 500
    for i in ids:
        assert i.startswith("hlt_") and validate_id(i) == i


def test_replay_refuses_an_unknown_store_op(tmp_path: Path) -> None:
    s = store(tmp_path)
    s.upsert(halt(), action="raise", actor="maya")
    s.journal.append("finding", actor="x", payload={"store": {"op": "teleport", "generation": 9}})
    with pytest.raises(StoreCorruptError, match="unknown store op"):
        s.replay()
