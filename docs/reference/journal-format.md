# Halt journal format (`agenthalt.journal.v1`)

The halt journal is the append-only, tamper-evident record of who stopped what, when, and why (R12). Its format is
**Tier-0**: fields and actions are only ever added. Implemented in
[`src/agenthalt/journal.py`](../../src/agenthalt/journal.py); design in [M0 design §6](../design/m0-foundation.md).

## Files

`<home>/journal/seg-000001.jsonl`, `seg-000002.jsonl`, … — one canonical JSON object per line, UTF-8, `0600`.
A segment rotates after `journal.segment_max_entries` entries (default 10000).

## Entry

| Field | Type | Notes |
|---|---|---|
| `schema` | `"agenthalt.journal.v1"` | |
| `seq` | int | 1, 2, 3… global across segments |
| `timestamp` | string | RFC 3339 UTC, millisecond precision, e.g. `2026-11-27T02:31:05.123Z` |
| `action` | string | `raise`, `execute`, `complete`, `lift`, `resume`, `escalate`, `trigger_rejected`, `finding`, `lineage` (a checkpoint of the [lineage](lineage.md) head: `lineage_seq`, `lineage_head`), `anchor` |
| `halt_id` | string \| null | safe identifier |
| `actor` | string | who acted — never empty |
| `scope` | string \| null | e.g. `agent:release-bot`, `all` |
| `mode` | string \| null | `pause`, `quarantine`, `kill` |
| `reason` | string \| null | **redacted** before writing |
| `payload` | object | action-specific, **redacted** before writing |
| `prev_hash` | string | `sha256:<hex>` of the previous entry; genesis is `sha256:` + 64 zeros |
| `entry_hash` | string | `sha256:<hex>` over the canonical form of every other field |

**Canonical form:** `json.dumps(entry_without_entry_hash, sort_keys=True, separators=(",", ":"),
ensure_ascii=False)`, UTF-8.

## Rotation anchors

Every segment after the first opens with an `anchor` entry (actor `agenthalt`) whose `prev_hash` is the previous
segment's head and whose payload commits to the previous file:

```json
{"prior_segment": "seg-000001.jsonl", "prior_head": "sha256:…", "prior_entries": 10000, "prior_file_sha256": "…"}
```

`anchor` is written only by rotation; `append()` refuses it.

## Verifying

`agenthalt journal verify` walks every segment and checks: each line parses, `schema` is known, the field set is
exact, `seq` is contiguous, `prev_hash` links, `entry_hash` recomputes, segments are numbered without gaps, and
each anchor matches the prior segment's head, entry count and file hash. It prints the head on success (exit 0)
or the first failure with segment and line (exit 1).

| Detected | By |
|---|---|
| an edited entry | `entry_hash` |
| an edited entry with a recomputed hash | the next entry's `prev_hash` |
| a deleted or reordered entry | `seq` / `prev_hash` |
| a deleted middle segment | segment numbering + the next anchor |
| an edited prior segment (even byte-only) | the next anchor's `prior_file_sha256` |
| a truncated final line | parse failure |

**Not detected by the local chain alone:** truncation of the newest whole entries, or a wholesale rebuild —
nothing outside the journal remembers the head. Record the head that `verify` prints somewhere else; remote
anchoring (open decision #9, M5) closes this.

## Writing

Writers take an exclusive `flock` on `journal/.lock`, check the **tail**, append one line, `fsync`, and release, so
concurrent `agenthalt` processes never fork the chain.

The tail check is constant-time: segment numbering has no gap, the last segment's first and last lines parse,
and the last entry's hash recomputes. An unterminated, unparsable or edited tail makes `append()` refuse to
write. The full-chain walk is `journal verify` (and `doctor`), not every append: re-verifying the whole history
on each write would make the halt path's journal cost grow without bound (PRD 39: trigger + journal ≤ 50 ms).
