"""Scopes, targets and the mode ladder (M1 design §2, PRD 18).

A **scope** names what a halt covers; a **target** is the thing asking the choke for permission to
act. ``Scope.matches(target)`` is the only place coverage is decided.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Literal

from agenthalt.ids import validate_id

__all__ = ["SCOPE_KINDS", "Impact", "Mode", "Scope", "Target"]

Impact = Literal["high", "low"]

# kind -> whether it takes a value
SCOPE_KINDS: dict[str, bool] = {
    "all": False,
    "tenant": True,
    "agent": True,
    "subtree": True,
    "run": True,
    "session": True,
    "tool": True,
    "writes-disabled": False,
}


class Mode(enum.IntEnum):
    """The stop ladder: each rung is a superset of the one below (PRD 18)."""

    PAUSE = 1
    QUARANTINE = 2
    KILL = 3

    @property
    def label(self) -> str:
        return self.name.lower()

    @classmethod
    def parse(cls, text: str) -> Mode:
        try:
            return cls[text.upper()]
        except KeyError:
            raise ValueError(f"unknown mode: {text!r} (pause, quarantine or kill)") from None


@dataclass(frozen=True)
class Target:
    """What is asking to act. Unknown fields are ``None``; ``impact`` defaults to ``high``."""

    agent: str | None = None
    run: str | None = None
    session: str | None = None
    tenant: str | None = None
    ancestors: tuple[str, ...] = field(default_factory=tuple)
    tool: str | None = None
    writes: bool = False
    impact: Impact = "high"
    lineage_known: bool = True
    """False when the caller could not establish the target's lineage (M2 sets it)."""

    def __post_init__(self) -> None:
        for name in ("agent", "run", "session", "tenant", "tool"):
            value = getattr(self, name)
            if value is not None:
                validate_id(value, what=f"target.{name}")
        for ancestor in self.ancestors:
            validate_id(ancestor, what="target.ancestors")
        if self.impact not in ("high", "low"):
            raise ValueError(f"impact must be 'high' or 'low', got {self.impact!r}")


@dataclass(frozen=True)
class Scope:
    kind: str
    value: str | None = None

    @classmethod
    def parse(cls, text: str) -> Scope:
        kind, sep, value = text.partition(":")
        if kind not in SCOPE_KINDS:
            raise ValueError(f"unknown scope: {text!r}")
        if SCOPE_KINDS[kind]:
            if not sep or not value:
                raise ValueError(f"scope {kind!r} needs a value: {kind}:<id>")
            validate_id(value, what=f"scope {kind}")
            return cls(kind, value)
        if sep:
            raise ValueError(f"scope {kind!r} takes no value: {text!r}")
        return cls(kind)

    def __str__(self) -> str:
        return self.kind if self.value is None else f"{self.kind}:{self.value}"

    def matches(self, target: Target) -> bool:
        if self.kind == "all":
            return True
        if self.kind == "writes-disabled":
            return target.writes
        if self.kind == "subtree":
            return self.value == target.run or self.value in target.ancestors
        attribute = {
            "tenant": target.tenant,
            "agent": target.agent,
            "run": target.run,
            "session": target.session,
            "tool": target.tool,
        }[self.kind]
        return attribute is not None and attribute == self.value
