"""The halt coordinator (M1 design §7): raise and lift, idempotency, the lifecycle.

Lifecycle (``HaltLifecycle``): ``pending → blocking → executing → finished``; ``lift`` removes a
halt from any of them. The *outcome* of a finished halt is a ``ReceiptStatus`` — a separate type,
never stored in the lifecycle field (PRD 15).

Recording happens first: the halt is in the store — so the choke already denies — from ``pending``
on (PRD 02: record before any layer acts). With a ``Containment`` the executing step cuts the
subtree (M3 design §3) and records what was observed; without one nothing is suspended and the
outcome is honestly ``incomplete``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agenthalt.containment import Containment, Cut
from agenthalt.executors import Result
from agenthalt.exit_codes import ReceiptStatus
from agenthalt.ids import new_halt_id
from agenthalt.journal import JournalBusyError, JournalError
from agenthalt.logs import bind_halt, get_logger
from agenthalt.scopes import Mode, Scope
from agenthalt.store import HaltLifecycle, HaltState, Store, StoreBusyError, StoreError

__all__ = [
    "M1_LAYERS",
    "TRANSITIONS",
    "Coordinator",
    "LifecycleError",
    "LiftResult",
    "RaiseResult",
]

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
    cut: Cut | None = None


@dataclass(frozen=True)
class LiftResult:
    released: tuple[Result, ...] = ()
    retried: bool = False
    """The halt had already been lifted; this retried what could not be released then."""


@dataclass
class Coordinator:
    store: Store
    containment: Containment | None = None
    """Executors are explicit: without them nothing is ever signalled."""

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
        wanted = self.new_halt(scope, mode, actor=actor, reason=reason, ttl_s=ttl_s)
        try:
            halt, created = self.store.raise_or_get(wanted, actor=actor)
        except (StoreBusyError, JournalBusyError) as exc:
            if self.containment is None:
                raise
            return self._cut_unblocked(wanted, exc)
        if self.containment is not None:
            return self._execute(halt, created)
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

    # ----------------------------------------------------------------------- execution

    def executions(self, halt_id: str) -> list[dict[str, Any]]:
        """Every recorded execution of a halt, oldest first."""
        return [
            e["payload"]["execution"]
            for e in self.store.journal.entries(halt_id=halt_id)
            if isinstance(e.get("payload"), dict) and "execution" in e["payload"]
        ]

    def _cut_unblocked(self, halt: HaltState, why: Exception) -> RaiseResult:
        """Someone is sitting on a state lock, perhaps the agent itself. The block cannot be
        written, so the outcome is ``failed``, but the processes are cut all the same."""
        if self.containment is None:  # pragma: no cover - the caller checked
            raise LifecycleError("no executors to cut with")
        _log.error("halt.unblocked", extra={"fields": {"error": str(why)}})
        cut = self.containment.cut(halt)
        cut.complete, cut.reason = False, f"block not established: {why}"
        layers = {**cut.layers(), "runtime_choke": "not established"}
        return RaiseResult(halt, True, ReceiptStatus.FAILED, layers, cut)

    def _execute(self, halt: HaltState, created: bool) -> RaiseResult:
        """Cut the subtree. Re-raising an active halt cuts again under the same id (DD-27)."""
        containment = self.containment
        if containment is None:  # pragma: no cover - the caller checked
            raise LifecycleError("no executors to cut with")
        with bind_halt(halt.halt_id):
            _log.info(
                "halt.raised" if created else "halt.duplicate",
                extra={"fields": {"scope": str(halt.scope), "mode": halt.mode.label}},
            )
            for step in (HaltLifecycle.BLOCKING, HaltLifecycle.EXECUTING):
                halt = self._step(halt, step)
            # past this point the block is established: bookkeeping trouble never stops the cut
            cut = containment.cut(halt)
            outcome, layers = cut.outcome(), cut.layers()
            try:
                self.store.journal.append(
                    "execute",
                    actor="agenthalt",
                    halt_id=halt.halt_id,
                    scope=str(halt.scope),
                    mode=halt.mode.label,
                    payload={"execution": {**cut.to_dict(), "outcome": outcome.value}},
                )
            except (JournalError, OSError) as exc:
                cut.complete = False
                cut.reason = f"the cut could not be journaled ({exc})"
                outcome = cut.outcome()
                _log.error("halt.unrecorded", extra={"fields": {"error": str(exc)}})
            halt = self._step(
                halt, HaltLifecycle.FINISHED, {"outcome": outcome.value, "layers": layers}
            )
            if self._lifted(halt.halt_id):
                # lifted while we were cutting: do not leave things frozen behind it
                containment.release(halt, self.store.load().halts, everything=True)
                cut.complete, cut.reason = False, "lifted while it was still cutting"
                outcome = cut.outcome()
            _log.info("halt.finished", extra={"fields": {"outcome": outcome.value}})
        return RaiseResult(halt=halt, created=created, outcome=outcome, layers=layers, cut=cut)

    def _step(
        self, halt: HaltState, to: HaltLifecycle, extra: dict[str, object] | None = None
    ) -> HaltState:
        """Advance if the lifecycle is exactly one step behind; otherwise leave it."""
        try:
            current = self.store.load().get(halt.halt_id)
            if current is None or to not in TRANSITIONS[current.status]:
                return current or halt
            return self.advance(halt.halt_id, to, actor="agenthalt", extra=extra)
        except (LifecycleError, StoreError, JournalError, OSError) as exc:
            _log.error("halt.lifecycle", extra={"fields": {"error": str(exc)}})
            return halt

    def _lifted(self, halt_id: str) -> bool:
        try:
            return self.store.load().get(halt_id) is None
        except StoreError:
            return False

    def lift(self, halt_id: str, *, actor: str, reason: str) -> LiftResult:
        if not reason or not reason.strip():
            raise ValueError("lifting a halt requires a reason")
        current = self.store.load().get(halt_id)
        if current is None:
            return self._retry_release(halt_id)
        try:
            self.store.remove(
                halt_id, actor=actor, reason=reason, extra={"lifted_from": current.status.value}
            )
        except KeyError:
            raise LookupError(f"no active halt {halt_id}") from None
        _log.info("halt.lifted", extra={"fields": {"halt_id": halt_id}})
        if self.containment is None:
            return LiftResult()
        return LiftResult(self._release(current))

    def _release(self, halt: HaltState) -> tuple[Result, ...]:
        if self.containment is None:  # pragma: no cover - the callers checked
            return ()
        try:
            return tuple(self.containment.release(halt, self.store.load().halts))
        except Exception as exc:  # the halt is gone by now: say what is left, do not crash
            _log.error("lift.release", extra={"fields": {"error": str(exc)}})
            return (Result("release", "failed", str(exc)),)

    def _retry_release(self, halt_id: str) -> LiftResult:
        if self.containment is not None:
            record = self.containment.cutlog.read(halt_id)
            if record and record.halt is not None:
                try:
                    halt = HaltState.from_dict(record.halt)
                except (KeyError, TypeError, ValueError):
                    pass
                else:
                    if halt.halt_id == halt_id:
                        return LiftResult(self._release(halt), retried=True)
        raise LookupError(f"no active halt {halt_id}")
