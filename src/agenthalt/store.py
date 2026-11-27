"""The halt store (R8, M1 design §3) — the single source of stop truth.

``<home>/store/state.json`` holds only the **active** halts. It is a materialised view of the
journal: every mutation is **journal-first** (append the journal entry carrying the full halt state
and the next generation, then atomically replace the store file), so the store can always be
rebuilt from the journal and an out-of-band edit is detectable (DD-44).

A missing store file is *unavailable*, not empty: the choke cannot tell whether a halt is armed, so
it fails closed. ``Store.ensure()`` creates the empty store; the CLI calls it.
"""

from __future__ import annotations

import contextlib
import enum
import fcntl
import json
import os
from collections.abc import Iterator
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agenthalt.ids import validate_id
from agenthalt.journal import GENESIS, Journal
from agenthalt.redact import redact_text
from agenthalt.scopes import Mode, Scope, Target

__all__ = [
    "INTEGRITY_SIGNALS",
    "SCHEMA",
    "HaltLifecycle",
    "HaltState",
    "Store",
    "StoreCorruptError",
    "StoreError",
    "StoreHealth",
    "StoreState",
    "StoreUnavailableError",
]

SCHEMA = "agenthalt.store.v1"


class StoreError(Exception):
    """Base class for store failures. Every one of them makes the choke fail closed."""


class StoreUnavailableError(StoreError):
    """The store file is missing or cannot be read."""


class StoreCorruptError(StoreError):
    """The store file exists but is not a valid ``agenthalt.store.v1`` document."""


class HaltLifecycle(enum.Enum):
    """Where a halt is in its life. The *outcome* is a separate type (``ReceiptStatus``)."""

    PENDING = "pending"
    BLOCKING = "blocking"
    EXECUTING = "executing"
    FINISHED = "finished"
    LIFTED = "lifted"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


@dataclass(frozen=True)
class HaltState:
    halt_id: str
    scope: Scope
    mode: Mode
    status: HaltLifecycle
    actor: str
    reason: str | None
    set_at: str
    ttl_s: int | None = None

    def __post_init__(self) -> None:
        validate_id(self.halt_id, what="halt_id")
        if not self.actor:
            raise ValueError("a halt names its actor")

    @classmethod
    def new(
        cls,
        *,
        halt_id: str,
        scope: Scope,
        mode: Mode,
        actor: str,
        reason: str | None,
        ttl_s: int | None = None,
    ) -> HaltState:
        return cls(
            halt_id=halt_id,
            scope=scope,
            mode=mode,
            status=HaltLifecycle.PENDING,
            actor=actor,
            reason=redact_text(reason) if reason else reason,
            set_at=_now(),
            ttl_s=ttl_s,
        )

    def with_status(self, status: HaltLifecycle) -> HaltState:
        return replace(self, status=status)

    def to_dict(self) -> dict[str, Any]:
        return {
            "halt_id": self.halt_id,
            "scope": str(self.scope),
            "mode": self.mode.label,
            "status": self.status.value,
            "actor": self.actor,
            "reason": self.reason,
            "set_at": self.set_at,
            "ttl_s": self.ttl_s,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HaltState:
        return cls(
            halt_id=data["halt_id"],
            scope=Scope.parse(data["scope"]),
            mode=Mode.parse(data["mode"]),
            status=HaltLifecycle(data["status"]),
            actor=data["actor"],
            reason=data.get("reason"),
            set_at=data["set_at"],
            ttl_s=data.get("ttl_s"),
        )


@dataclass(frozen=True)
class StoreState:
    generation: int
    journal_seq: int
    journal_head: str
    halts: tuple[HaltState, ...]

    def matching(self, target: Target) -> list[HaltState]:
        return [h for h in self.halts if h.scope.matches(target)]

    def get(self, halt_id: str) -> HaltState | None:
        return next((h for h in self.halts if h.halt_id == halt_id), None)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "generation": self.generation,
            "journal_seq": self.journal_seq,
            "journal_head": self.journal_head,
            "halts": [h.to_dict() for h in self.halts],
        }

    @classmethod
    def from_dict(cls, data: Any) -> StoreState:
        if not isinstance(data, dict) or data.get("schema") != SCHEMA:
            raise StoreCorruptError(f"not an {SCHEMA} document")
        try:
            generation, seq = data["generation"], data["journal_seq"]
            if not all(isinstance(v, int) and not isinstance(v, bool) for v in (generation, seq)):
                raise TypeError("generation/journal_seq must be integers")
            return cls(
                generation=generation,
                journal_seq=seq,
                journal_head=str(data["journal_head"]),
                halts=tuple(HaltState.from_dict(h) for h in data["halts"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise StoreCorruptError(f"invalid store document: {exc}") from None


EMPTY = StoreState(generation=0, journal_seq=0, journal_head=GENESIS, halts=())

INTEGRITY_SIGNALS = ("unreachable", "truncated", "head_mismatch")


@dataclass(frozen=True)
class StoreHealth:
    """Store health: ``status`` is ok, unavailable or recovering; ``signal`` is an integrity signal.

    A signal is raised only when the journal says a halt is armed (or the journal itself is broken):
    a planned restart with nothing armed is a health event, not tampering.
    """

    status: str
    signal: str | None
    armed: bool
    detail: str


class Store:
    def __init__(self, home: Path, *, journal: Journal | None = None) -> None:
        self.home = Path(home)
        self.dir = self.home / "store"
        self.path = self.dir / "state.json"
        self.journal = journal if journal is not None else Journal(self.home)

    # ----------------------------------------------------------------------- reading

    def load(self) -> StoreState:
        try:
            raw = self.path.read_bytes()
        except FileNotFoundError:
            raise StoreUnavailableError(f"halt store not found: {self.path}") from None
        except OSError as exc:
            raise StoreUnavailableError(f"halt store unreadable: {exc}") from None
        try:
            data = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise StoreCorruptError(f"halt store is not valid JSON: {exc}") from None
        return StoreState.from_dict(data)

    # ----------------------------------------------------------------------- writing

    def _ensure_dirs(self) -> None:
        for directory in (self.home, self.dir):
            directory.mkdir(mode=0o700, parents=True, exist_ok=True)
            os.chmod(directory, 0o700)

    @contextlib.contextmanager
    def _locked(self) -> Iterator[None]:
        self._ensure_dirs()
        fd = os.open(self.dir / ".lock", os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    def _write(self, state: StoreState) -> None:
        """Atomic replace: readers see the old file or the new one, never a partial write."""
        tmp = self.dir / f"state.json.{os.getpid()}.tmp"
        data = json.dumps(state.to_dict(), sort_keys=True, indent=1).encode("utf-8") + b"\n"
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            os.write(fd, data)
            os.fsync(fd)
        finally:
            os.close(fd)
        os.replace(tmp, self.path)
        dir_fd = os.open(self.dir, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)

    def ensure(self) -> StoreState:
        """Create the empty store if none exists (no journal entry: nothing changed)."""
        with self._locked():
            if self.path.exists():
                return self.load()
            self._write(EMPTY)
            return EMPTY

    def _upsert_locked(
        self, state: StoreState, halt: HaltState, action: str, actor: str, extra: dict[str, Any]
    ) -> StoreState:
        generation = state.generation + 1
        entry = self.journal.append(
            action,
            actor=actor,
            halt_id=halt.halt_id,
            scope=str(halt.scope),
            mode=halt.mode.label,
            reason=halt.reason,
            payload={
                **extra,
                "store": {"op": "upsert", "generation": generation, "halt": halt.to_dict()},
            },
        )
        halts = (*(h for h in state.halts if h.halt_id != halt.halt_id), halt)
        new = StoreState(generation, entry["seq"], entry["entry_hash"], halts)
        self._write(new)
        return new

    def upsert(
        self, halt: HaltState, *, action: str, actor: str, extra: dict[str, Any] | None = None
    ) -> StoreState:
        """Insert or replace one halt, journal-first."""
        with self._locked():
            return self._upsert_locked(self.load(), halt, action, actor, extra or {})

    def transition(
        self,
        halt_id: str,
        *,
        expected: HaltLifecycle,
        to: HaltLifecycle,
        action: str,
        actor: str,
        extra: dict[str, Any] | None = None,
    ) -> HaltState:
        """Compare-and-set a halt's lifecycle under the lock.

        Raises ``LookupError`` if the halt is no longer active (e.g. lifted concurrently) or is not
        in ``expected`` — so a stale writer can never resurrect a lifted halt or skip a state.
        """
        with self._locked():
            state = self.load()
            current = state.get(halt_id)
            if current is None:
                raise LookupError(f"no active halt {halt_id}")
            if current.status is not expected:
                raise LookupError(f"{halt_id} is {current.status.value}, expected {expected.value}")
            moved = current.with_status(to)
            self._upsert_locked(state, moved, action, actor, extra or {})
            return moved

    def raise_or_get(self, halt: HaltState, *, actor: str) -> tuple[HaltState, bool]:
        """Atomically insert ``halt`` unless an active halt has the same scope and mode (DD-27).

        Returns ``(halt, True)`` when inserted, or ``(existing, False)`` for a duplicate — journaled
        as a ``duplicate_raise`` finding so it stays visible. Check and insert happen under one
        lock, so concurrent duplicate raises create exactly one halt.
        """
        with self._locked():
            state = self.load()
            existing = next(
                (h for h in state.halts if h.scope == halt.scope and h.mode == halt.mode), None
            )
            if existing is not None:
                self.journal.append(
                    "finding",
                    actor=actor,
                    halt_id=existing.halt_id,
                    scope=str(existing.scope),
                    mode=existing.mode.label,
                    reason=halt.reason,
                    payload={"finding": "duplicate_raise"},
                )
                return existing, False
            self._upsert_locked(state, halt, "raise", actor, {})
            return halt, True

    def remove(
        self, halt_id: str, *, actor: str, reason: str, extra: dict[str, Any] | None = None
    ) -> StoreState:
        """Remove (lift) one active halt, journal-first. Raises ``KeyError`` if it is not active."""
        with self._locked():
            state = self.load()
            current = state.get(halt_id)
            if current is None:
                raise KeyError(halt_id)
            generation = state.generation + 1
            entry = self.journal.append(
                "lift",
                actor=actor,
                halt_id=halt_id,
                scope=str(current.scope),
                mode=current.mode.label,
                reason=reason,
                payload={
                    **(extra or {}),
                    "store": {"op": "remove", "generation": generation, "halt_id": halt_id},
                },
            )
            halts = tuple(h for h in state.halts if h.halt_id != halt_id)
            new = StoreState(generation, entry["seq"], entry["entry_hash"], halts)
            self._write(new)
            return new

    # ----------------------------------------------------------------------- rebuild

    def replay(self) -> StoreState:
        """Derive the store state from the journal alone (no writes)."""
        return self._history()[-1]

    def _history(self) -> list[StoreState]:
        """The store state after every store-changing journal entry; index == generation."""
        history = [EMPTY]
        state = EMPTY
        for entry in self.journal.entries():
            op = (entry.get("payload") or {}).get("store")
            if not isinstance(op, dict):
                continue
            halts = state.halts
            if op["op"] == "upsert":
                halt = HaltState.from_dict(op["halt"])
                halts = (*(h for h in halts if h.halt_id != halt.halt_id), halt)
            elif op["op"] == "remove":
                halts = tuple(h for h in halts if h.halt_id != op["halt_id"])
            else:
                # Skipping an unknown op could silently drop a halt from the rebuilt state.
                raise StoreCorruptError(
                    f"journal seq {entry['seq']}: unknown store op {op['op']!r}"
                )
            state = StoreState(op["generation"], entry["seq"], entry["entry_hash"], halts)
            history.append(state)
        return history

    # ----------------------------------------------------------------------- health

    def health(self) -> StoreHealth:
        """Health + the integrity signal (M1 design §6).

        The signal is the input contract for the 8.2 ``tamper_store`` trigger.

        "Armed" comes from the **journal**, so deleting or editing the store cannot hide a halt.
        """
        verified = self.journal.verify()
        if not verified.ok:
            return StoreHealth(
                "unavailable",
                "head_mismatch",
                True,
                f"journal does not verify ({verified.describe()}); treating the fleet as armed",
            )
        try:
            history = self._history()
        except StoreCorruptError as exc:
            return StoreHealth(
                "unavailable", "head_mismatch", True, f"journal cannot be replayed: {exc}"
            )
        expected = history[-1]
        is_armed = bool(expected.halts)
        try:
            actual = self.load()
        except StoreUnavailableError as exc:
            return StoreHealth(
                "unavailable", "unreachable" if is_armed else None, is_armed, str(exc)
            )
        except StoreCorruptError as exc:
            return StoreHealth("unavailable", "truncated" if is_armed else None, is_armed, str(exc))
        if actual == expected:
            return StoreHealth("ok", None, is_armed, f"generation {actual.generation}")
        if actual.generation < expected.generation and history[actual.generation] == actual:
            return StoreHealth(
                "recovering",
                None,
                is_armed,
                f"store at generation {actual.generation}, journal at {expected.generation}: "
                "rebuild from the journal",
            )
        return StoreHealth(
            "unavailable",
            "head_mismatch",
            is_armed,
            f"store generation {actual.generation} does not match the journal "
            f"(expected {expected.generation}): edited outside agenthalt",
        )

    def rebuild(self) -> StoreState:
        """Rewrite the store from the journal (recovery after a crash between journal and store)."""
        with self._locked():
            state = self.replay()
            self._write(state)
            return state
