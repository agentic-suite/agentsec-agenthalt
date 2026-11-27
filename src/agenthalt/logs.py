"""Structured logging (M0 design §8).

JSON lines on stderr by default, one per event, carrying ``halt_id`` when one is bound via
``bind_halt``. **No secrets at any level** (PRD 06): every message, field and formatted exception
passes through the redactor before it is written. The log is the debuggable companion of the
journal, never a replacement for it.
"""

from __future__ import annotations

import contextlib
import contextvars
import json
import logging
import sys
from collections.abc import Iterator
from datetime import datetime, timezone
from typing import IO, Any

from agenthalt.redact import redact_text, redact_value

__all__ = ["bind_halt", "configure_logging", "get_logger"]

LOGGER_NAME = "agenthalt"
_LEVELS = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
}
_halt_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "agenthalt_halt_id", default=None
)


@contextlib.contextmanager
def bind_halt(halt_id: str) -> Iterator[None]:
    """Correlate every log line inside the block with ``halt_id``."""
    token = _halt_id.set(halt_id)
    try:
        yield
    finally:
        _halt_id.reset(token)


def _iso(created: float) -> str:
    """RFC 3339 UTC with millisecond precision, e.g. ``2026-11-27T02:31:05.123Z``."""
    return datetime.fromtimestamp(created, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _payload(record: logging.LogRecord) -> dict[str, Any]:
    fields = getattr(record, "fields", None) or {}
    data: dict[str, Any] = {
        "ts": _iso(record.created),
        "level": record.levelname.lower(),
        "event": redact_text(record.getMessage()),
        "logger": record.name,
        "halt_id": _halt_id.get(),
    }
    for key, value in redact_value(dict(fields)).items():
        data.setdefault(key, value)
    if record.exc_info:
        data["exception"] = redact_text(logging.Formatter().formatException(record.exc_info))
    return data


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps(_payload(record), sort_keys=True, default=str)


class _TextFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data = _payload(record)
        head = f"{data.pop('ts')} {data.pop('level'):<7} {data.pop('event')}"
        data.pop("logger")
        halt = data.pop("halt_id")
        extras = " ".join(f"{k}={v}" for k, v in sorted(data.items()))
        return " ".join(part for part in (head, f"halt={halt}" if halt else "", extras) if part)


def configure_logging(level: str, fmt: str, *, stream: IO[str] | None = None) -> logging.Logger:
    """(Re)configure the ``agenthalt`` logger. Replaces any previous handler."""
    if level not in _LEVELS:
        raise ValueError(f"unknown log level: {level!r}")
    logger = logging.getLogger(LOGGER_NAME)
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
    handler = logging.StreamHandler(stream if stream is not None else sys.stderr)
    handler.setFormatter(_JsonFormatter() if fmt == "json" else _TextFormatter())
    logger.addHandler(handler)
    logger.setLevel(_LEVELS[level])
    logger.propagate = False
    return logger


def get_logger(name: str | None = None) -> logging.Logger:
    return logging.getLogger(LOGGER_NAME if name is None else f"{LOGGER_NAME}.{name}")
