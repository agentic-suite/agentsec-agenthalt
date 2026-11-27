"""The Tier-0 exit-code contract and receipt status precedence.

Exit codes are immutable once shipped (PRD 40): runbooks and scripts branch on them. When several
outcomes apply to one halt, the worst true status wins — ``failed`` > ``incomplete`` >
``partial-layer`` > ``complete`` (DD-39, ADR-0011) — and the exit code follows the same order.
Precedence is decided here, once; every caller uses these functions.
"""

from __future__ import annotations

import enum

__all__ = ["ExitCode", "ReceiptStatus", "exit_code_for", "status_for"]


class ExitCode(enum.IntEnum):
    """Process exit codes. Tier-0: never renumbered."""

    COMPLETE = 0
    """Halt complete — all members confirmed, zero survivors."""
    INCOMPLETE = 1
    """Survivors or unconfirmed members (the receipt says which)."""
    PARTIAL_LAYER = 2
    """Complete for reachable members; at least one layer was ``unsupported``."""
    FAILED = 3
    """Blocking was never established — use the manual fallback."""
    TRIGGER_REJECTED = 4
    """Auth, replay, scope ceiling, non-interactive panic key, or an unconfirmed fleet halt."""
    USAGE = 5
    """Usage or configuration error; nothing executed."""


class ReceiptStatus(enum.Enum):
    """Headline status of a receipt, declared from least to most severe."""

    COMPLETE = "complete"
    PARTIAL_LAYER = "partial-layer"
    INCOMPLETE = "incomplete"
    FAILED = "failed"

    @property
    def severity(self) -> int:
        return _SEVERITY[self]

    @classmethod
    def worst(cls, *statuses: ReceiptStatus) -> ReceiptStatus:
        """Return the most severe status (DD-39 precedence)."""
        if not statuses:
            raise ValueError("worst() needs at least one status")
        return max(statuses, key=lambda s: s.severity)


_SEVERITY = {status: rank for rank, status in enumerate(ReceiptStatus)}

_EXIT_FOR_STATUS = {
    ReceiptStatus.COMPLETE: ExitCode.COMPLETE,
    ReceiptStatus.PARTIAL_LAYER: ExitCode.PARTIAL_LAYER,
    ReceiptStatus.INCOMPLETE: ExitCode.INCOMPLETE,
    ReceiptStatus.FAILED: ExitCode.FAILED,
}


def exit_code_for(status: ReceiptStatus) -> ExitCode:
    """Map a receipt status to its exit code."""
    return _EXIT_FOR_STATUS[status]


def status_for(*, survivor: bool, unsupported_layer: bool, blocking_failed: bool) -> ReceiptStatus:
    """Derive the headline status from the three facts that decide it."""
    statuses = [ReceiptStatus.COMPLETE]
    if unsupported_layer:
        statuses.append(ReceiptStatus.PARTIAL_LAYER)
    if survivor:
        statuses.append(ReceiptStatus.INCOMPLETE)
    if blocking_failed:
        statuses.append(ReceiptStatus.FAILED)
    return ReceiptStatus.worst(*statuses)
