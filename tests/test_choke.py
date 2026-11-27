"""1.2 Runtime choke (#414): store read before every action, seconds-scale cache, fail-closed."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from agenthalt.choke import RuntimeChoke
from agenthalt.reasons import ReasonCode
from agenthalt.scopes import Mode, Scope, Target
from agenthalt.store import HaltState, Store, StoreState


def setup(tmp_path: Path, ttl: int = 2) -> tuple[Store, RuntimeChoke]:
    store = Store(tmp_path / ".agenthalt")
    store.ensure()
    return store, RuntimeChoke(store, cache_ttl_s=ttl)


def raise_halt(store: Store, scope: str, mode: Mode = Mode.KILL, halt_id: str = "hlt_1") -> None:
    store.upsert(
        HaltState.new(
            halt_id=halt_id, scope=Scope.parse(scope), mode=mode, actor="maya", reason="r"
        ),
        action="raise",
        actor="maya",
    )


BOT = Target(agent="bot", run="r1")


def test_allows_when_nothing_is_halted(tmp_path: Path) -> None:
    _, choke = setup(tmp_path)
    d = choke.check(BOT)
    assert d.allow and d.status == "allow" and d.reason is None and d.layer == "runtime"


def test_a_new_halt_is_visible_on_the_next_check_within_50ms(tmp_path: Path) -> None:
    store, choke = setup(tmp_path, ttl=59)  # long TTL: visibility must not depend on it
    assert choke.check(BOT).allow
    raise_halt(store, "agent:bot")
    start = time.perf_counter()
    d = choke.check(BOT)
    elapsed_ms = (time.perf_counter() - start) * 1000
    assert not d.allow and d.reason is ReasonCode.HALTED
    assert d.halt_id == "hlt_1" and d.mode is Mode.KILL
    assert elapsed_ms < 50 and d.latency_ms < 50


def test_check_latency_budget(tmp_path: Path) -> None:
    store, choke = setup(tmp_path)
    for i in range(50):
        raise_halt(store, f"agent:a{i}", halt_id=f"hlt_{i}")
    samples = []
    for _ in range(200):
        start = time.perf_counter()
        choke.check(BOT)
        samples.append((time.perf_counter() - start) * 1000)
    samples.sort()
    assert samples[int(len(samples) * 0.95)] < 50  # PRD 39: choke read <= 50 ms p95


def test_lift_is_visible_immediately(tmp_path: Path) -> None:
    store, choke = setup(tmp_path, ttl=59)
    raise_halt(store, "agent:bot")
    assert not choke.check(BOT).allow
    store.remove("hlt_1", actor="maya", reason="false alarm")
    assert choke.check(BOT).allow


def test_cache_reused_while_unchanged_and_younger_than_ttl(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, choke = setup(tmp_path, ttl=2)
    clock = [100.0]
    monkeypatch.setattr(choke, "_clock", lambda: clock[0])
    loads: list[int] = []
    real_load = store.load

    def counting_load() -> StoreState:
        loads.append(1)
        return real_load()

    monkeypatch.setattr(store, "load", counting_load)
    choke.check(BOT)
    choke.check(BOT)
    clock[0] += 1.9
    choke.check(BOT)
    assert len(loads) == 1  # unchanged file, inside the TTL: cached
    clock[0] += 0.2  # 2.1 s: TTL expired
    choke.check(BOT)
    assert len(loads) == 2


def test_ttl_zero_always_rereads(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store, choke = setup(tmp_path, ttl=0)
    loads: list[int] = []
    real_load = store.load

    def counting_load() -> StoreState:
        loads.append(1)
        return real_load()

    monkeypatch.setattr(store, "load", counting_load)
    for _ in range(3):
        choke.check(BOT)
    assert len(loads) == 3


def test_cache_ttl_is_seconds_never_minutes(tmp_path: Path) -> None:
    store = Store(tmp_path)
    with pytest.raises(ValueError):
        RuntimeChoke(store, cache_ttl_s=60)
    with pytest.raises(ValueError):
        RuntimeChoke(store, cache_ttl_s=-1)


def test_strictest_matching_mode_wins(tmp_path: Path) -> None:
    # DD-43: a narrow pause cannot weaken a fleet kill
    store, choke = setup(tmp_path)
    raise_halt(store, "all", Mode.KILL, "hlt_fleet")
    raise_halt(store, "agent:bot", Mode.PAUSE, "hlt_bot")
    d = choke.check(BOT)
    assert d.mode is Mode.KILL and d.halt_id == "hlt_fleet"
    raise_halt(store, "agent:x", Mode.KILL, "hlt_x")
    store.remove("hlt_fleet", actor="maya", reason="done")
    assert choke.check(BOT).mode is Mode.PAUSE


def test_a_halt_denies_low_impact_actions_too(tmp_path: Path) -> None:
    store, choke = setup(tmp_path)
    raise_halt(store, "agent:bot")
    assert not choke.check(Target(agent="bot", impact="low")).allow


def test_unreachable_store_denies_high_allows_low(tmp_path: Path) -> None:
    store, choke = setup(tmp_path)
    choke.check(BOT)  # warm the cache
    store.path.unlink()
    high = choke.check(BOT)
    assert not high.allow and high.reason is ReasonCode.HALT_STORE_UNAVAILABLE
    low = choke.check(Target(agent="bot", impact="low"))
    assert low.allow and low.reason is ReasonCode.HALT_STORE_UNAVAILABLE


def test_never_created_store_denies_high(tmp_path: Path) -> None:
    choke = RuntimeChoke(Store(tmp_path / ".agenthalt"), cache_ttl_s=2)
    assert choke.check(BOT).reason is ReasonCode.HALT_STORE_UNAVAILABLE


def test_corrupt_store_denies_high(tmp_path: Path) -> None:
    store, choke = setup(tmp_path)
    store.path.write_text("{garbage", encoding="utf-8")
    d = choke.check(BOT)
    assert not d.allow and d.reason is ReasonCode.STORE_INTEGRITY


def test_exception_inside_the_choke_denies(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store, choke = setup(tmp_path)

    def boom() -> None:
        raise RuntimeError("unexpected")

    monkeypatch.setattr(store, "load", boom)
    d = choke.check(BOT)
    assert not d.allow and d.reason is ReasonCode.ADAPTER_FAILED
    low = choke.check(Target(agent="bot", impact="low"))
    assert not low.allow  # a broken choke denies everything, not only high-impact
