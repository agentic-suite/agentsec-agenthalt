"""1.6 Store health + the integrity signal (#418) — the input contract for 8.2 `tamper_store`."""

from __future__ import annotations

import json
from pathlib import Path

from agenthalt.coordinator import Coordinator
from agenthalt.scopes import Mode, Scope
from agenthalt.store import HaltState, Store


def armed(tmp_path: Path) -> Store:
    store = Store(tmp_path / ".agenthalt")
    store.ensure()
    Coordinator(store).raise_halt(Scope.parse("agent:bot"), Mode.KILL, actor="m", reason="r")
    return store


def test_healthy_store(tmp_path: Path) -> None:
    h = armed(tmp_path).health()
    assert h.status == "ok" and h.signal is None and h.armed


def test_fresh_store_is_healthy_and_unarmed(tmp_path: Path) -> None:
    store = Store(tmp_path / ".agenthalt")
    store.ensure()
    h = store.health()
    assert h.status == "ok" and h.signal is None and not h.armed


def test_restart_with_nothing_armed_is_a_health_event_not_tamper(tmp_path: Path) -> None:
    store = Store(tmp_path / ".agenthalt")
    store.ensure()
    store.path.unlink()  # planned restart / not yet created
    h = store.health()
    assert h.status == "unavailable" and h.signal is None and not h.armed


def test_missing_store_while_armed_signals_unreachable(tmp_path: Path) -> None:
    store = armed(tmp_path)
    store.path.unlink()
    h = store.health()
    assert h.status == "unavailable" and h.signal == "unreachable" and h.armed


def test_truncation_while_armed_signals_truncated(tmp_path: Path) -> None:
    store = armed(tmp_path)
    store.path.write_bytes(store.path.read_bytes()[:40])
    h = store.health()
    assert h.signal == "truncated" and h.armed


def test_corrupt_store_with_nothing_armed_has_no_signal(tmp_path: Path) -> None:
    store = Store(tmp_path / ".agenthalt")
    store.ensure()
    store.path.write_text("{garbage", encoding="utf-8")
    h = store.health()
    assert h.status == "unavailable" and h.signal is None


def test_crash_between_journal_and_store_is_recovery(tmp_path: Path) -> None:
    store = armed(tmp_path)
    state = store.load()
    # simulate the crash: the journal entry lands, the store write never happens
    halt = HaltState.new(
        halt_id="hlt_crash", scope=Scope.parse("all"), mode=Mode.PAUSE, actor="m", reason="r"
    )
    store.journal.append(
        "raise",
        actor="m",
        halt_id="hlt_crash",
        scope="all",
        mode="pause",
        payload={
            "store": {"op": "upsert", "generation": state.generation + 1, "halt": halt.to_dict()}
        },
    )
    h = store.health()
    assert h.status == "recovering" and h.signal is None
    store.rebuild()
    after = store.health()
    assert after.status == "ok" and after.signal is None
    assert {x.halt_id for x in store.load().halts} >= {"hlt_crash"}


def test_out_of_band_edit_signals_head_mismatch(tmp_path: Path) -> None:
    # the agent deletes its own halt from the store file (same OS user, DD-44)
    store = armed(tmp_path)
    data = json.loads(store.path.read_text())
    data["halts"] = []
    store.path.write_text(json.dumps(data), encoding="utf-8")
    h = store.health()
    assert h.signal == "head_mismatch" and h.armed  # armed comes from the journal, not the store


def test_forged_generation_ahead_signals_head_mismatch(tmp_path: Path) -> None:
    store = armed(tmp_path)
    data = json.loads(store.path.read_text())
    data["generation"] += 5
    store.path.write_text(json.dumps(data), encoding="utf-8")
    assert store.health().signal == "head_mismatch"


def test_broken_journal_is_reported(tmp_path: Path) -> None:
    store = armed(tmp_path)
    seg = store.journal.dir / "seg-000001.jsonl"
    seg.write_text(seg.read_text().replace('"actor":"m"', '"actor":"x"', 1))
    h = store.health()
    assert h.signal == "head_mismatch" and h.status == "unavailable" and h.armed
    assert "journal" in h.detail


def test_signal_values_are_the_documented_contract() -> None:
    from agenthalt.store import INTEGRITY_SIGNALS

    assert INTEGRITY_SIGNALS == ("unreachable", "truncated", "head_mismatch")


def test_unreplayable_journal_signals_head_mismatch(tmp_path: Path) -> None:
    store = armed(tmp_path)
    store.journal.append(
        "finding", actor="x", payload={"store": {"op": "teleport", "generation": 9}}
    )
    h = store.health()
    assert h.signal == "head_mismatch" and h.armed and "cannot be replayed" in h.detail
