# PRD 25 — Test Strategy

**BLUF:** agenthalt is a **verification product** — testing *is* the product. The strategy is a five-level
pyramid: **unit** (pure logic), **adapter contract** (each layer's fake must behave like the real one),
**integration** (a live subtree on each OS), the **chaos drill** (the measured, release-blocking proof), and the
**self-halt adversarial pack** (attack the stop itself). Plus two cross-cutting matrices: **failure injection**
(every failure mode of [PRD 13](13-non-functional-requirements.md) is fuzzed) and the **platform × harness**
field matrix. A capability that isn't under one of these levels doesn't ship.

**Status:** Draft — v0.1.0 (2026-11-14) · **Owner:** @deghosal-2026 · **Parent:** agentic-suite #209 · PRD #216

## The pyramid

| Level | What it proves | Gate |
|---|---|---|
| **L1 — Unit** | Pure logic: subtree resolution, mode-ladder semantics, receipt assembly, chain math, TTL/expiry, idempotency, compensation-list construction | Every PR |
| **L2 — Adapter contract** | Each executor/trigger adapter against a **contract fake**: the fake enforces the adapter's documented response shape (`confirmed/requested/unsupported/failed`), signatures, and timeouts | Every PR |
| **L3 — Integration** | A live spawned subtree (parent → 2 children → MCP child → shell) per OS: raise → resolve → block → suspend → snapshot → receipt, on real processes | Every PR (macOS runner), per-release (Linux) |
| **L4 — Chaos drill** (`agenthalt drill`) | The measured end-to-end: alert → full stop ≤1 s p95, zero surviving descendants, receipt `complete`; the **release gate** (R14, [PRD 07](07-success-metrics.md)) | Per release; a survivor fails the build |
| **L5 — Self-halt pack** | The [PRD 06](06-security-baseline.md) adversarial sub-matrix: halt suppression, edge deletion/poisoning, trigger spoof/replay, receipt forgery, journal tamper, snapshot destruction | Per release; a hit blocks the release, misses published |

## Golden fixtures (deterministic regression)

- **Golden receipts**: named scenarios (clean kill; missing gateway; survivor; SaaS partial — see
  [PRD 26](26-receipt-schema-and-examples.md)) with pinned expected receipt contents (minus timestamps/ids).
- **Golden plans**: target graph + mode ⇒ expected StopPlan ordering (block-new-first, DD-05).
- **Golden journals**: a seeded sequence of raises/lifts/resumes ⇒ expected chain hashes.
- A PR that flips a golden (e.g., a "requested" that became "confirmed") fails the build with the exact
  fixture — the same discipline as agentpolicy's golden decisions (R22 there).

## Failure-injection matrix (the fuzzed spine)

Every row is a CI test; **no failure mode silently allows** ([PRD 13](13-non-functional-requirements.md)):

| Injected failure | Expected behavior | Test |
|---|---|---|
| Halt store unreachable | Choke **denies** high-impact actions; distinct `reason_code=halt_store_unavailable` | `test_failclosed_store` |
| Adapter timeout (slow revoke API) | Step misses deadline ⇒ `requested`, receipt `incomplete` at that target; others unaffected | `test_deadline_partial` |
| Agentgate absent (Wave-0 default) | Gateway step `unsupported`; receipt `partial-layer`; rest completes | `test_layer_missing` |
| Lineage edge missing / deleted | `lineage_gap` finding; drill survivor-detector catches the descendant; loud, never quiet | `test_lineage_gap` |
| Snapshot collector crash | Stop still completes; receipt `evidence: failed`; loud finding; never cancels the stop | `test_evidence_degrade` |
| Journal write fails | Halt proceeds; degraded mode is itself journaled where possible; manual-fallback flagged | `test_journal_degrade` |
| Duplicate trigger (same halt) | Idempotent: existing receipt returned, no state interleave | `test_idempotency` |
| Concurrent different halts | Tighter scope wins within its subtree; no corruption | `test_concurrent_scopes` |
| Panic key from non-interactive context | Rejected + journaled; no halt | `test_panic_binding` |
| Trigger replay (stale webhook) | Rejected within replay window; journaled | `test_trigger_replay` |
| Fuzzed malformed inputs (target/mode/ids) | ConfigError or deny — never a crash, never a silent allow | property tests |

## Platform matrix

| Leg | Runner | Must-pass |
|---|---|---|
| **macOS** | dev machine + CI macOS runner | process-group suspend semantics; panic key; Demo 1/2/5 |
| **Linux** | CI container + (where deployed) agentkernel leg | cgroup freeze; eBPF kill trigger wiring; Demo 1/2/4 |
| **Windows** | not supported at v0.1.0 (DD-17) | the *absence* is tested: install surfaces a clear not-supported message |

## Harness matrix (what "compatible" means — [PRD 19](19-harness-compatibility.md))

| Harness | Drill leg at v0.1.0 |
|---|---|
| Claude Code | full drill (primary) |
| Codex CLI | full drill (primary) |
| Gemini CLI | layer-set drill leg |
| Cursor | layer-set as headless allows; else covered-by-construction, listed honestly |
| Copilot (agent mode) | documented lower-layer only — **never claimed as tested** |

## CI gates & release blockers

1. L1–L3 green on every PR; L4 drill + L5 pack green on the release commit.
2. Drill number (p50/p95/p99 stop time) published from CI into the release artifact — measured, never assumed
   (DD-29).
3. Golden flip ⇒ build fails naming the fixture.
4. Survivor anywhere ⇒ build fails (this is the product's one unforgivable defect class, RK-3).
5. Claims linter ([PRD 31](31-claims-ledger.md)) green on docs/README changes.
6. The 24 h pause/resume leg (R7) is too long for per-PR CI: it runs nightly and on the release candidate, and
   its latest green run is attached to the release artifact.

## Test-data discipline

- Fixtures use synthetic credentials only; snapshot redaction is *tested* by planting a canary secret and
  asserting it never persists (PRD 06).
- Drill hardware is stated in every published number; numbers don't migrate between machines silently.
- The demo agents ([PRD 22](22-demo-scenarios.md)) double as integration fixtures — one code path, no demo-only
  magic.
