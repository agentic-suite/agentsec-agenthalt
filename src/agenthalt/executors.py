"""The executor adapter contract, registry and confirmation signing (M3 design §2, §5).

An adapter cuts what it is told to cut and reports what it observed. It holds no policy: it is never
given the halt store and does not choose targets, order or mode.
"""

from __future__ import annotations

import contextlib
import hashlib
import hmac
import json
import os
import secrets
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path
from typing import Any

from agenthalt.config import ConfigError
from agenthalt.logs import get_logger
from agenthalt.observe import Proc

__all__ = [
    "ENTRY_POINT_GROUP",
    "LAYERS",
    "PHASES",
    "STATUSES",
    "Confirmation",
    "Context",
    "ExecutorSigner",
    "Member",
    "Result",
    "load_adapters",
    "run_phase",
]

ENTRY_POINT_GROUP = "agenthalt.executors"
STATUSES = ("confirmed", "requested", "unsupported", "failed")
LAYERS = ("process", "sandbox")
PHASES = ("suspend", "block", "terminate")
SIGNED_BY = "agenthalt-executor"
GRACE_S = 2.0
"""How long past the deadline a phase may still run before it is abandoned."""
_log = get_logger("executors")


@dataclass(frozen=True)
class Member:
    """One process of a halted subtree."""

    node: str
    pid: int
    start: str
    run: str
    """The enrolled run it belongs to."""
    via: str = "lineage"
    cgroup: str | None = None
    """The run's own cgroup, if it has one."""
    uid: int | None = None
    """The ``run --user`` uid, from a root-owned record: the only other uid sudo may signal."""


@dataclass(frozen=True)
class Result:
    target: str
    status: str
    note: str = ""
    undo: Mapping[str, Any] | None = None
    """What ``release`` needs to reverse this cut; ``None`` when nothing was changed."""
    signed_by: str | None = None
    signature: str | None = None


@dataclass(frozen=True)
class Context:
    halt_id: str
    deadline: float
    """``time.monotonic()`` value after which nothing more may be reported ``confirmed``."""
    expand: Callable[[dict[int, Proc]], Sequence[Member]] = lambda procs: ()
    """Members that appeared since the last look (children forked while stopping)."""
    invoking_uid: int = field(default_factory=os.getuid)
    held: Callable[[], frozenset[tuple[Any, Any]]] = frozenset
    """What other halts hold. Read after observing: they record before they act."""
    record: Callable[[str, Mapping[str, Any]], None] = lambda layer, item: None
    """Call with the undo item *before* changing anything."""

    def expired(self) -> bool:
        return time.monotonic() >= self.deadline

    def remaining(self) -> float:
        return max(self.deadline - time.monotonic(), 0.001)


@dataclass(frozen=True)
class Confirmation:
    layer: str
    phase: str
    target: str
    status: str
    attestation: str
    at: str
    note: str = ""
    signed_by: str | None = None
    signature: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


# --------------------------------------------------------------------------- signing


def _payload(halt_id: str, item: Confirmation) -> bytes:
    body = {k: v for k, v in item.to_dict().items() if k not in ("signature", "signed_by")}
    return json.dumps({"halt_id": halt_id, **body}, sort_keys=True, separators=(",", ":")).encode()


class ExecutorSigner:
    """Self-attestation with a local executor key (provisional until WBS 4.6, DD-49)."""

    def __init__(self, home: Path) -> None:
        self.path = Path(home) / "keys" / "executor.key"

    def _key(self, *, create: bool) -> bytes:
        if create and not self.path.exists():
            self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            draft = self.path.with_name(f"{self.path.name}.{os.getpid()}.{secrets.token_hex(4)}")
            fd = os.open(draft, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w") as handle:
                handle.write(secrets.token_hex(32))
            try:  # appears complete or not at all; the first writer wins
                with contextlib.suppress(FileExistsError):
                    os.link(draft, self.path)
            finally:
                os.unlink(draft)
        key = bytes.fromhex(self.path.read_text().strip())
        if len(key) < 32:
            raise ValueError("executor key is too short")
        return key

    def sign(self, halt_id: str, item: Confirmation) -> tuple[str, str] | None:
        try:
            key = self._key(create=True)
        except (OSError, ValueError) as exc:
            _log.error("sign.unavailable", extra={"fields": {"error": str(exc)}})
            return None
        return SIGNED_BY, hmac.new(key, _payload(halt_id, item), hashlib.sha256).hexdigest()

    def verify(self, halt_id: str, item: Confirmation) -> bool:
        if item.signature is None:
            return False
        try:
            key = self._key(create=False)
        except (OSError, ValueError):
            return False
        good = hmac.new(key, _payload(halt_id, item), hashlib.sha256).hexdigest()
        return hmac.compare_digest(good, item.signature)


# --------------------------------------------------------------------------- registry


def _validate(name: str, adapter: Any) -> Any:
    problems = []
    if getattr(adapter, "name", None) != name:
        problems.append("its 'name' must match the registration")
    if getattr(adapter, "layer", None) not in LAYERS:
        problems.append(f"'layer' must be one of {', '.join(LAYERS)}")
    if not isinstance(getattr(adapter, "version", None), str):
        problems.append("'version' must be a string")
    if getattr(adapter, "attestation", None) not in ("self", "third_party"):
        problems.append("'attestation' must be 'self' or 'third_party'")
    if not any(callable(getattr(adapter, phase, None)) for phase in PHASES):
        problems.append(f"it implements none of {', '.join(PHASES)}")
    if not callable(getattr(adapter, "release", None)):
        problems.append("it has no 'release'")
    if problems:
        raise ConfigError(
            f"bad executor adapter {name!r}: {'; '.join(problems)}", key=name, source="executors"
        )
    return adapter


def load_adapters(
    builtins: Mapping[str, Callable[[], Any]],
    *,
    names: Iterable[str] | None = None,
    entry_points: Callable[[], Iterable[Any]] | None = None,
) -> dict[str, Any]:
    """``layer -> adapter``. A registered third-party adapter replaces the built-in of its layer."""
    if entry_points is None:

        def entry_points() -> Iterable[Any]:
            return metadata.entry_points(group=ENTRY_POINT_GROUP)

    external: dict[str, Any] = {}
    for point in entry_points():
        external[point.name] = point
    wanted = list(names) if names is not None else [*builtins, *external]
    chosen: dict[str, Any] = {}
    for name in sorted(wanted, key=lambda n: n in external):
        try:
            if name in external:
                adapter = external[name].load()()
            elif name in builtins:
                adapter = builtins[name]()
            else:
                raise ConfigError(f"unknown adapter {name!r}", key=name, source="executors")
        except ConfigError:
            raise
        except Exception as exc:
            raise ConfigError(
                f"executor adapter {name!r} failed to load: {exc}", key=name, source="executors"
            ) from None
        _validate(name, adapter)
        chosen[adapter.layer] = adapter
    return chosen


# --------------------------------------------------------------------------- running a phase


def run_phase(
    adapter: Any,
    phase: str,
    targets: Sequence[Any],
    names: Sequence[str],
    ctx: Context,
) -> list[Result]:
    """Call one phase and hold it to the contract. Never raises for an adapter's fault."""
    try:
        raw = list(getattr(adapter, phase)(targets, ctx))
        results: dict[str, Result] = {}
        extra: list[Result] = []
        for item in raw:
            if not isinstance(item, Result):
                raise TypeError(f"not a Result: {type(item).__name__}")
            if item.status not in STATUSES:
                item = replace(item, status="failed", note=f"unknown status {item.status!r}")
            if item.target in names:
                results[item.target] = item
            else:
                extra.append(item)
    except Exception as exc:
        _log.error("adapter.failed", extra={"fields": {"adapter": phase, "error": str(exc)}})
        return [Result(name, "failed", f"adapter error: {exc}") for name in names]
    missing = [Result(n, "requested", "no result reported") for n in names if n not in results]
    # a result for something that was not asked for (a child found while stopping) is kept
    # only when the adapter can say what it did to it
    found = [item for item in extra if item.note]
    return [*results.values(), *missing, *found]


def confirmation(
    halt_id: str,
    layer: str,
    phase: str,
    result: Result,
    *,
    attestation: str,
    signer: ExecutorSigner | None,
) -> Confirmation:
    """A signable confirmation. ``confirmed`` without a signature becomes ``requested``."""
    item = Confirmation(
        layer=layer,
        phase=phase,
        target=result.target,
        status=result.status,
        attestation=attestation,
        at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
        note=result.note,
    )
    if attestation == "third_party":
        signed = (
            (result.signed_by, result.signature) if result.signed_by and result.signature else None
        )
    else:
        signed = None
        with contextlib.suppress(AttributeError):
            signed = signer.sign(halt_id, item) if signer is not None else None
    if signed is None:
        if item.status != "confirmed":
            return item
        item = replace(item, status="requested", note=f"{item.note} (unsigned)".strip())
        return item
    return replace(item, signed_by=signed[0], signature=signed[1])
