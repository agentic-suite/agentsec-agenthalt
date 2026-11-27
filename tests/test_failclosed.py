"""1.4 Fail-closed semantics + reason codes (#416): every failure path denies, each with a distinct code."""

from __future__ import annotations

import json
import os
import random
from collections.abc import Callable
from pathlib import Path

import pytest

from agenthalt.choke import DualChoke, RuntimeChoke
from agenthalt.reasons import REGISTRY, ReasonCode
from agenthalt.scopes import Target
from agenthalt.store import Store

HIGH = Target(agent="bot", run="r1")
LOW = Target(agent="bot", run="r1", impact="low")


def fresh(tmp_path: Path) -> tuple[Store, RuntimeChoke]:
    store = Store(tmp_path / ".agenthalt")
    store.ensure()
    return store, RuntimeChoke(store, cache_ttl_s=0)


def test_registry_documents_every_code_once() -> None:
    assert set(REGISTRY) == set(ReasonCode)
    assert len({c.value for c in ReasonCode}) == len(ReasonCode)
    for info in REGISTRY.values():
        assert info.meaning and info.denies in ("all", "high", "none")


def test_fail_closed_codes_are_distinct_and_deny() -> None:
    fail_closed = [i for i in REGISTRY.values() if i.fail_closed]
    assert {i.code for i in fail_closed} == {
        ReasonCode.HALT_STORE_UNAVAILABLE,
        ReasonCode.STORE_INTEGRITY,
        ReasonCode.ADAPTER_FAILED,
        ReasonCode.LINEAGE_GAP,
    }
    assert all(i.denies in ("all", "high") for i in fail_closed)


def _missing(s: Store) -> None:
    s.path.unlink()


def _empty(s: Store) -> None:
    s.path.write_bytes(b"")


def _truncated(s: Store) -> None:
    s.path.write_bytes(s.path.read_bytes()[:10])


def _not_json(s: Store) -> None:
    s.path.write_text("{not json", encoding="utf-8")


def _not_utf8(s: Store) -> None:
    s.path.write_bytes(b"\xff\xfe\x00")


def _wrong_schema(s: Store) -> None:
    s.path.write_text(json.dumps({"schema": "agenthalt.store.v0"}), encoding="utf-8")


def _array(s: Store) -> None:
    s.path.write_text("[]", encoding="utf-8")


def _bad_generation(s: Store) -> None:
    data = json.loads(s.path.read_text())
    data["generation"] = True
    s.path.write_text(json.dumps(data), encoding="utf-8")


def _missing_field(s: Store) -> None:
    data = json.loads(s.path.read_text())
    del data["halts"]
    s.path.write_text(json.dumps(data), encoding="utf-8")


def _bad_halt(s: Store) -> None:
    data = json.loads(s.path.read_text())
    data["halts"] = [
        {
            "halt_id": "hlt_1",
            "scope": "galaxy:far",
            "mode": "kill",
            "status": "pending",
            "actor": "m",
            "set_at": "x",
        }
    ]
    s.path.write_text(json.dumps(data), encoding="utf-8")


def _bad_mode(s: Store) -> None:
    data = json.loads(s.path.read_text())
    data["halts"] = [
        {
            "halt_id": "hlt_1",
            "scope": "all",
            "mode": "nuke",
            "status": "pending",
            "actor": "m",
            "set_at": "x",
        }
    ]
    s.path.write_text(json.dumps(data), encoding="utf-8")


def _unreadable(s: Store) -> None:
    os.chmod(s.path, 0o000)


def _dir_is_a_file(s: Store) -> None:
    s.path.unlink()
    s.path.mkdir()


INJECTIONS: dict[str, tuple[Callable[[Store], None], ReasonCode]] = {
    "missing": (_missing, ReasonCode.HALT_STORE_UNAVAILABLE),
    "unreadable": (_unreadable, ReasonCode.HALT_STORE_UNAVAILABLE),
    "path is a directory": (_dir_is_a_file, ReasonCode.HALT_STORE_UNAVAILABLE),
    "empty": (_empty, ReasonCode.STORE_INTEGRITY),
    "truncated": (_truncated, ReasonCode.STORE_INTEGRITY),
    "not json": (_not_json, ReasonCode.STORE_INTEGRITY),
    "not utf-8": (_not_utf8, ReasonCode.STORE_INTEGRITY),
    "wrong schema": (_wrong_schema, ReasonCode.STORE_INTEGRITY),
    "array": (_array, ReasonCode.STORE_INTEGRITY),
    "bad generation": (_bad_generation, ReasonCode.STORE_INTEGRITY),
    "missing field": (_missing_field, ReasonCode.STORE_INTEGRITY),
    "bad halt scope": (_bad_halt, ReasonCode.STORE_INTEGRITY),
    "bad halt mode": (_bad_mode, ReasonCode.STORE_INTEGRITY),
}


@pytest.mark.parametrize("name", sorted(INJECTIONS))
def test_every_store_failure_denies_high_impact(tmp_path: Path, name: str) -> None:
    store, choke = fresh(tmp_path)
    inject, expected = INJECTIONS[name]
    if name == "unreadable" and os.geteuid() == 0:
        pytest.skip("root reads 0000 files")
    inject(store)
    try:
        high = choke.check(HIGH)
        assert not high.allow and high.reason is expected, (name, high)
        low = choke.check(LOW)
        assert low.allow and low.reason is expected  # read-only work continues, flagged
        dual = DualChoke(choke).check(HIGH)
        assert not dual.allow and dual.reason is expected
    finally:
        if store.path.is_file():
            os.chmod(store.path, 0o600)


def test_fuzzed_store_bytes_never_allow_high_impact(tmp_path: Path) -> None:
    store, choke = fresh(tmp_path)
    good = store.path.read_bytes()
    rng = random.Random(20261127)
    for i in range(300):
        data = bytearray(good)
        for _ in range(rng.randint(1, 8)):
            if data and rng.random() < 0.7:
                data[rng.randrange(len(data))] = rng.randrange(256)
            elif data:
                del data[rng.randrange(len(data)) :]
        store.path.write_bytes(bytes(data))
        d = choke.check(HIGH)
        if d.allow:
            # a mutation that still parses as a valid empty store is the only way to allow
            assert store.load().halts == (), i
        else:
            assert d.reason in (ReasonCode.STORE_INTEGRITY, ReasonCode.HALT_STORE_UNAVAILABLE), (
                i,
                d,
            )


@pytest.mark.parametrize("exc", [RuntimeError, KeyError, MemoryError, ValueError, OSError])
def test_any_exception_denies_everything(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, exc: type[BaseException]
) -> None:
    store, choke = fresh(tmp_path)

    def boom() -> None:
        raise exc("injected")

    monkeypatch.setattr(store, "load", boom)
    for target in (HIGH, LOW):
        d = choke.check(target)
        if exc is OSError:
            # OSError from load() is an I/O failure of the store itself
            assert not d.allow or target.impact == "low"
        else:
            assert not d.allow and d.reason is ReasonCode.ADAPTER_FAILED


def test_stat_failure_denies(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _, choke = fresh(tmp_path)
    choke.check(HIGH)

    def bad_stat(path: object) -> os.stat_result:
        raise PermissionError("denied")

    monkeypatch.setattr("agenthalt.choke.os.stat", bad_stat)
    d = choke.check(HIGH)
    assert not d.allow and d.reason is ReasonCode.HALT_STORE_UNAVAILABLE


def test_lineage_gap_denies_high_impact(tmp_path: Path) -> None:
    _, choke = fresh(tmp_path)
    gap = Target(agent="bot", run="r9", lineage_known=False)
    d = choke.check(gap)
    assert not d.allow and d.reason is ReasonCode.LINEAGE_GAP
    low = choke.check(Target(agent="bot", run="r9", lineage_known=False, impact="low"))
    assert low.allow and low.reason is ReasonCode.LINEAGE_GAP


def test_an_active_halt_beats_a_lineage_gap(tmp_path: Path) -> None:
    from agenthalt.scopes import Mode, Scope
    from agenthalt.store import HaltState

    store, choke = fresh(tmp_path)
    store.upsert(
        HaltState.new(
            halt_id="hlt_1", scope=Scope.parse("agent:bot"), mode=Mode.KILL, actor="m", reason="r"
        ),
        action="raise",
        actor="m",
    )
    d = choke.check(Target(agent="bot", lineage_known=False, impact="low"))
    assert not d.allow and d.reason is ReasonCode.HALTED
