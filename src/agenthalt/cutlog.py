"""The cut record: what each halt is about to change, written *before* it is changed.

Append-only and lock-free, one file per halt. Each line adds an item (``cut``) or retires it
(``done``). A halt that crashes, times out or is lifted midway therefore never loses track of what
it froze, and a release that fails can be retried.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agenthalt.logs import get_logger

__all__ = ["LAYERS", "CutLog", "CutWriter", "Record", "item_key"]

LAYERS = ("process", "sandbox", "credentials", "gateway")
_log = get_logger("cutlog")


def item_key(item: Mapping[str, Any]) -> tuple[Any, Any] | None:
    """What an item holds, for telling whether another halt already holds it."""
    if "freeze" in item:
        return ("freeze", item["freeze"])
    if "pid" in item and "start" in item:
        return (item["pid"], item["start"])
    return None


@dataclass
class Record:
    halt: dict[str, Any] | None = None
    pending: dict[str, list[dict[str, Any]]] = field(
        default_factory=lambda: {layer: [] for layer in LAYERS}
    )
    ever: dict[str, list[dict[str, Any]]] = field(
        default_factory=lambda: {layer: [] for layer in LAYERS}
    )

    def __bool__(self) -> bool:
        return any(self.pending.values())


class CutWriter:
    """One open file. Opened with the invoking user's ids; writable after elevation."""

    def __init__(self, fd: int | None) -> None:
        self._fd = fd
        self.failed: str | None = None if fd is not None else "the cut record cannot be written"

    def _line(self, body: Mapping[str, Any]) -> None:
        if self._fd is None:
            return
        try:
            os.write(self._fd, json.dumps(body, sort_keys=True).encode() + b"\n")
        except (OSError, ValueError) as exc:
            self.failed = f"the cut record cannot be written: {exc}"
            _log.error("cutlog.failed", extra={"fields": {"error": str(exc)}})

    def header(self, halt: Mapping[str, Any]) -> None:
        self._line({"halt": dict(halt)})

    def cut(self, layer: str, item: Mapping[str, Any]) -> None:
        self._line({"op": "cut", "layer": layer, "item": dict(item)})

    def done(self, layer: str, item: Mapping[str, Any]) -> None:
        self._line({"op": "done", "layer": layer, "item": dict(item)})

    def close(self) -> None:
        if self._fd is not None:
            with contextlib.suppress(OSError):
                os.close(self._fd)
            self._fd = None


class CutLog:
    def __init__(self, home: Path) -> None:
        self.dir = Path(home) / "cuts"

    def writer(self, halt: Mapping[str, Any]) -> CutWriter:
        try:
            self.dir.mkdir(mode=0o700, parents=True, exist_ok=True)
            fd = os.open(
                self.dir / f"{halt['halt_id']}.jsonl",
                os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW,
                0o600,
            )
        except OSError as exc:
            _log.error("cutlog.failed", extra={"fields": {"error": str(exc)}})
            return CutWriter(None)
        writer = CutWriter(fd)
        writer.header(halt)
        return writer

    def read(self, halt_id: str) -> Record:
        record = Record()
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", halt_id):
            return record
        try:
            text = (self.dir / f"{halt_id}.jsonl").read_text(errors="replace")
        except OSError:
            return record
        pending: dict[tuple[str, str], dict[str, Any]] = {}
        ever: dict[tuple[str, str], dict[str, Any]] = {}
        for line in text.splitlines():
            try:
                body = json.loads(line)
                if "halt" in body:
                    record.halt = dict(body["halt"])
                    continue
                layer, item = body["layer"], dict(body["item"])
                if layer not in LAYERS:
                    continue
                key = (layer, json.dumps(item, sort_keys=True))
                if body["op"] == "cut":
                    pending[key] = ever[key] = item
                else:
                    pending.pop(key, None)
            except (ValueError, KeyError, TypeError):
                continue  # a torn or foreign line says nothing
        for source, target in ((pending, record.pending), (ever, record.ever)):
            for (layer, _), item in source.items():
                target[layer].append(item)
        return record

    def held(self, *, besides: str) -> frozenset[tuple[Any, Any]]:
        """Everything some other halt still holds."""
        found: set[tuple[Any, Any]] = set()
        try:
            names = [p.stem for p in self.dir.glob("*.jsonl")]
        except OSError:
            return frozenset()
        for halt_id in names:
            if halt_id != besides:
                for item in self.read(halt_id).pending["process"]:
                    key = item_key(item)
                    if key is not None and all(isinstance(v, (int, str)) for v in key):
                        found.add(key)
        return frozenset(found)
