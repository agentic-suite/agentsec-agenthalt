# PRD 07 — Success Metrics

**BLUF:** agenthalt succeeds when an operator can **stop a live agent and prove it stopped** — one command,
**≤ 1 second** from alert to full stop (choke blocking, subtree suspended, revocable credentials confirmed dead,
first evidence segment committed — [PRD 39](39-performance-budget.md)), **zero surviving
descendants**, and a receipt a third party can verify. The headline metric is not "switch shipped" — it is
**measured, CI-verified stop time and containment**, plus the adoption of the **drill** (a switch nobody has
pulled is a label on a box). Anti-metrics: no false success, no rollback theater, no single-layer claims.

**Status:** Draft — v0.1.0 (2026-11-14) · **Owner:** @deghosal-2026 · **Parent:** agentic-suite #209 · PRD #216

## Outcome metrics

| Metric | Target | Why it is the right metric |
|---|---|---|
| Alert → full stop | **≤ 1 s** in the chaos drill (the [PRD 39](39-performance-budget.md) clock: choke blocking, subtree suspended, revocable grants confirmed, first evidence segment committed), measured in CI every release | The ecosystem's #1 success criterion (#216); "continuously verified, not just at launch" |
| Containment completeness | **zero surviving descendants** make a network call post-halt (verified in the drill) | Stop is a graph operation; the drill tests the graph, not the parent |
| Stop-plan correctness | **100%** on the acceptance matrix (scope × mode × layer × failure injection) | A deterministic control plane — no "usually stops" |
| Proof integrity | **100%** of halts return a receipt built from confirmations; an unconfirmed descendant reports `incomplete` | The category fudges with requests; agenthalt's differentiator is confirmations (R10) |
| Halt reliability | **zero failed halts** across a release cycle of drills | The #216 success metric; a halt that fails once is a runbook lie forever |
| Trigger coverage | each trigger path (CLI/webhook/PagerDuty/Slack/panic key) **tested in drills** | R4; a trigger that only works in the README is not a trigger |
| Zero-hook-surface containment | the hostile-harness fixture (hooks removed) is still fully contained | R5 — the Plugin4Shell case; the reason containment is below-harness |
| Pause/resume integrity | a paused session resumes with **full context, no corruption, after 24 h** | R7; pause that corrupts state is a stop with extra steps |
| Evidence acceptance | the snapshot is accepted as a **forensic artifact** in a dry-run incident review (tamper-evident, third-party verifiable) | R3; the incident record must survive the incident |
| Event visibility | **100%** of halts + triggers emitted in the agentwatch schema; a SOC test alarms on a halt | R6; a stop the SOC cannot see did not formally happen |
| Fail-closed coverage | **0** failure modes that silently allow | The safety spine (CUJ-16); one fail-open path invalidates the product |
| Drill adoption (partners) | halts appear in **real partner runbooks**; a non-author runs `agenthalt drill` | Operational adoption (#216); the honesty moat |
| Time to first halt | **< 5 min** from `pip install` to a successful drill halt on a demo agent | Adoption friction gates the Wave-0 demo ("one harness, all four capabilities, 15 minutes") |
| Irreversibility honesty | **100%** of receipts carry a compensation list; **0** claims of reversal | R13 — the category's biggest lie, refused |

## Release gate (v0.1.0)

A release is not "done" unless:

1. The chaos drill passes in CI: alert → full stop **≤ 1 s**, measured, on the supported platforms (R1, R14).
2. Lineage containment is proven: **zero surviving descendants** make a network call post-halt (R2, CUJ-3).
3. The evidence snapshot is written before termination, hash-chained, and verifies offline (R3, CUJ-8).
4. Every trigger path fires and is journaled (R4, CUJ-11/12).
5. The hostile-harness fixture (hooks removed) is still contained (R5, CUJ-13).
6. Halts + triggers are emitted in the agentwatch schema and join on a common id (R6, CUJ-14).
7. Pause/resume survives the 24 h wall-clock test (R7, CUJ-4), run on the release candidate (and nightly), not
   per PR.
8. The halt store fail-closed contract holds under the fuzzed failure matrix (R8, CUJ-16).
9. Every halt returns a receipt built from confirmations; an unconfirmed descendant reports `incomplete` (R10).
10. The readout answers the 09:01 question with live grants, queued work, siblings, downstream (R11, CUJ-10).
11. The journal verifies as an unbroken chain; a seeded edit is detected (R12).
12. The self-halt adversarial pack passes with zero crafted escapes (PRD 06); misses are published, not hidden.
13. The compatibility table (harness × layer × version) is published and honest — including "not supported" rows.
14. The standards/regulatory coverage matrix (OWASP ASI, EU AI Act Art. 14, NCSC guidance, H.R. 9917 capability
    set) is regenerated from the pack tags, not hand-edited (PRD 20).
15. A non-author completes a drill in a user test (CUJ-15) — someone who did not build agenthalt — running the
    [PRD 34](34-design-partner-evaluation-guide.md) week-1 kit, and the field-test report is written from that run.

## Anti-metrics (what we refuse to optimize)

- **"Kill switch" as a marketing label** — the number is the drill, not the badge.
- **False success** — never report `done` on a request; never hide a survivor behind a green status.
- **Rollback theater** — never imply an undone action; the compensation list exists because there is no undo.
- **Single-layer shortcuts** — never claim a stop one layer cannot deliver ("gateway-revoked ⇒ stopped").
- **Stop-time cherry-picking** — the published number is the CI drill's p95/p99 on the stated hardware, not a
  best-case demo.
- **Halt count** — more halts is *not* better; a fleet that halts constantly is mis-scoped, and the readout data
  should say so.

## Instrumentation of success

- Every receipt links its `halt_id`, lineage snapshot, trigger event, and evidence ref — the receipt is the unit
  of review: if a responder cannot act on it, it is a bug.
- The drill's measured stop-time percentiles publish with each release (measured, never assumed).
- The refused-call log is written by the enforcement points, not narrated by the agent.
- The compatibility table and the coverage matrix regenerate from CI, not by hand.
- Partner drill results (pass/fail + time) are the adoption funnel, tracked per release.
