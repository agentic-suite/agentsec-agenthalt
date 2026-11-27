"""The halt coordinator (M1 design §7): raise and lift, idempotency, the lifecycle.

Lifecycle (``HaltLifecycle``): ``pending → blocking → executing → finished``; ``lift`` removes a
halt from any of them. The *outcome* of a finished halt is a ``ReceiptStatus`` — a separate type,
never stored in the lifecycle field (PRD 15).

Recording happens first: the halt is in the store — so the choke already denies — from ``pending``
on (PRD 02: record before any layer acts). In M1 there are no executor layers, so ``executing``
attempts nothing and the outcome is honestly ``incomplete``: blocking is enforced at the runtime
choke, but nothing is suspended or revoked and there is no member list to confirm.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from agenthalt.exit_codes import ReceiptStatus
from agenthalt.ids import new_halt_id
from agenthalt.logs import bind_halt, get_logger
from agenthalt.scopes import Mode, Scope
from agenthalt.store import HaltLifecycle, HaltState, Store

__all__ = ["M1_LAYERS", "TRANSITIONS", "Coordinator", "LifecycleError", "RaiseResult"]

TRANSITIONS: dict[HaltLifecycle, frozenset[HaltLifecycle]] = {
    HaltLifecycle.PENDING: frozenset({HaltLifecycle.BLOCKING}),
    HaltLifecycle.BLOCKING: frozenset({HaltLifecycle.EXECUTING}),
    HaltLifecycle.EXECUTING: frozenset({HaltLifecycle.FINISHED}),
    HaltLifecycle.FINISHED: frozenset(),
    HaltLifecycle.LIFTED: frozenset(),  # terminal; reached only through lift()
}

# What each layer does for a halt in this build (M3-M4 replace "unsupported" with real executors).
M1_LAYERS: dict[str, str] = {
    "runtime_choke": "enforced",
    "gateway": "unsupported",
    "process": "unsupported",
    "credentials": "unsupported",
    "sandbox": "unsupported",
}

_log = get_logger("coordinator")


class LifecycleError(Exception):
    """An invalid lifecycle transition, or a transition on an unknown halt."""


@dataclass(frozen=True)
class RaiseResult:
    halt: HaltState
    created: bool
    outcome: ReceiptStatus | None = None
    layers: dict[str, str] = field(default_factory=dict)


@dataclass
class Coordinator:
    store: Store

    def new_halt(
        self, scope: Scope, mode: Mode, *, actor: str, reason: str | None, ttl_s: int | None = None
    ) -> HaltState:
        return HaltState.new(
            halt_id=new_halt_id(), scope=scope, mode=mode, actor=actor, reason=reason, ttl_s=ttl_s
        )

    def advance(
        self,
        halt_id: str,
        to: HaltLifecycle,
        *,
        actor: str,
        extra: dict[str, object] | None = None,
    ) -> HaltState:
        current = self.store.load().get(halt_id)
        if current is None:
            raise LifecycleError(f"no active halt {halt_id}")
        if to not in TRANSITIONS[current.status]:
            raise LifecycleError(f"{halt_id}: {current.status.value} -> {to.value} is not allowed")
        action = "complete" if to is HaltLifecycle.FINISHED else "execute"
        try:
            # re-checked under the store lock: a concurrent lift is never undone
            return self.store.transition(
                halt_id,
                expected=current.status,
                to=to,
                action=action,
                actor=actor,
                extra=dict(extra or {}),
            )
        except LookupError as exc:
            raise LifecycleError(str(exc)) from None

    def raise_halt(
        self,
        scope: Scope,
        mode: Mode,
        *,
        actor: str,
        reason: str | None,
        ttl_s: int | None = None,
    ) -> RaiseResult:
        halt, created = self.store.raise_or_get(
            self.new_halt(scope, mode, actor=actor, reason=reason, ttl_s=ttl_s), actor=actor
        )
        if not created:
            _log.info("halt.duplicate", extra={"fields": {"halt_id": halt.halt_id}})
            return RaiseResult(halt=halt, created=False)
        with bind_halt(halt.halt_id):
            _log.info("halt.raised", extra={"fields": {"scope": str(scope), "mode": mode.label}})
            self.advance(halt.halt_id, HaltLifecycle.BLOCKING, actor="agenthalt")
            self.advance(halt.halt_id, HaltLifecycle.EXECUTING, actor="agenthalt")
            outcome = ReceiptStatus.INCOMPLETE
            finished = self.advance(
                halt.halt_id,
                HaltLifecycle.FINISHED,
                actor="agenthalt",
                extra={"outcome": outcome.value, "layers": dict(M1_LAYERS)},
            )
            _log.info("halt.finished", extra={"fields": {"outcome": outcome.value}})
        return RaiseResult(halt=finished, created=True, outcome=outcome, layers=dict(M1_LAYERS))

    def lift(self, halt_id: str, *, actor: str, reason: str) -> None:
        if not reason or not reason.strip():
            raise ValueError("lifting a halt requires a reason")
        current = self.store.load().get(halt_id)
        if current is None:
            raise LookupError(f"no active halt {halt_id}")
        try:
            self.store.remove(
                halt_id, actor=actor, reason=reason, extra={"lifted_from": current.status.value}
            )
        except KeyError:
            raise LookupError(f"no active halt {halt_id}") from None
        _log.info("halt.lifted", extra={"fields": {"halt_id": halt_id}})
