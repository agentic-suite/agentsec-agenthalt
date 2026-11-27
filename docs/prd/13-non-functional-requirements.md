# PRD 13 — Non-Functional Requirements

**BLUF:** agenthalt's non-functionals are dominated by **speed** (≤1 s alert → full stop, measured) and
**fail-closed safety** (no path silently keeps the agent running). It must be **deterministic** (same halt
request + state ⇒ same stop plan), **portable** (harness-agnostic, local-first, macOS + Linux at v0.1.0),
**auditable** (tamper-evident journal + receipt), **honest** (confirmations, residual windows, compensation
lists), and cheap enough to drill in CI on every release.

**Status:** Draft — v0.1.0 (2026-11-14) · **Owner:** @deghosal-2026 · **Parent:** agentic-suite #209 · PRD #216

## Speed (primary)

- **Alert → full stop ≤ 1 s** in the chaos drill: halt-state visible to the dual choke, process tree suspended,
  revocation issued, evidence collection started. The **synchronous** portion is the choke write; everything
  else runs parallel within a **deadline** (default 1 s, configurable), and what misses the deadline reports
  honestly as pending/`incomplete` (RK-4).
- **Choke read latency**: the runtime/gateway check of halt state is a local read with a **short-TTL cache
  (seconds, never minutes)** — a multi-minute cache in front of a kill state is the category's known failure
  (a feature flag is not a kill switch).
- **Cold-start budgeted** (store load + adapter registration) and measured in the drill; p50/p95/p99 published
  per release on stated hardware (DD-29: measured numbers only).
- **Parallel fan-out** across executor adapters with per-adapter timeouts; a slow revoke API never serializes
  the stop.

## Determinism (primary)

- **Same halt request + same state ⇒ same stop plan**, always. The stop path contains **no ML, no randomness**;
  time and lineage are explicit inputs, never ambient.
- **Replayable**: a halt (target + mode + lineage snapshot + adapter versions) re-derives the same plan and the
  same receipt contents offline — the basis of the offline evidence bundle (CUJ-24, R21).
- **Documented semantics**: how each layer cut is sequenced and confirmed is published ([PRD 02](02-architecture.md));
  no proprietary "smart" ordering.
- Verified by an automated determinism test (re-run ⇒ identical plan unless a pin changed).

## Fail-closed safety (primary)

- **Any exception, unreachable store, adapter failure, or lineage gap ⇒ deny new high-impact actions** with a
  distinct `reason_code` (`halt_store_unavailable`, `adapter_failed`, `lineage_gap`).
- **The safe direction is always stopped.** The predecessor's availability-oriented fail-open stance
  (`ai-loopguard`) is deliberately inverted here ([PRD 10](10-feature-parity.md) P10).
- **Evidence is a side effect, not a gating dependency** — a snapshot failure never cancels the stop; it
  degrades the receipt honestly (`evidence: pending/failed`) and is a loud finding.
- The fail-closed contract is itself a CI test over a fuzzed failure matrix (CUJ-16).

## Reliability & failure modes

- A malformed config **refuses to load** (`agenthalt doctor` reports the exact key); the coordinator never
  starts with a broken configuration.
- **Every halt completes to a receipt**, even when layers fail: the receipt reports per-layer
  `confirmed`/`requested`/`unsupported`/`failed` — there is no "unknown" state after completion.
- **Idempotency**: duplicate trigger of the same halt returns the existing receipt; concurrent different halts
  compose by scope (a tighter scope wins within its subtree).
- Exit codes are always propagated (0 = clean stop, non-zero = incomplete/failed stop or error), `--ci` or not.
- **Manual fallback**: the runbook ships the raw per-layer commands an operator runs if agenthalt itself is down
  (PRD 06) — the control plane must not be a single point of failure for the ability to stop at all.

## Portability

- **Harness-agnostic by construction** — containment at process/credential/sandbox layers; the same stop for
  every harness, including zero-hook-surface ones (R5).
- **Local-first** (no service required for core function); the daemon is a local performance/reliability
  optimization, not a dependency; **CI-second** (the drill runs in CI); optional HTTP/MCP surfaces for remote
  triggers.
- **macOS + Linux at v0.1.0** (per-OS executor adapters; DD-17); Windows documented not-supported with a dated
  plan.
- Python 3.10+ core; no runtime dependency on a proprietary backend; each composed layer degrades independently
  and honestly (DD-18).

## Security

- **Trigger authentication** per path (HMAC/mTLS/interactive session) with replay protection (PRD 06).
- **Append-only, hash-chained** journal and lineage edges; anchored rotation; verification commands.
- **Signed receipts**: receipt entries are signed by the enforcement points that produced them; the offline
  verifier re-derives the chain.
- **Snapshot hygiene**: secrets in the captured trace window are redacted per the security baseline; a forensic
  artifact is not a secrets dump; strict identifier validation (`^[a-zA-Z0-9_-]+$`) before any path use.
- **Least-privilege composition**: agenthalt asks layers to act through their documented action surfaces; it
  never holds their credentials or bypasses their controls.

## Auditability

- Append-only halt journal (actor, scope, reason, timestamp, run IDs, mode, revoke status) with policy/trigger
  version per entry.
- **Tamper-evident**: hash chain + rotation anchors; verification proves unedited history; a missing segment is
  a loud finding.
- Halts + triggers emitted in the agentwatch schema; the refused-call log is written by the enforcement points.
- **Retention**: receipts and journal are retained per policy (default 90 days hot, archived thereafter); the
  evidence snapshot follows incident-response retention (configurable, exportable).

## Cost

- A halt is free; no per-call API cost on the default path.
- The drill is CI-cheap (local processes + fixtures); no cloud spend required to verify the product's core
  claim.
- Optional remote integrations (PagerDuty, Slack) use their free webhook surfaces; no paid dependency is
  required for any P0 requirement.

## Observability & self-check

- `agenthalt doctor` — environment/store/adapter sanity before you need it at 3 a.m., including the platform
  checks enrollment and the panic key depend on (Linux cgroup v2 delegation, macOS Accessibility).
- `agenthalt status [--halt <id>]` — live halt state + the 09:01 readout.
- `agenthalt prove --halt <id>` — receipt verification (online and offline).
- `agenthalt drill [--platform <os>]` — the measured rehearsal; CI job runs it per release.
- Metrics: stop-time percentiles, halts by trigger/mode, incomplete halts, unrevocable grants surfaced,
  paused-run count and age.

## Documentation

- Every receipt documents its halt id, trigger origin, layer versions, and evidence ref so an external party can
  re-derive the stop offline (CUJ-24). The receipt is the unit of documentation — if a responder cannot act on
  it, it is a bug.
