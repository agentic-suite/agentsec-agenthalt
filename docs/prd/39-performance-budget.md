# PRD 39 — Performance Budget (the 1000 ms doc)

**BLUF:** "≤1 s alert → full stop" is the product's headline number, so it gets a headline decomposition. This
document defines **what the clock measures** (trigger accepted → choke blocking ∧ subtree suspended ∧
revocations confirmed), the **per-phase budgets** (store write ≤50 ms, suspend ≤200 ms, revoke ≤400 ms, gateway
≤200 ms, snapshot start ≤150 ms — fanned out in parallel inside a 1000 ms deadline), the **reference
hardware** the claim is valid on, the **measurement discipline** (monotonic clocks, p95 over N, cold/warm,
CI artifact as the single source), and the **honesty rules**: a phase that misses its budget reports
`requested`, the halt reports `incomplete`, and the published number never leaves the CI artifact.

**Status:** Draft — v0.1.0 (2026-11-14) · **Owner:** @deghosal-2026 · **Parent:** agentic-suite #209 · PRD #216

## What the clock measures (the definition that makes the claim testable)

```
T_stop = t(choke blocks for scope) ∧ t(subtree suspended) ∧ t(revocations confirmed) − t(trigger accepted)
```

- **T_start:** trigger authenticated and accepted by the coordinator (auth cost is *in* the budget — a slow
  HMAC is our latency, not the caller's excuse).
- **T_stop (the claim):** the **safe state** — new actions denied at the choke, every enumerated member
  suspended, every revocable grant confirmed revoked.
- **Explicitly outside the clock (reported separately, never fudged):** full snapshot write (`T_evidence` —
  the *first chained segment* must commit inside the window; completion is async and the receipt reports
  `evidence: pending → written`), in-flight call cancellation (best-effort per layer, E17), and operator
  reaction time (upstream of us).
- Reconciliation with the #216 phrasing ("process frozen, creds dead, evidence written"): "evidence written" =
  first chained segment committed — the receipt's `evidence.status` distinguishes `written` from `pending`
  so no number ever borrows from an unfinished phase.

## Phase budgets (inside the 1000 ms deadline)

| Phase | Budget (p95) | Window | Notes |
|---|---|---|---|
| Trigger auth + journal write | ≤ 50 ms | synchronous | local append; journal-first is a correctness rule, not a perf cost ([PRD 16](16-trigger-catalogue.md)) |
| **Choke write → visible** | ≤ 50 ms | **synchronous — the hard guarantee** | the only phase that must *always* land; everything else degrades honestly |
| Subtree suspend (SIGSTOP/cgroup freeze) | ≤ 200 ms | parallel | per-OS executor adapters ([PRD 19](19-harness-compatibility.md)) |
| Revocation issue + confirm (agentkeys) | ≤ 400 ms | parallel | worst legitimate network phase — local broker first, issuer confirm may trail |
| Gateway terminate (agentgate) | ≤ 200 ms | parallel | absent in Wave 0 → `unsupported` in ≤ 1 ms, honestly |
| Sandbox egress block | ≤ 150 ms | parallel | with suspend, this closes the reach window |
| Snapshot first-segment commit | ≤ 150 ms | parallel | write-ahead of termination ([PRD 17](17-evidence-and-proof-format.md)) |
| **Deadline** | **1000 ms** | — | confirmations collected until deadline; missed ⇒ `requested` |

Sequencing per DD-05: the synchronous portion is the choke write (~50 ms); everything else is a parallel
fan-out with per-phase timeouts. **A slow revoke API never serializes the stop** (RK-4); it degrades one
confirmation to `requested` and the receipt says so.

## Reference hardware (what "≤1 s" means, on what)

| Class | Definition (pinned per release) | Legs |
|---|---|---|
| **Reference laptop** | Apple Silicon M-series, ≥16 GB (stated exactly in the CI artifact) | macOS leg, panic-key case |
| **Reference server** | stated cloud VM class (4 vCPU/8 GB) or CI runner equivalent | Linux leg, cgroup/eBPF cases |
| Drill artifact | platform string + kernel + agenthalt version + per-case p50/p95/p99 | the C-02 source ([PRD 31](31-claims-ledger.md)) |

Numbers do not migrate between hardware classes; a claim about a class cites that class's artifact
(DD-29: measured numbers only, no stopwatch readings, no cross-platform averaging).

## Measurement discipline

1. **Monotonic clocks** for all phase timestamps; wall-clock only for the journal's human-readable fields.
2. **Percentiles over N ≥ 100** runs per case per platform: p50/p95/p99 all published; the SLO binds **p95**
   ([PRD 36](36-observability-and-soc-pack.md)).
3. **Cold and warm both measured**: cold (first halt after daemon start) is reported separately — a cold-start
   budget exists ([PRD 13](13-non-functional-requirements.md)) and hides in warm averages otherwise.
4. **The drill is the only publisher**: `agenthalt_drill_stop_time_seconds` and the release artifact are the
   single source; hand-typed numbers fail the claims lint (C-02).
5. **No benchmark mode**: the drill runs the real pipeline against real local processes — a synthetic fast-path
   used for the published number is a forbidden claim (F-05 adjacent).

## Degradation and the honesty rules

| Event | Behavior |
|---|---|
| A phase misses its budget | `requested`, not `confirmed`; receipt may report `incomplete` if a member stays unconfirmed |
| Store write itself slow/unreachable | **The halt fails loudly (exit 3)** — the one phase with no honest degradation; fail-closed covers the fleet while the operator runs the manual fallback ([PRD 28](28-failure-mode-runbook.md) §7) |
| Enumeration exceeds budget (flood case) | deadline-bounded, honest `incomplete`, never a hang ([PRD 27](27-lineage-model.md) `test_enumeration_flood`) |
| Network phases (issuer confirm) trail | revocation `confirmed` when the issuer confirms; until then `requested` + residual window in the readout — the clock never *includes* a distant API, and never *claims* its effect |

## CI enforcement & SLO breach policy

- Every release job runs the catalogue per platform and writes the perf artifact; C-02/C-03 read it.
- **Breach = feature freeze**: a p95 stop-time breach or any survivor on the weekly CI drill freezes the next
  release to fixes until green (the error-budget policy, [PRD 36](36-observability-and-soc-pack.md)); the breach
  publishes in the release notes.
- Regression tracking: per-phase histograms compared release-over-release; a 20% p95 regression in any phase
  fails the perf gate even inside the deadline — the budget erodes visibly, not silently.

## Fleet headroom (v0.2.0+, not a v0.1.0 commitment)

Distributed store replication adds a replication hop to the choke write — the design reserves **150 ms of the
choke budget** for it and keeps the 1000 ms total unchanged (the honest answer is a *tighter* synchronous
window, not a bigger claim). Peer confirmation and dual-control authorization flows are **outside** T_stop by
definition (they precede the trigger's acceptance) and are budgeted separately in the v0.2.0 authorization spec.

## What would falsify this budget

- The choke write cannot hit ≤50 ms p95 on reference hardware ⇒ the store design is wrong (RK-4 escalation).
- Parallel fan-out cannot hold 1000 ms with a real issuer confirmation in the mix ⇒ the "creds dead inside the
  second" claim narrows to "creds requested inside the second, confirmed as reported" — a **claims-ledger
  revision** (C-02 wording), done in public, not snuck into the README.
