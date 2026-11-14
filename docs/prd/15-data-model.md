# PRD 15 — Data Model & Lifecycle

**BLUF:** The core entities are **Trigger → Halt → LineageEdge → StopPlan → Execution → Confirmation →
Receipt → EvidenceSnapshot → JournalEntry**, with **HaltState** (the store's live kill state) and
**CompensationItem** (the no-undo honesty record). Halts are emitted in the **agentwatch schema**; receipts are
offline-verifiable; local state lives under `.agenthalt/`; every mutation of the record is hash-chained.

**Status:** Draft — v0.1.0 (2026-11-14) · **Owner:** @deghosal-2026 · **Parent:** agentic-suite #209 · PRD #216

## Entities

| Entity | Definition | Key fields |
|---|---|---|
| **Trigger** | The authenticated raise of a halt | `trigger_id`, `source` (`cli`/`webhook`/`pagerduty`/`slack`/`panic_key`/`dead_man`/`drill`), `principal`, `channel`, `reason`, `reason_code?`, `signature` |
| **Halt** | The resolved stop request | `halt_id`, `target` (`agent`/`session`/`run`/`subtree`/`all`), `mode` (`pause`/`quarantine`/`kill`), `status` (`pending`/`blocking`/`executing`/`complete`/`incomplete`/`lifted`), `trigger_id`, `deadline_ms`, `created_at` |
| **HaltState** | The authoritative kill state (the store) | `scope`, `mode`, `halt_id`, `set_at`, `ttl?`, `cache_ttl` |
| **LineageEdge** | A parent→child spawn record | `parent_run`, `child_run`, `spawn_source` (`hook`/`process`/`runtime`), `recorded_at`, `chain_hash` |
| **Subtree** | The resolved target graph | `root`, `members[]` (run ids), `grants[]` (credential refs held by members) |
| **StopPlan** | The deterministic fan-out plan | `halt_id`, `steps[]` (`{layer, adapter, action, order, timeout_ms}`), `adapter_versions{}` |
| **Execution** | One layer's cut of one target | `step_ref`, `target`, `started_at`, `finished_at?`, `outcome` (`confirmed`/`requested`/`unsupported`/`failed`), `signature` |
| **Confirmation** | An enforcement point's signed report | `execution_ref`, `layer`, `status`, `evidence_ref?`, `signed_by` |
| **Receipt** | The proof-of-stop artifact | `halt_id`, `subtree`, `confirmations[]`, `refused_calls`, `survivors[]`, `compensation[]`, `readout`, `evidence_ref`, `verifier_input{}` |
| **EvidenceSnapshot** | The preserved scene | `snapshot_id`, `trace_window_ref`, `process_tree`, `open_connections[]`, `timestamp`, `prev_hash`, `entry_hash` |
| **CompensationItem** | A side effect that already landed | `kind` (`email_sent`/`record_written`/`call_made`/…), `ref`, `observed_at`, `reversible` (always `false` at v0.1.0) |
| **JournalEntry** | One append-only halt-history record | `seq`, `prev_hash`, `entry_hash`, `halt_id`, `actor`, `action` (`raise`/`execute`/`complete`/`lift`/`resume`), `payload_ref`, `timestamp` |
| **PausedRun** | A pause-mode halt awaiting resume | `halt_id`, `scope`, `paused_at`, `max_ttl`, `resumable_until` |
| **DrillResult** | A measured rehearsal outcome | `drill_id`, `platform`, `stop_time_ms` (p50/p95/p99), `survivors` (must be 0), `pass`, `hardware_note` |

## Example — a halt request (CLI)

```json
{
  "target": "agent:release-bot",
  "mode": "kill",
  "reason": "prod mutation observed; SIEM alert 4412",
  "deadline_ms": 1000
}
```

## Example — the receipt (proof-of-stop)

```json
{
  "schema": "agenthalt.receipt.v1",
  "halt_id": "hlt_01J...",
  "mode": "kill",
  "status": "complete",
  "trigger": { "source": "pagerduty", "principal": "ravi@corp", "reason_code": "siem_alert" },
  "subtree": {
    "root": "agent:release-bot",
    "members": ["run_a1", "run_a2", "mcp:fs-server", "proc:sh(8841)"],
    "lineage_verified": true
  },
  "confirmations": [
    { "layer": "process", "target": "run_a1", "status": "confirmed", "signed_by": "agentseatbelt" },
    { "layer": "process", "target": "run_a2", "status": "confirmed", "signed_by": "agentseatbelt" },
    { "layer": "credentials", "target": "grant:aws-deploy", "status": "confirmed", "signed_by": "agentkeys" },
    { "layer": "gateway", "target": "mcp:fs-server", "status": "unsupported", "note": "agentgate not deployed" }
  ],
  "refused_calls": { "count": 3, "first_at": "2026-11-14T02:31:07Z", "log_ref": "evt_..." },
  "survivors": [],
  "compensation": [
    { "kind": "record_written", "ref": "db:customers#8823", "reversible": false }
  ],
  "readout": {
    "unrevocable_grants": [ { "ref": "static:GH_PAT", "expires": "2026-12-01" } ],
    "queued_work": ["queue:deploy#77"],
    "downstream": ["agent:escalation-bot"],
    "siblings": []
  },
  "evidence_ref": "snap_01J...",
  "verifier_input": { "journal_head": "sha256:...", "adapter_versions": { "process": "0.1.0" } }
}
```

## Example — the halt event (emitted in the agentwatch schema)

```json
{
  "schema": "agentwatch.security_event.v1",
  "event_type": "halt.raised",
  "event_id": "evt_01J...",
  "halt_id": "hlt_01J...",
  "trigger": { "source": "pagerduty", "principal": "ravi@corp" },
  "target": { "agent": "release-bot", "scope": "subtree" },
  "mode": "kill",
  "reason_code": "siem_alert",
  "timestamp": "2026-11-14T02:31:05Z"
}
```

## Lifecycle

1. **Raise** — a trigger authenticates and submits `{target, mode, reason}` → a **Trigger** record is journaled.
2. **Resolve** — the target walks the lineage → a **Subtree** (+ its grants); missing edges are a loud
   `lineage_gap` finding, never a quiet guess.
3. **Record** — the **HaltState** is written to the store (synchronous; the choke now denies) → a **Halt** is
   journaled as `blocking`.
4. **Plan** — the deterministic **StopPlan** is derived (block-new first; suspend/revoke/snapshot parallel).
5. **Execute** — executor adapters cut their targets → **Executions**; enforcement points return signed
   **Confirmations** within the deadline.
6. **Snapshot** — the **EvidenceSnapshot** is written (parallel with 5, completed before any process
   destruction completes) and hash-chained.
7. **Emit** — the halt (+ trigger) is emitted as agentwatch events; refused calls log to the event stream.
8. **Receipt** — the **Receipt** is built from confirmations only; `survivors[]` non-empty ⇒ status
   `incomplete`; the **readout** and **compensation[]** complete it; journaled as `complete`/`incomplete`.
9. **Resume/lift** (pause mode / operator action) — a journaled state change with its own actor and reason;
   pause expiry auto-escalates to kill (RK-15).

## Storage layout (`.agenthalt/`)

```
.agenthalt/
  store/             # HaltState (the live kill state; local-first, fail-closed)
  lineage/           # append-only LineageEdge segments (hash-chained)
  halts/<id>/        # Halt, Subtree, StopPlan, Executions, Confirmations
  receipts/<id>.json # Receipt (offline-verifiable)
  evidence/<id>/     # EvidenceSnapshot + captured trace window (redacted)
  journal/           # append-only, hash-chained halt journal (anchored rotation)
  drills/            # DrillResults (measured numbers per release)
```

## Invariants

- **Single source of stop truth:** the store's HaltState is the only kill authority; every choke reads it.
- **Fail-closed:** store unreachable ⇒ deny high-impact actions; no path silently continues.
- **Confirmations only:** a receipt never reports a request as a stop; `incomplete` is a first-class status.
- **Snapshot-before-termination:** no process destruction completes before its evidence is captured.
- **Append-only record:** lineage edges and journal entries are hash-chained; any edit is detectable; a missing
  segment is a loud finding.
- **No reversal claims:** `CompensationItem.reversible` is always `false` at v0.1.0; the UI never offers "undo".
- **Idempotency:** the same halt re-raised returns the existing receipt; no interleaved states.
- **Provenance:** every receipt records adapter versions and the journal head, so an offline verifier can
  re-derive it (CUJ-24).
- **Path safety:** identifiers used in paths match `^[a-zA-Z0-9_-]+$`.
- **Secrets hygiene:** the snapshot's trace window is redacted per the security baseline; raw secrets never
  persist in receipts or the journal.
