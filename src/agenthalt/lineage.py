"""The lineage registry (R9, DD-24, DD-48, M2 design §2-§3).

Append-only, hash-chained JSONL segments under ``<home>/lineage/``. Every record is authenticated
with its adapter's HMAC key, and every append batch is checkpointed in the journal, so a deleted,
reordered, edited, forged or rebuilt edge is detectable. Records that authenticate are still used
when the chain around them is damaged: tampering must not make *other* children disappear.

Limit (DD-44): an agent running as the same OS user can read the keys. ``run --user`` removes that.
"""

from __future__ import annotations

import contextlib
import fcntl
import hashlib
import hmac
import json
import os
import re
import secrets
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agenthalt.ids import validate_id
from agenthalt.journal import GENESIS, Journal, JournalError, canonical_hash
from agenthalt.redact import redact_value

__all__ = [
    "SOURCES",
    "AdapterCredential",
    "Edge",
    "ForgedEdgeError",
    "LineageBusyError",
    "LineageError",
    "LineageRead",
    "LineageRegistry",
    "TamperFinding",
]

SCHEMA = "agenthalt.lineage.v1"
SOURCES = ("process", "runtime", "hook")
FIELDS = frozenset(
    {"schema", "seq", "recorded_at", "kind", "adapter", "data", "mac", "prev_hash", "chain_hash"}
)
_SEGMENT = re.compile(r"seg-(\d{6})\.jsonl")


class LineageError(Exception):
    """A record was refused, or the registry cannot be appended to safely."""


class LineageBusyError(LineageError):
    """Another process holds the lineage lock."""


class ForgedEdgeError(LineageError):
    """A write that does not authenticate as a registered adapter."""


@dataclass(frozen=True)
class AdapterCredential:
    name: str
    source: str
    key: bytes = field(repr=False)


@dataclass(frozen=True)
class Edge:
    parent_run: str
    child_run: str
    spawn_source: str
    adapter: str
    recorded_at: str
    chain_hash: str
    seq: int
    child: dict[str, Any]


@dataclass(frozen=True)
class TamperFinding:
    """The input contract for the 8.2 ``tamper_lineage`` trigger."""

    segment: str
    seq: int
    problem: str
    detail: str
    detected_at: str


@dataclass(frozen=True)
class LineageRead:
    edges: tuple[Edge, ...]
    verified: frozenset[str]
    findings: tuple[TamperFinding, ...]
    head: str
    complete: bool = True


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _line(record: dict[str, Any]) -> bytes:
    return (
        json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
    ).encode("utf-8")


def _mac(key: bytes, kind: str, adapter: str, data: Any, recorded_at: str) -> str:
    body = _line(
        {
            "schema": SCHEMA,
            "kind": kind,
            "adapter": adapter,
            "data": data,
            "recorded_at": recorded_at,
        }
    )
    return hmac.new(key, body, hashlib.sha256).hexdigest()


def _chain(record: dict[str, Any]) -> str:
    return canonical_hash({k: v for k, v in record.items() if k != "chain_hash"})


class LineageRegistry:
    def __init__(
        self,
        home: Path,
        *,
        journal: Journal,
        segment_max_entries: int = 10_000,
        now: Callable[[], str] = _now,
    ) -> None:
        if segment_max_entries < 2:
            raise ValueError("segment_max_entries must be >= 2")
        self.home = Path(home)
        self.dir = self.home / "lineage"
        self.keys = self.home / "keys" / "lineage"
        self.journal = journal
        self.segment_max_entries = segment_max_entries
        self.lock_timeout_s = 5.0
        self._now = now

    # ----------------------------------------------------------------------- adapters

    def _load_key(self, name: str) -> tuple[str, bytes] | None:
        try:
            source, key = (self.keys / f"{name}.key").read_text().split()
            return source, bytes.fromhex(key)
        except FileNotFoundError:
            return None
        except (OSError, ValueError) as exc:
            raise LineageError(f"adapter key for {name!r} is unreadable: {exc}") from None

    def register_adapter(self, name: str, source: str) -> AdapterCredential:
        """Create (once) and return an adapter's credential. Needs write access to the home."""
        validate_id(name, what="adapter")
        if source not in SOURCES:
            raise LineageError(f"unknown spawn source: {source!r}")
        for directory in (self.home, self.home / "keys", self.keys):
            directory.mkdir(mode=0o700, parents=True, exist_ok=True)
            os.chmod(directory, 0o700)
        with self._locked():
            known = self._load_key(name)
            if known is None:
                key = secrets.token_bytes(32)
                fd = os.open(self.keys / f"{name}.key", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                try:
                    os.write(fd, f"{source} {key.hex()}\n".encode())
                    os.fsync(fd)
                finally:
                    os.close(fd)
                known = source, key
        if known[0] != source:
            raise LineageError(f"adapter {name!r} is registered as {known[0]!r}, not {source!r}")
        return AdapterCredential(name, *known)

    def _authenticate(self, credential: AdapterCredential) -> None:
        known = self._load_key(validate_id(credential.name, what="adapter"))
        if (
            known is None
            or known[0] != credential.source
            or not hmac.compare_digest(known[1], credential.key)
        ):
            self._journal_finding(
                "forged_edge_refused", {"adapter": credential.name}, actor="agenthalt"
            )
            raise ForgedEdgeError(f"adapter {credential.name!r} does not authenticate")

    # ----------------------------------------------------------------------- writing

    @contextlib.contextmanager
    def _locked(self, expired: Callable[[], bool] | None = None) -> Iterator[None]:
        for directory in (self.home, self.dir):
            directory.mkdir(mode=0o700, parents=True, exist_ok=True)
            os.chmod(directory, 0o700)
        fd = os.open(self.dir / ".lock", os.O_CREAT | os.O_RDWR, 0o600)
        give_up = time.monotonic() + self.lock_timeout_s
        try:
            while True:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() >= give_up or (expired is not None and expired()):
                        raise LineageBusyError(
                            "the lineage lock is held by another process"
                        ) from None
                    time.sleep(0.01)
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    def _segments(self) -> list[tuple[int, Path]]:
        if not self.dir.is_dir():
            return []
        found = [(m, p) for p in self.dir.iterdir() if (m := _SEGMENT.fullmatch(p.name))]
        return sorted((int(m.group(1)), p) for m, p in found)

    def _tail(self, path: Path) -> tuple[int, str, int, bytes]:
        """``(last seq, head, records in segment, raw bytes)``; refuse to build on a bad tail."""
        raw = path.read_bytes()
        rows = raw.split(b"\n")
        if not raw.endswith(b"\n"):
            raise LineageError(f"refusing to append: {path.name} is empty or unterminated")
        try:
            last = json.loads(rows[-2])
            if _chain(last) != last["chain_hash"]:
                raise ValueError("hash")
            return int(last["seq"]), str(last["chain_hash"]), len(rows) - 1, raw
        except (ValueError, KeyError, TypeError, AttributeError):
            raise LineageError(
                f"refusing to append: the last record of {path.name} does not verify"
            ) from None

    def _write(self, path: Path, records: list[dict[str, Any]]) -> None:
        fd = os.open(path, os.O_CREAT | os.O_APPEND | os.O_WRONLY, 0o600)
        try:
            os.write(fd, b"".join(_line(r) for r in records))
            os.fsync(fd)
        finally:
            os.close(fd)

    def _record(
        self, credential: AdapterCredential, kind: str, data: Any, seq: int, prev: str
    ) -> dict[str, Any]:
        recorded_at = self._now()
        record: dict[str, Any] = {
            "schema": SCHEMA,
            "seq": seq,
            "recorded_at": recorded_at,
            "kind": kind,
            "adapter": credential.name,
            "data": data,
            "mac": _mac(credential.key, kind, credential.name, data, recorded_at),
            "prev_hash": prev,
        }
        record["chain_hash"] = _chain(record)
        return record

    def _append(
        self, credential: AdapterCredential, kind: str, items: list[Any]
    ) -> list[dict[str, Any]]:
        self._authenticate(credential)
        if not items:
            return []
        written: list[dict[str, Any]] = []
        with self._locked():
            segments = self._segments()
            number, path = segments[-1] if segments else (1, self.dir / "seg-000001.jsonl")
            seq, head, count, raw = self._tail(path) if segments else (0, GENESIS, 0, b"")
            batch: list[dict[str, Any]] = []
            for data in items:
                if count >= self.segment_max_entries:
                    if batch:
                        self._write(path, batch)
                        batch, raw = [], path.read_bytes()
                    anchor = self._record(
                        credential,
                        "anchor",
                        {
                            "prior_segment": path.name,
                            "prior_head": head,
                            "prior_entries": count,
                            "prior_file_sha256": hashlib.sha256(raw).hexdigest(),
                        },
                        seq + 1,
                        head,
                    )
                    number, path = number + 1, self.dir / f"seg-{number + 1:06d}.jsonl"
                    batch, count, seq, head = [anchor], 1, anchor["seq"], anchor["chain_hash"]
                record = self._record(credential, kind, data, seq + 1, head)
                batch.append(record)
                written.append(record)
                count, seq, head = count + 1, record["seq"], record["chain_hash"]
            self._write(path, batch)
            # Lineage first, checkpoint second: a crash between them leaves lineage ahead.
            self.journal.append(
                "lineage",
                actor=f"adapter:{credential.name}",
                payload={"lineage_seq": seq, "lineage_head": head},
            )
        return written

    def append_edges(
        self, credential: AdapterCredential, edges: list[dict[str, Any]]
    ) -> list[Edge]:
        """Append ``{parent_run, child_run, child}`` records; the source is the adapter's own."""
        items = []
        for item in edges:
            try:
                parent = validate_id(item["parent_run"], what="parent_run")
                child = validate_id(item["child_run"], what="child_run")
            except (KeyError, ValueError) as exc:
                raise LineageError(f"invalid edge: {exc}") from None
            if parent == child:
                raise LineageError(f"invalid edge: {child} cannot be its own parent")
            items.append(
                {
                    "parent_run": parent,
                    "child_run": child,
                    "spawn_source": credential.source,
                    "child": redact_value(item.get("child") or {}),
                }
            )
        return [_edge(r) for r in self._append(credential, "edge", items)]

    def mark_verified(self, credential: AdapterCredential, run: str) -> None:
        self._append(credential, "verified", [{"run": validate_id(run, what="run")}])

    # ----------------------------------------------------------------------- reading

    def read(self, *, expired: Callable[[], bool] = lambda: False) -> LineageRead:
        """Read and verify everything. ``expired`` stops early (``complete=False``)."""
        if not self.dir.is_dir():
            return self._scan(expired)
        try:
            with self._locked(expired):
                return self._scan(expired)
        except LineageBusyError:
            return LineageRead((), frozenset(), (), GENESIS, False)

    def _scan(self, expired: Callable[[], bool]) -> LineageRead:
        edges: list[Edge] = []
        verified: set[str] = set()
        findings: dict[tuple[str, str, int], TamperFinding] = {}
        chain: dict[int, str] = {}
        keys: dict[str, tuple[str, bytes] | None] = {}

        def flag(segment: str, seq: int, problem: str, detail: str) -> None:
            findings.setdefault(
                (problem, segment, seq),
                TamperFinding(segment, seq, problem, detail, self._now()),
            )

        seq, head, expected_number = 0, GENESIS, 1
        prior: dict[str, Any] | None = None
        for number, path in self._segments():
            name = path.name
            if number != expected_number:
                flag(f"seg-{expected_number:06d}.jsonl", seq + 1, "segment_missing", "deleted")
            expected_number = number + 1
            try:
                raw = path.read_bytes()
            except OSError as exc:
                flag(name, seq + 1, "unreadable_record", str(exc))
                continue
            rows = raw.split(b"\n")
            if rows[-1] == b"":
                rows.pop()
            elif rows:
                flag(name, seq + 1, "unreadable_record", "unterminated last record")
            for line_no, row in enumerate(rows, start=1):
                if len(chain) % 256 == 0 and expired():
                    return LineageRead(
                        tuple(edges), frozenset(verified), tuple(findings.values()), head, False
                    )
                try:
                    record = _parse(row)
                    adapter = record["adapter"]
                    if adapter not in keys:
                        try:
                            keys[adapter] = self._load_key(adapter)
                        except LineageError:
                            keys[adapter] = None
                    known = keys[adapter]
                    authentic = known is not None and hmac.compare_digest(
                        _mac(
                            known[1],
                            record["kind"],
                            adapter,
                            record["data"],
                            record["recorded_at"],
                        ).encode(),
                        record["mac"].encode(),
                    )
                    intact = _chain(record) == record["chain_hash"]
                except Exception:  # whatever the bytes are, they are a finding, never a crash
                    flag(name, seq + 1, "unreadable_record", f"line {line_no}")
                    continue
                number_in_chain = record["seq"]
                if number_in_chain != seq + 1 or record["prev_hash"] != head:
                    flag(
                        name,
                        number_in_chain,
                        "chain_broken",
                        f"line {line_no} does not follow seq {seq} (deleted or reordered)",
                    )
                if not intact:
                    flag(name, number_in_chain, "forged_record", f"line {line_no} was edited")
                    authentic = False
                if record["kind"] == "anchor" and prior is not None and line_no == 1:
                    data = record["data"]
                    if any(data.get(k) != v for k, v in prior.items()):
                        flag(name, number_in_chain, "anchor_mismatch", "prior segment altered")
                seq, head = number_in_chain, record["chain_hash"]
                chain[seq] = head
                if not authentic:
                    flag(name, seq, "forged_record", f"line {line_no} does not authenticate")
                    continue
                data = record["data"]
                if record["kind"] == "edge":
                    try:
                        if known is None or data.get("spawn_source") != known[0]:
                            flag(name, seq, "forged_record", "adapter claimed another source")
                            continue
                        edges.append(_edge(record))
                    except (KeyError, TypeError):
                        flag(name, seq, "unreadable_record", f"line {line_no} is not an edge")
                elif record["kind"] == "verified":
                    verified.add(str(data.get("run")))
            prior = {
                "prior_segment": name,
                "prior_head": head,
                "prior_entries": len(rows),
                "prior_file_sha256": hashlib.sha256(raw).hexdigest(),
            }
        self._check_checkpoints(chain, flag)
        return LineageRead(tuple(edges), frozenset(verified), tuple(findings.values()), head)

    def _check_checkpoints(
        self, chain: dict[int, str], flag: Callable[[str, int, str, str], None]
    ) -> None:
        try:
            verified = self.journal.verify()
            if not verified.ok:
                flag("journal", 0, "journal_unreadable", verified.describe())
            for entry in self.journal.entries():
                if entry.get("action") != "lineage":
                    continue
                seq = int(_payload(entry)["lineage_seq"])
                if seq not in chain:
                    flag("journal", seq, "records_missing", "a checkpointed record is gone")
                elif chain[seq] != _payload(entry)["lineage_head"]:
                    flag("journal", seq, "checkpoint_mismatch", "a record was replaced")
        except Exception as exc:
            flag("journal", 0, "journal_unreadable", str(exc))

    # ----------------------------------------------------------------------- findings

    def _journal_finding(self, finding: str, payload: dict[str, Any], *, actor: str) -> None:
        self.journal.append("finding", actor=actor, payload={"finding": finding, **payload})

    def record_finding(
        self, finding: str, payload: dict[str, Any], *, actor: str, unique: tuple[str, ...]
    ) -> bool:
        """Journal a finding once per distinct ``unique`` fields. Returns True when written."""
        wanted = {k: payload[k] for k in unique}
        for entry in self.journal.entries():
            seen = _payload(entry)
            if seen.get("finding") == finding and all(seen.get(k) == v for k, v in wanted.items()):
                return False
        self._journal_finding(finding, payload, actor=actor)
        return True

    def findings(self, finding: str) -> list[dict[str, Any]]:
        return [
            _payload(e) for e in self.journal.entries() if _payload(e).get("finding") == finding
        ]

    def check_tamper(self, *, actor: str) -> tuple[TamperFinding, ...]:
        """Verify, and journal each tamper finding once — before anything reacts to it."""
        found = self.read().findings
        for item in found:
            try:
                self.record_finding(
                    "tamper_lineage",
                    {
                        "problem": item.problem,
                        "segment": item.segment,
                        "lineage_seq": item.seq,
                        "detail": item.detail,
                        "detected_at": item.detected_at,
                    },
                    actor=actor,
                    unique=("problem", "segment", "lineage_seq"),
                )
            except (JournalError, OSError, UnicodeError, ValueError):
                break  # the journal itself is damaged: the finding is still returned
        return found


def _parse(row: bytes) -> dict[str, Any]:
    """A record with the right fields and types, or an exception."""
    record = json.loads(row)
    if not isinstance(record, dict) or set(record) != FIELDS or record["schema"] != SCHEMA:
        raise ValueError("not a lineage record")
    if type(record["seq"]) is not int or not isinstance(record["data"], dict):
        raise ValueError("bad types")
    for name in ("kind", "adapter", "mac", "recorded_at", "prev_hash", "chain_hash"):
        if not isinstance(record[name], str):
            raise ValueError("bad types")
    validate_id(record["adapter"], what="adapter")
    return record


def _payload(entry: dict[str, Any]) -> dict[str, Any]:
    payload = entry.get("payload")
    return payload if isinstance(payload, dict) else {}


def _edge(record: dict[str, Any]) -> Edge:
    data = record["data"]
    return Edge(
        parent_run=data["parent_run"],
        child_run=data["child_run"],
        spawn_source=data["spawn_source"],
        adapter=record["adapter"],
        recorded_at=record["recorded_at"],
        chain_hash=record["chain_hash"],
        seq=record["seq"],
        child=data["child"],
    )
