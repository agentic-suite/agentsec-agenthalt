"""Identifier validation (PRD 15: identifiers used in paths match ``^[a-zA-Z0-9_-]+$``)."""

from __future__ import annotations

import re

__all__ = ["ID_PATTERN", "validate_id"]

ID_PATTERN = re.compile(r"[a-zA-Z0-9_-]{1,128}")


def validate_id(value: str, *, what: str = "identifier") -> str:
    """Return ``value`` if it is a safe identifier, else raise ``ValueError``.

    Applied before any identifier reaches a filesystem path, a log line, or the journal.
    """
    if not isinstance(value, str) or not ID_PATTERN.fullmatch(value):
        raise ValueError(
            f"invalid identifier for {what}: {value!r} "
            "(allowed: letters, digits, '_' and '-', 1-128 chars)"
        )
    return value
