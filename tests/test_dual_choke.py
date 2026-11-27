"""1.3 Gateway choke interface (#415): the dual choke; agentgate reports `unsupported`, never skipped."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from agenthalt.choke import AgentgateStub, Decision, DualChoke, GatewayChoke, RuntimeChoke, Status
from agenthalt.reasons import ReasonCode
from agenthalt.scopes import Mode, Scope, Target
from agenthalt.store import HaltState, Store

BOT = Target(agent="bot")


def dual(tmp_path: Path, gateway: GatewayChoke | None = None) -> tuple[Store, DualChoke]:
    store = Store(tmp_path / ".agenthalt")
    store.ensure()
    runtime = RuntimeChoke(store, cache_ttl_s=2)
    return store, (DualChoke(runtime) if gateway is None else DualChoke(runtime, gateway))


def test_stub_reports_unsupported_fast() -> None:
    stub = AgentgateStub()
    assert stub.name == "agentgate" and stub.available() is False
    start = time.perf_counter()
    d = stub.check(BOT)
    assert (time.perf_counter() - start) * 1000 < 1  # PRD 39: absent layer answers in <= 1 ms
    assert (
        d.status == "unsupported"
        and d.layer == "gateway"
        and d.reason is ReasonCode.LAYER_UNSUPPORTED
    )
    assert not d.allow


def test_default_gateway_is_the_stub(tmp_path: Path) -> None:
    _, choke = dual(tmp_path)
    assert isinstance(choke.gateway, AgentgateStub)


def test_unsupported_gateway_is_reported_not_skipped(tmp_path: Path) -> None:
    _, choke = dual(tmp_path)
    d = choke.check(BOT)
    assert d.allow  # nothing halted; an unsupported gateway does not block
    assert d.layers == {"runtime": "allow", "gateway": "unsupported"}
    assert d.gateway.reason is ReasonCode.LAYER_UNSUPPORTED


def test_runtime_deny_wins(tmp_path: Path) -> None:
    store, choke = dual(tmp_path)
    store.upsert(
        HaltState.new(
            halt_id="hlt_1", scope=Scope.parse("agent:bot"), mode=Mode.KILL, actor="m", reason="r"
        ),
        action="raise",
        actor="m",
    )
    d = choke.check(BOT)
    assert not d.allow and d.reason is ReasonCode.HALTED
    assert d.layers == {"runtime": "deny", "gateway": "unsupported"}


@dataclass
class FakeGateway:
    verdict: Status | Literal["raise"]
    name: str = "fake"

    def available(self) -> bool:
        return True

    def check(self, target: Target) -> Decision:
        if self.verdict == "raise":
            raise RuntimeError("gateway down")
        return Decision(
            status=self.verdict,
            layer="gateway",
            reason=ReasonCode.HALTED if self.verdict == "deny" else None,
        )


def test_gateway_deny_wins(tmp_path: Path) -> None:
    _, choke = dual(tmp_path, FakeGateway("deny"))
    d = choke.check(BOT)
    assert not d.allow and d.reason is ReasonCode.HALTED


def test_both_allow(tmp_path: Path) -> None:
    _, choke = dual(tmp_path, FakeGateway("allow"))
    d = choke.check(BOT)
    assert d.allow and d.layers == {"runtime": "allow", "gateway": "allow"} and d.reason is None


def test_failing_gateway_adapter_denies(tmp_path: Path) -> None:
    _, choke = dual(tmp_path, FakeGateway("raise"))
    d = choke.check(BOT)
    assert not d.allow and d.gateway.reason is ReasonCode.ADAPTER_FAILED


def test_stub_satisfies_the_protocol() -> None:
    gateway: GatewayChoke = AgentgateStub()
    assert gateway.check(BOT).layer == "gateway"
