# PRD 26 — Receipt Schema & Examples

**BLUF:** The receipt (`agenthalt.receipt.v1`) is agenthalt's proof-of-stop artifact: a **structured,
enforcement-point-signed, offline-verifiable** record of what was stopped, what was revoked, what was refused,
what survived, what already landed, and what the stop could not reach. This document is its normative schema,
its status vocabulary, and four worked examples — the clean kill, the missing layer, the survivor, and the
SaaS-hosted partial halt. The schema is **append-only**: a v0.1.0 receipt verifies forever.

**Status:** Draft — v0.1.0 (2026-11-14) · **Owner:** @deghosal-2026 · **Parent:** agentic-suite #209 · PRD #216

## Schema v1 (normative)

```
agenthalt.receipt.v1
├─ schema           "agenthalt.receipt.v1"          (frozen; evolution = new optional fields only)
├─ halt_id          ULID
├─ mode             "pause" | "quarantine" | "kill"
├─ status           "complete" | "incomplete" | "partial-layer" | "failed"   (no "probably")
├─ trigger          { source, principal, channel?, reason_code?, incident_ref? }
├─ subtree
│   ├─ root         "<kind>:<id>"
│   ├─ members[]    [{ id, kind: run|proc|mcp|agent, confirmed: bool }]
│   ├─ grants[]     [credential refs held by members]
│   └─ lineage_verified   bool        (false ⇒ receipt says so — never claims completeness)
├─ confirmations[]  [{ layer: process|credentials|gateway|sandbox|hooks,
│                       target, status: confirmed|requested|unsupported|failed,
│                       signed_by, signature, note? }]
├─ refused_calls    { count, first_at, last_at, log_ref }    (written by enforcement points)
├─ survivors[]      [{ id, last_seen, why }]                (non-empty ⇒ status=incomplete)
├─ compensation[]   [{ kind, ref, observed_at, reversible: false }]   (always false at v1)
├─ readout
│   ├─ unrevocable_grants[]   [{ ref, expires?, window_note }]
│   ├─ queued_work[]         [refs the stopped agent had claimed]
│   ├─ siblings[]            [agents outside the subtree]
│   ├─ downstream[]          [agents the stopped agent handed work to]
│   └─ uncovered_routes[]    [network paths no composed layer reaches]
├─ evidence         { snapshot_ref, chain_head, status: written|pending|failed }
├─ mode_history[]   [{ at, mode, actor? }]                   (pause→quarantine→kill timeline)
├─ verifier_input   { journal_head, adapter_versions{}, halt_ref, trigger_ref, receipt_hash }
└─ timestamps       { raised_at, blocking_at, completed_at }  (RFC 3339 UTC, monotonic seq)
```

**Field rules**

- `confirmations[].status` is written **only** by the enforcement point that performed the cut (DD-04);
  `requested` never upgrades to a stop in any display.
- `survivors[]` is the receipts' conscience: non-empty forces `status=incomplete` — a schema-level invariant,
  not a UI choice.
- `compensation[].reversible` is a frozen `false` at v1; adding a `true` path later would require a new schema
  version and a forbidden-claim review ([PRD 20](20-standards-and-claims.md) §F).
- `readout.uncovered_routes` is mandatory honesty (E5/E8): what the stop did *not* reach is named, never
  omitted.

## Status vocabulary (exhaustive)

| Status | Meaning | Verifier output |
|---|---|---|
| `complete` | every member confirmed; zero survivors; no `failed` confirmations | `VERIFIED (complete)` |
| `incomplete` | survivor(s) or unconfirmed members at deadline | `VERIFIED (incomplete: <survivor ids>)` |
| `partial-layer` | stop complete for reachable members; ≥1 layer `unsupported` (e.g. no agentgate) | `VERIFIED (partial-layer: gateway)` |
| `failed` | the halt could not establish blocking at the choke | `VERIFIED (failed)` — plus the manual-fallback runbook pointer |

There is deliberately **no** status meaning "probably stopped," and no way to express success from requests.

## Example 1 — the clean kill (Demo 1)

```json
{ "schema": "agenthalt.receipt.v1", "halt_id": "hlt_01J", "mode": "kill", "status": "complete",
  "trigger": { "source": "webhook", "principal": "siem@corp", "reason_code": "siem_alert" },
  "subtree": { "root": "agent:release-bot",
    "members": [ { "id": "run_a1", "kind": "run", "confirmed": true },
                 { "id": "proc:sh(8841)", "kind": "proc", "confirmed": true } ],
    "grants": ["grant:aws-deploy"], "lineage_verified": true },
  "confirmations": [
    { "layer": "process", "target": "run_a1", "status": "confirmed", "signed_by": "agentseatbelt" },
    { "layer": "credentials", "target": "grant:aws-deploy", "status": "confirmed", "signed_by": "agentkeys" },
    { "layer": "sandbox", "target": "run_a1", "status": "confirmed", "signed_by": "agentseatbelt" } ],
  "refused_calls": { "count": 3, "first_at": "…T02:31:07Z", "last_at": "…T02:31:09Z", "log_ref": "evt_9" },
  "survivors": [],
  "compensation": [ { "kind": "record_written", "ref": "db:customers#8823", "reversible": false } ],
  "readout": { "unrevocable_grants": [], "queued_work": ["queue:deploy#77"],
               "siblings": [], "downstream": ["agent:escalation-bot"], "uncovered_routes": [] },
  "evidence": { "snapshot_ref": "snap_01J", "chain_head": "sha256:…", "status": "written" } }
```

## Example 2 — the missing layer (Wave-0 default, no agentgate)

Same as Example 1 except: `status: "partial-layer"`, one confirmation
`{ "layer": "gateway", "status": "unsupported", "note": "agentgate not deployed" }`, and the verifier prints
`VERIFIED (partial-layer: gateway)`. **The honest Wave-0 shape** (DD-18) — never padded, never hidden.

## Example 3 — the survivor

```json
{ "status": "incomplete",
  "survivors": [ { "id": "run_a3", "last_seen": "…T02:31:12Z", "why": "lineage edge missing at spawn" } ],
  "confirmations": [ …, { "layer": "process", "target": "run_a3", "status": "requested", "signed_by": null } ],
  "readout": { "uncovered_routes": ["direct:https://api.provider.example"], … } }
```

This receipt **fails the drill** (release blocker) and hands the responder a target list — the system's most
important output is its refusal to lie (RK-3).

## Example 4 — the SaaS-hosted partial halt (CUJ-22)

```json
{ "mode": "quarantine", "status": "partial-layer",
  "subtree": { "root": "agent:support-copilot", "lineage_verified": false,
    "members": [ { "id": "grant:zendesk-oauth", "kind": "agent", "confirmed": true } ] },
  "confirmations": [
    { "layer": "credentials", "target": "grant:zendesk-oauth", "status": "confirmed", "signed_by": "agentkeys" },
    { "layer": "process", "target": "vendor-hosted", "status": "unsupported",
      "note": "SaaS-hosted process not reachable by any composed layer" } ],
  "readout": { "unrevocable_grants": [ { "ref": "static:vendor-key", "expires": "2026-12-01" } ], … } }
```

The receipt states plainly: *we killed what we could reach; the vendor's process is out of our layers* (R19) —
the anti-over-claim posture as a schema field.

## Backward compatibility (the append-only rule)

- **Fields are only ever added, never repurposed.** A v0.1.0 verifier reads every future receipt; a future
  verifier reads every v0.1.0 receipt.
- New **optional** fields ship with a minor schema bump; semantic changes (status vocabulary, confirmation
  semantics) require a new schema id and a migration note (DD-31).
- Enforcement-point **signing keys** rotate via the release attestation bundle ([PRD 20](20-standards-and-claims.md) §E);
  old signatures stay verifiable against archived keys.

## Verification semantics (`agenthalt prove`, [PRD 17](17-evidence-and-proof-format.md))

1. Re-derive `receipt_hash`; check journal linkage (`halt_ref`, `trigger_ref`, `journal_head`).
2. Verify each confirmation signature against the enforcement point's published key.
3. Cross-check the evidence chain head.
4. Emit exactly one of: `VERIFIED (complete)` · `VERIFIED (incomplete: …)` · `VERIFIED (partial-layer: …)` ·
   `VERIFIED (failed)` · `TAMPERED (field: …)` — output designed to paste into an incident report.
