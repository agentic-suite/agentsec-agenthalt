"""The halt journal (R12, M0 design §6) — append-only, hash-chained, rotation-anchored.

Every entry carries ``prev_hash`` (the previous entry's hash) and ``entry_hash`` (SHA-256 over the
canonical JSON of every other field). Segments rotate at ``segment_max_entries``; each new segment
opens with an ``anchor`` entry committing the prior segment's head, entry count and file hash, so
the chain is continuous across files and an edited or deleted prior segment is detectable.

What the local chain cannot detect on its own: truncation of the *newest* entries or a wholesale
rebuild, because nothing outside the journal remembers the head. ``verify`` prints the head so
operators can record it elsewhere; remote anchoring (open decision #9) closes the gap in M5.

The entry format is Tier-0 (PRD 40): fields and actions are only ever added.
"""

from __future__ import annotations

import contextlib
import fcntl
import hashlib
import json
import os
import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agenthalt.ids import validate_id
from agenthalt.redact import redact_text, redact_value

__all__ = [
    "ACTIONS",
    "GENESIS",
    "SCHEMA",
    "Journal",
    "JournalError",
    "VerifyResult",
    "canonical_hash",
]

SCHEMA = "agenthalt.journal.v1"
GENESIS = "sha256:" + "0" * 64
ACTIONS = frozenset(
    {
        "raise",
        "execute",
        "complete",
        "lift",
        "resume",
        "escalate",
        "trigger_rejected",
        "finding",
        "anchor",
    }
)
MODES = frozenset({"pause", "quarantine", "kill"})
FIELDS = (
    "schema",
    "seq",
    "timestamp",
    "action",
    "halt_id",
    "actor",
    "scope",
    "mode",
    "reason",
    "payload",
    "prev_hash",
    "entry_hash",
)
_SEGMENT = re.compile(r"seg-(\d{6})\.jsonl")


class JournalError(Exception):
    """An entry was refused, or the journal on disk is not an intact chain."""


def _canonical(entry: dict[str, Any]) -> bytes:
    return json.dumps(entry, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def canonical_hash(entry_without_hash: dict[str, Any]) -> str:
    """``sha256:<hex>`` over the canonical JSON form (sorted keys, no whitespace, UTF-8)."""
    return "sha256:" + hashlib.sha256(_canonical(entry_without_hash)).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


@dataclass(frozen=True)
class VerifyResult:
    ok: bool
    entries: int
    head: str
    segments: int
    error: str | None = None
    segment: str | None = None
    line: int | None = None

    def describe(self) -> str:
        if self.ok:
            return (
                f"journal intact: {self.entries} entries in {self.segments} segment(s); "
                f"head {self.head}"
            )
        where = f"{self.segment} line {self.line}" if self.segment else "journal"
        return f"journal BROKEN at {where}: {self.error}"


class Journal:
    """The halt journal under ``<home>/journal/``."""

    def __init__(
        self,
        home: Path,
        *,
        segment_max_entries: int = 10_000,
        now: Callable[[], str] = _utc_now,
    ) -> None:
        if segment_max_entries < 2:
            raise ValueError("segment_max_entries must be >= 2")
        self.home = Path(home)
        self.dir = self.home / "journal"
        self.segment_max_entries = segment_max_entries
        self._now = now

    # ----------------------------------------------------------------------- reading

    def _segments(self) -> list[tuple[int, Path]]:
        if not self.dir.is_dir():
            return []
        found = []
        for path in self.dir.iterdir():
            match = _SEGMENT.fullmatch(path.name)
            if match:
                found.append((int(match.group(1)), path))
        return sorted(found)

    def _read(self) -> Iterator[tuple[str, int, dict[str, Any]]]:
        """Yield ``(segment_name, line_no, entry)``; raise on unparsable lines."""
        for _, path in self._segments():
            with path.open(encoding="utf-8") as handle:
                for line_no, line in enumerate(handle, start=1):
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError as exc:
                        raise JournalError(
                            f"{path.name} line {line_no}: cannot parse entry ({exc.msg})"
                        ) from None
                    if not isinstance(entry, dict):
                        raise JournalError(f"{path.name} line {line_no}: entry is not an object")
                    yield path.name, line_no, entry

    def entries(self, *, halt_id: str | None = None) -> Iterator[dict[str, Any]]:
        for _, _, entry in self._read():
            if halt_id is None or entry.get("halt_id") == halt_id:
                yield entry

    def head(self) -> str:
        result = self.verify()
        if not result.ok:
            raise JournalError(result.describe())
        return result.head

    def verify(self) -> VerifyResult:
        segments = self._segments()
        prev_hash, seq, count = GENESIS, 0, 0
        prior: tuple[str, str, int, str] | None = None  # name, head, entries, file sha256
        expected_number = 1
        for number, path in segments:
            name = path.name
            if number != expected_number:
                return VerifyResult(
                    False,
                    count,
                    prev_hash,
                    len(segments),
                    f"missing segment seg-{expected_number:06d}.jsonl",
                    name,
                    None,
                )
            expected_number += 1
            raw = path.read_bytes()
            seg_entries = 0
            for line_no, line in enumerate(raw.decode("utf-8").splitlines(), start=1):
                fail = self._check_line(line, seq, prev_hash, line_no, prior)
                if fail is not None:
                    return VerifyResult(False, count, prev_hash, len(segments), fail, name, line_no)
                entry = json.loads(line)
                seq, prev_hash = entry["seq"], entry["entry_hash"]
                seg_entries += 1
                count += 1
            if seg_entries == 0:
                return VerifyResult(
                    False, count, prev_hash, len(segments), "empty segment", name, None
                )
            prior = (name, prev_hash, seg_entries, hashlib.sha256(raw).hexdigest())
        return VerifyResult(True, count, prev_hash, len(segments))

    @staticmethod
    def _check_line(
        line: str,
        seq: int,
        prev_hash: str,
        line_no: int,
        prior: tuple[str, str, int, str] | None,
    ) -> str | None:
        try:
            entry = json.loads(line)
        except json.JSONDecodeError as exc:
            return f"cannot parse entry ({exc.msg})"
        if not isinstance(entry, dict):
            return "entry is not an object"
        if entry.get("schema") != SCHEMA:
            return f"unknown schema {entry.get('schema')!r}"
        if set(entry) != set(FIELDS):
            return f"unexpected fields {sorted(set(entry) ^ set(FIELDS))}"
        if entry["seq"] != seq + 1:
            return f"seq {entry['seq']} does not follow {seq} (deleted or reordered entry)"
        if entry["prev_hash"] != prev_hash:
            return "prev_hash does not match the previous entry_hash"
        body = {k: v for k, v in entry.items() if k != "entry_hash"}
        if canonical_hash(body) != entry["entry_hash"]:
            return "entry_hash does not match the entry (edited entry)"
        is_anchor = entry["action"] == "anchor"
        if line_no == 1 and prior is not None:
            if not is_anchor:
                return "segment does not open with a rotation anchor"
            name, head, entries, file_hash = prior
            payload = entry["payload"]
            for field, expected in (
                ("prior_segment", name),
                ("prior_head", head),
                ("prior_entries", entries),
                ("prior_file_sha256", file_hash),
            ):
                if payload.get(field) != expected:
                    return f"anchor {field} does not match {name} (prior segment altered)"
        elif is_anchor:
            return "anchor entry outside a segment boundary"
        return None

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

    def _write(self, path: Path, entry: dict[str, Any]) -> None:
        new = not path.exists()
        fd = os.open(path, os.O_CREAT | os.O_APPEND | os.O_WRONLY, 0o600)
        try:
            os.write(fd, _canonical(entry) + b"\n")
            os.fsync(fd)
        finally:
            os.close(fd)
        if new:
            dir_fd = os.open(self.dir, os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)

    def _make(self, action: str, seq: int, prev_hash: str, **fields: Any) -> dict[str, Any]:
        entry: dict[str, Any] = {
            "schema": SCHEMA,
            "seq": seq,
            "timestamp": self._now(),
            "action": action,
            "halt_id": fields.get("halt_id"),
            "actor": fields["actor"],
            "scope": fields.get("scope"),
            "mode": fields.get("mode"),
            "reason": fields.get("reason"),
            "payload": fields.get("payload") or {},
            "prev_hash": prev_hash,
        }
        entry["entry_hash"] = canonical_hash(entry)
        return entry

    def append(
        self,
        action: str,
        *,
        actor: str,
        halt_id: str | None = None,
        scope: str | None = None,
        mode: str | None = None,
        reason: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Append one entry under the write lock and return it as written."""
        if action not in ACTIONS or action == "anchor":
            raise JournalError(f"unknown or reserved journal action: {action!r}")
        if not actor:
            raise JournalError("every journal entry names its actor")
        if halt_id is not None:
            try:
                validate_id(halt_id, what="halt_id")
            except ValueError as exc:
                raise JournalError(str(exc)) from None
        if mode is not None and mode not in MODES:
            raise JournalError(f"unknown mode: {mode!r}")
        clean_reason = redact_text(reason) if reason is not None else None
        clean_payload = redact_value(payload or {})

        with self._locked():
            segments = self._segments()
            number, path = segments[-1] if segments else (1, self.dir / "seg-000001.jsonl")
            seq, prev_hash, in_segment = self._tail(segments)
            if segments and in_segment >= self.segment_max_entries:
                raw = path.read_bytes()
                anchor = self._make(
                    "anchor",
                    seq + 1,
                    prev_hash,
                    actor="agenthalt",
                    payload={
                        "prior_segment": path.name,
                        "prior_head": prev_hash,
                        "prior_entries": in_segment,
                        "prior_file_sha256": hashlib.sha256(raw).hexdigest(),
                    },
                )
                number, path = number + 1, self.dir / f"seg-{number + 1:06d}.jsonl"
                self._write(path, anchor)
                seq, prev_hash = anchor["seq"], anchor["entry_hash"]
            entry = self._make(
                action,
                seq + 1,
                prev_hash,
                actor=actor,
                halt_id=halt_id,
                scope=scope,
                mode=mode,
                reason=clean_reason,
                payload=clean_payload,
            )
            self._write(path, entry)
            return entry

    def _tail(self, segments: list[tuple[int, Path]]) -> tuple[int, str, int]:
        """Return ``(last seq, head hash, entries in the last segment)`` in constant time.

        The append path checks only the tail: the last segment is where it should be, its first
        and last entries parse, and the last entry's hash recomputes. Full-chain verification is
        ``verify()`` (``journal verify``, ``doctor``) — re-walking the whole history on every
        append would make the halt path's journal write grow without bound (PRD 39: <= 50 ms).
        """
        if not segments:
            return 0, GENESIS, 0
        number, path = segments[-1]
        if number != len(segments):
            raise JournalError(
                "refusing to append: segment numbering has a gap (run `journal verify`)"
            )
        first, last = _first_line(path), _last_line(path)
        if first is None or last is None:
            raise JournalError(f"refusing to append: {path.name} is empty or unterminated")
        try:
            head, tail = json.loads(first), json.loads(last)
        except json.JSONDecodeError:
            raise JournalError(f"refusing to append: {path.name} has an unparsable entry") from None
        if not isinstance(tail, dict) or not isinstance(head, dict):
            raise JournalError(f"refusing to append: {path.name} has a non-object entry")
        body = {k: v for k, v in tail.items() if k != "entry_hash"}
        if tail.get("schema") != SCHEMA or canonical_hash(body) != tail.get("entry_hash"):
            raise JournalError(f"refusing to append: the last entry of {path.name} does not verify")
        return int(tail["seq"]), str(tail["entry_hash"]), int(tail["seq"]) - int(head["seq"]) + 1


def _first_line(path: Path) -> str | None:
    with path.open("rb") as handle:
        line = handle.readline()
    return line.decode("utf-8") if line.endswith(b"\n") else None


def _last_line(path: Path, chunk: int = 4096) -> str | None:
    """The last complete line, read from the end of the file (no full scan)."""
    with path.open("rb") as handle:
        handle.seek(0, os.SEEK_END)
        end = handle.tell()
        if end == 0:
            return None
        handle.seek(end - 1)
        if handle.read(1) != b"\n":
            return None  # unterminated: a crash or a truncation mid-write
        data, pos = b"", end - 1
        while pos > 0 and b"\n" not in data:
            step = min(chunk, pos)
            pos -= step
            handle.seek(pos)
            data = handle.read(step) + data
        return data.rsplit(b"\n", 1)[-1].decode("utf-8") if b"\n" in data else data.decode("utf-8")
