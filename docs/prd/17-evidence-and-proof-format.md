# PRD 17 — Evidence & Proof Format

**BLUF:** Two artifacts leave every halt: the **EvidenceSnapshot** (the preserved scene — trace window, process
tree, open connections, hash-chained and timestamped) and the **Receipt** (the proof-of-stop — confirmations
signed by enforcement points, the refused-call log, survivors, the compensation list, the readout). Both are
**documented, open formats** usable in incident response and legal contexts; both verify **offline** without
installing agenthalt; neither ever claims more than it can prove.

**Status:** Draft — v0.1.0 (2026-11-14) · **Owner:** @deghosal-2026 · **Parent:** agentic-suite #209 · PRD #216

## The EvidenceSnapshot (what the scene was)

**Captured on halt, before termination** (DD-10 — the stop must not destroy the scene it preserves):

| Component | Contents | Source |
|---|---|---|
| **Trace window** | The agentwatch event window for the subtree (tool calls, decisions, asks) — secrets redacted per the security baseline | agentwatch |
| **Process tree** | The resolved lineage: every run/process in the subtree, parent→child edges, spawn sources | lineage registry + process adapter |
| **Open connections** | Established sockets at halt time (local/remote endpoints, owning process) | process/sandbox adapter |
| **Credential inventory** | Grants held by subtree members, with revoke status at snapshot time (revoked / expiring / unrevocable) | agentkeys |
| **Halt context** | Trigger (actor, channel, reason), mode, adapter versions, timestamps | agenthalt |

**Format (v1):**

- `snapshot.json` — the structured scene (schema `agenthalt.evidence.v1`, versioned; the schema is append-only —
  a v0.1.0 snapshot parses forever).
- `chain.jsonl` — each snapshot is an entry in a local hash chain: `{ seq, prev_hash, entry_hash, timestamp }`;
  the chain head is **anchored at every rotation** (signed local anchor, optionally remote-timestamped) so
  truncate-and-rebuild is detectable, not just in-segment edits.
- `manifest.json` — content hashes of every file in the bundle; the manifest hash appears in the journal.

**Rules:**

- **Redaction before persistence** — raw secrets in the trace window are replaced with typed placeholders
  (`secret:aws_key[redacted]`) + counts; the raw values never land in the snapshot (PRD 06).
- **Exportable** — `agenthalt evidence export --halt <id>` emits the bundle (snapshot + chain segment + manifest)
  as a single tarball with detached hashes; a third party can verify it.
- **Retention** — incident-response retention (configurable; default 90 days hot then archived); each archived
  segment commits to the prior segment's head; a missing segment is a loud finding, never a quiet gap.

## The Receipt (proof that it stopped)

The receipt is the answer to *"did the stop actually stop it?"* — built **only from confirmations**
(DD-04), never from requests:

| Section | Contents | Honesty rule |
|---|---|---|
| `subtree` | Root, members, `lineage_verified` | An unverifiable lineage says so; it never claims completeness |
| `confirmations[]` | Per layer × target: `confirmed` / `requested` / `unsupported` / `failed`, each signed by the enforcement point that produced it | `requested` is never rounded up to a stop |
| `refused_calls` | Count + first/last timestamps + event-stream ref of calls the choke denied post-flip | Written by the enforcement points, not narrated by the agent |
| `survivors[]` | Any member unconfirmed at deadline | Non-empty ⇒ receipt status is `incomplete` — **never** `done` |
| `compensation[]` | Side effects that already landed (kind, ref, `reversible: false`) | The no-undo record; the receipt never offers reversal |
| `readout` | Unrevocable grants + residual windows, queued work, siblings, downstream agents | The 09:01 answer; what the stop did *not* reach is named |
| `verifier_input` | Journal head, adapter versions, halt/trigger ids | Everything an offline verifier needs |

**Status vocabulary:** `complete` (all members confirmed, no survivors) · `incomplete` (survivors or
unconfirmed members — the receipt says which) · `partial-layer` where a composed layer was `unsupported`
(e.g. agentgate not deployed — DD-18) · `failed` (blocking never established). When several apply, the worst
wins: `failed` > `incomplete` > `partial-layer` > `complete` (DD-39, [PRD 26](26-receipt-schema-and-examples.md)).
There is **no** status that means "probably stopped."

## Offline verification (CUJ-24)

```
agenthalt prove --receipt receipt.json --evidence bundle.tar.gz
```

- **Re-derivation:** the verifier recomputes each confirmation's signature against the enforcement points'
  published keys, re-checks the evidence chain segment, and re-derives the journal head — **without agenthalt
  installed** (a standalone verifier script ships in the bundle).
- **Binding:** the receipt is hash-bound to `halt_id`, the trigger record, and the evidence manifest; a receipt
  transplanted onto another halt fails verification.
- **Result:** `VERIFIED (complete)` / `VERIFIED (incomplete: 1 survivor: run_a3)` / `TAMPERED` — the verifier's
  output is designed to be pasted into an incident report.
- A third party (an auditor, a partner, a court reviewer) can check a stop with no trust in the operator's
  environment beyond the enforcement points' published keys.

## Alignment to the ecosystem standards

- The **agentwatch security-event schema** carries the halt + trigger events; the snapshot references the
  event stream by ids, so evidence joins telemetry on common keys (R6).
- The **hash-chained, timestamped evidence format** is the ecosystem's documented forensic format (PRD #216
  "Standards it must meet") — the same chain pattern as the agentpolicy decision log and the agentwatch record
  chain, so an auditor learns one verification model.
- Timestamps are RFC 3339 UTC with monotonic sequence numbers; chain anchoring is optional-remote
  (RFC 3161-style timestamping) where orgs want it.

## What the artifacts never claim

- Never `guaranteed zero descendants` — the receipt says what was **verified** (no post-halt call observed in
  the drill window).
- Never "rollback" — `compensation[]` exists precisely because there is no undo (R13).
- Never silent gaps — `unsupported` layers, unverifiable lineage, and pending evidence are first-class fields,
  not omissions.
- Never raw secrets — redaction precedes persistence, everywhere (PRD 06).

## Open questions

- **Remote anchoring default** — local anchor only (default) vs. RFC 3161 remote timestamping (opt-in)?
  Hypothesis: local default, remote opt-in for high-assurance deployments (needs design-partner input).
- **Snapshot encryption at rest** — encrypt the evidence dir by default with a local key? (Ties to the security
  baseline; hypothesis: yes for the trace window, no for the receipt.)
- **Third-party key publication** — where do enforcement-point verification keys live for offline verifiers?
  (Hypothesis: in the release attestation bundle; part of PRD 20's ladder.)
