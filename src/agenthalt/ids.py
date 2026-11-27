"""Identifier validation (PRD 15: identifiers used in paths match ``^[a-zA-Z0-9_-]+$``)."""

from __future__ import annotations

import re

__all__ = ["ID_PATTERN", "new_halt_id", "validate_id"]

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


_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def new_halt_id() -> str:
    """``hlt_`` + a ULID-style id: 48-bit millisecond time + 80 random bits, Crockford base32.

    Sortable by creation time, unique, and safe for paths (``^[a-zA-Z0-9_-]+$``).
    """
    import secrets
    import time

    value = (int(time.time() * 1000) << 80) | secrets.randbits(80)
    chars = []
    for _ in range(26):
        chars.append(_CROCKFORD[value & 31])
        value >>= 5
    return "hlt_" + "".join(reversed(chars))
