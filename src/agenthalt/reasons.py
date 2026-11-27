"""Reason codes (M1 design §9, PRD 06 fail-closed contract).

Every deny the choke issues carries exactly one of these codes, and every fail-closed path has its
own code, so an operator (and a SIEM rule) can tell *why* an action was refused. Codes are
additive: never renamed, never reused.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass

__all__ = ["REGISTRY", "ReasonCode", "ReasonInfo"]


class ReasonCode(enum.Enum):
    HALTED = "halted"
    HALT_STORE_UNAVAILABLE = "halt_store_unavailable"
    STORE_INTEGRITY = "store_integrity"
    ADAPTER_FAILED = "adapter_failed"
    LINEAGE_GAP = "lineage_gap"
    LAYER_UNSUPPORTED = "layer_unsupported"


@dataclass(frozen=True)
class ReasonInfo:
    code: ReasonCode
    meaning: str
    denies: str  # "all" | "high" | "none"
    fail_closed: bool  # True when the code exists because something failed


REGISTRY: dict[ReasonCode, ReasonInfo] = {
    info.code: info
    for info in (
        ReasonInfo(ReasonCode.HALTED, "an active halt covers the target", "all", fail_closed=False),
        ReasonInfo(
            ReasonCode.HALT_STORE_UNAVAILABLE,
            "the halt store is missing or unreadable",
            "high",
            fail_closed=True,
        ),
        ReasonInfo(
            ReasonCode.STORE_INTEGRITY,
            "the halt store is corrupt, truncated, or inconsistent with the journal",
            "high",
            fail_closed=True,
        ),
        ReasonInfo(
            ReasonCode.ADAPTER_FAILED,
            "the choke or an adapter raised an error",
            "all",
            fail_closed=True,
        ),
        ReasonInfo(
            ReasonCode.LINEAGE_GAP,
            "the target's lineage could not be established",
            "high",
            fail_closed=True,
        ),
        ReasonInfo(
            ReasonCode.LAYER_UNSUPPORTED,
            "a composed layer is absent (reported, not a decision)",
            "none",
            fail_closed=False,
        ),
    )
}
