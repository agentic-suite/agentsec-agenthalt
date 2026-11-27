"""Secret redaction (PRD 06, PRD 38): a forensic record is not a secrets dump.

Known secret shapes are replaced with typed placeholders ``secret:<kind>[redacted]`` so the record
keeps its forensic value (*what kind* of secret was there) without the secret itself. Used by the
journal (``reason``/``payload``) and the structured logger in M0, and by the evidence pipeline
in M5.
"""

from __future__ import annotations

import re
from typing import Any

__all__ = ["SECRET_KEY_NAMES", "placeholder", "redact_text", "redact_value"]


def placeholder(kind: str) -> str:
    return f"secret:{kind}[redacted]"


_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "private_key",
        re.compile(
            r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.DOTALL
        ),
    ),
    ("aws_access_key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
    ("slack_token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b")),
    ("api_key", re.compile(r"\bsk-[A-Za-z0-9_-]{16,}")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}")),
]

_BEARER = re.compile(r"(?i)\b(bearer)\s+[A-Za-z0-9._~+/=-]{16,}")

SECRET_KEY_NAMES = (
    "password",
    "passwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "access_key",
    "private_key",
    "client_secret",
    "authorization",
)
_KEY_NAME = (
    r"(?:password|passwd|secret|token|api[_-]?key|access[_-]?key|private[_-]?key|client[_-]?secret)"
)
# The lookaheads keep an existing placeholder ("secret:<kind>[redacted]") from being redacted twice.
_KEY_VALUE = re.compile(
    rf"(?i)\b({_KEY_NAME})\b(\s*[:=]\s*)([\"']?)(?!secret:)(?![^\s\"',;]*\[redacted\])([^\s\"',;]+)\3"
)


def _is_secret_key(name: str) -> bool:
    lowered = name.lower().replace("-", "_")
    return any(part in lowered for part in SECRET_KEY_NAMES)


def redact_text(text: str) -> str:
    """Redact secret shapes inside free text."""
    for kind, pattern in _PATTERNS:
        text = pattern.sub(placeholder(kind), text)
    text = _BEARER.sub(lambda m: f"{m.group(1)} {placeholder('bearer_token')}", text)
    return _KEY_VALUE.sub(
        lambda m: f"{m.group(1)}{m.group(2)}{placeholder(m.group(1).lower().replace('-', '_'))}",
        text,
    )


def redact_value(value: Any) -> Any:
    """Redact recursively through dicts, lists and tuples. Values under secret-named keys are
    replaced whole, whatever they look like."""
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, dict):
        out: dict[Any, Any] = {}
        for key, item in value.items():
            if isinstance(key, str) and _is_secret_key(key) and isinstance(item, (str, int, float)):
                out[key] = placeholder(key.lower().replace("-", "_"))
            else:
                out[key] = redact_value(item)
        return out
    if isinstance(value, (list, tuple)):
        return [redact_value(item) for item in value]
    return value
