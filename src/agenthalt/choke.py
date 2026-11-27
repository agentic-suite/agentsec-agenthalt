"""The choke (R8, ADR-0002, M1 design §4-§5).

``RuntimeChoke.check(target)`` is what a runtime calls before every action. It ``stat()``s the store
on every call (microseconds), so a new halt is visible on the **next** check; the cache TTL —
seconds, never minutes — only bounds how long an *unchanged* copy is trusted. Every failure denies:
an unreachable or corrupt store denies high-impact actions, and an exception inside the choke denies
everything (ADR-0004).

The gateway half is a protocol; in Wave 0 the agentgate adapter is a stub that reports
``unsupported`` honestly (DD-18). ``DualChoke`` always reports both layers — an unsupported gateway
is visible, never silently skipped.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal, Protocol

from agenthalt.logs import get_logger
from agenthalt.reasons import ReasonCode
from agenthalt.scopes import Mode, Target
from agenthalt.store import Store, StoreCorruptError, StoreState, StoreUnavailableError

__all__ = [
    "AgentgateStub",
    "Decision",
    "DualChoke",
    "DualDecision",
    "GatewayChoke",
    "RuntimeChoke",
]

Status = Literal["allow", "deny", "unsupported"]
_log = get_logger("choke")


@dataclass(frozen=True)
class Decision:
    status: Status
    layer: str
    reason: ReasonCode | None = None
    halt_id: str | None = None
    mode: Mode | None = None
    latency_ms: float = 0.0

    @property
    def allow(self) -> bool:
        return self.status == "allow"


@dataclass
class _Cache:
    key: tuple[int, int, int]
    loaded_at: float
    state: StoreState


@dataclass
class RuntimeChoke:
    store: Store
    cache_ttl_s: int = 2
    _clock: Callable[[], float] = field(default=time.monotonic, repr=False)
    _cache: _Cache | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if not 0 <= self.cache_ttl_s <= 59:
            raise ValueError("the choke cache TTL is seconds, never minutes (0..59)")

    def _state(self) -> StoreState:
        try:
            st = os.stat(self.store.path)
        except FileNotFoundError:
            self._cache = None
            raise StoreUnavailableError(f"halt store not found: {self.store.path}") from None
        except OSError as exc:
            self._cache = None
            raise StoreUnavailableError(f"halt store unreachable: {exc}") from None
        key = (st.st_ino, st.st_mtime_ns, st.st_size)
        now = self._clock()
        cached = self._cache
        if cached is not None and cached.key == key and now - cached.loaded_at < self.cache_ttl_s:
            return cached.state
        state = self.store.load()
        self._cache = _Cache(key, now, state)
        return state

    def check(self, target: Target) -> Decision:
        start = time.perf_counter()

        def done(status: Status, reason: ReasonCode | None, **kw: object) -> Decision:
            return Decision(
                status=status,
                layer="runtime",
                reason=reason,
                latency_ms=(time.perf_counter() - start) * 1000,
                **kw,  # type: ignore[arg-type]
            )

        try:
            try:
                state = self._state()
            except (StoreUnavailableError, StoreCorruptError) as exc:
                code = (
                    ReasonCode.HALT_STORE_UNAVAILABLE
                    if isinstance(exc, StoreUnavailableError)
                    else ReasonCode.STORE_INTEGRITY
                )
                _log.warning(
                    "choke.fail_closed",
                    extra={"fields": {"reason": code.value, "detail": str(exc)}},
                )
                return done("allow" if target.impact == "low" else "deny", code)
            matches = state.matching(target)
            if not matches:
                if not target.lineage_known:
                    # Without lineage a subtree halt cannot be ruled out:
                    # deny high-impact actions (fail-closed).
                    return done(
                        "allow" if target.impact == "low" else "deny", ReasonCode.LINEAGE_GAP
                    )
                return done("allow", None)
            strictest = max(matches, key=lambda h: (h.mode, h.set_at))
            return done("deny", ReasonCode.HALTED, halt_id=strictest.halt_id, mode=strictest.mode)
        except Exception as exc:
            _log.error("choke.error", extra={"fields": {"error": repr(exc)}})
            return done("deny", ReasonCode.ADAPTER_FAILED)


class GatewayChoke(Protocol):
    @property
    def name(self) -> str: ...

    def available(self) -> bool: ...

    def check(self, target: Target) -> Decision: ...


@dataclass(frozen=True)
class AgentgateStub:
    """agentgate is Wave 1: until it ships, the gateway half reports ``unsupported`` (DD-18)."""

    name: str = "agentgate"

    def available(self) -> bool:
        return False

    def check(self, target: Target) -> Decision:
        start = time.perf_counter()
        return Decision(
            status="unsupported",
            layer="gateway",
            reason=ReasonCode.LAYER_UNSUPPORTED,
            latency_ms=(time.perf_counter() - start) * 1000,
        )


@dataclass(frozen=True)
class DualDecision:
    runtime: Decision
    gateway: Decision

    @property
    def allow(self) -> bool:
        return self.runtime.allow and self.gateway.status in ("allow", "unsupported")

    @property
    def layers(self) -> dict[str, Status]:
        return {"runtime": self.runtime.status, "gateway": self.gateway.status}

    @property
    def reason(self) -> ReasonCode | None:
        for decision in (self.runtime, self.gateway):
            if decision.status == "deny":
                return decision.reason
        return self.runtime.reason


@dataclass
class DualChoke:
    runtime: RuntimeChoke
    gateway: GatewayChoke = field(default_factory=AgentgateStub)

    def check(self, target: Target) -> DualDecision:
        runtime = self.runtime.check(target)
        try:
            gateway = self.gateway.check(target)
        except Exception as exc:
            _log.error("choke.gateway_error", extra={"fields": {"error": repr(exc)}})
            gateway = Decision(status="deny", layer="gateway", reason=ReasonCode.ADAPTER_FAILED)
        return DualDecision(runtime=runtime, gateway=gateway)
