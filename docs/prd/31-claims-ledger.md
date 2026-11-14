# PRD 31 — Claims Ledger

**BLUF:** A security product's marketing is part of its attack surface: every public claim is either
**backed by a named, CI-generated artifact** or it doesn't ship. This ledger is the machine-checkable registry:
one row per allowed claim — exact wording, required proof artifact, owner, cadence — plus the forbidden list and
the linter rules. Same discipline as the agentdrill `claims-ledger` pattern, applied to agenthalt's
claims-heavy category (a field where competitors ship "kill switch" labels on unexercised buttons).

**Status:** Draft — v0.1.0 (2026-11-14) · **Owner:** @deghosal-2026 · **Parent:** agentic-suite #209 · PRD #216

## The ledger (allowed claims)

| ID | Allowed wording (exact) | Required proof artifact | Owner | Cadence |
|---|---|---|---|---|
| C-01 | "Composes a stop across process, credential, gateway, and sandbox layers" | Compatibility table ([PRD 19](19-harness-compatibility.md)) naming per-layer version + exercised status, CI-generated | release | per release |
| C-02 | "Alert → full stop in ≤1 s" **(only with the drill artifact on stated hardware)** | CI drill output: p50/p95/p99 + hardware note | release | per release (number refreshed from CI, never hand-edited) |
| C-03 | "Zero surviving descendants **verified in the drill**" | Drill survivor-detector result (`survivors: 0`) | release | per release |
| C-04 | "Proof-of-stop receipt built from enforcement-point confirmations" | `prove` golden cases ([PRD 26](26-receipt-schema-and-examples.md)) + signature tests | security | per release |
| C-05 | "Works on harnesses with zero hook surface" | Hostile-harness fixture pass (Demo 2 / drill leg) | release | per release |
| C-06 | "Halt and trigger events in the open agentwatch security-event schema" | Event-join test (halt ⇄ record on common id) | eng | per release |
| C-07 | "Hash-chained, timestamped, offline-verifiable evidence" | Chain-verification test + `prove` offline case | security | per release |
| C-08 | "Aligned to the capability sets of H.R. 9917 / UK NCSC / EU AI Act Art. 14" **(alignment, never compliance)** | [PRD 29](29-regulatory-crosswalk.md) rows, each with its capability evidence | owner | per release + on regulatory movement |
| C-09 | "Pause/resume with full context" | 24 h wall-clock test output | eng | per release |
| C-10 | "Absorbs the `ai-loopguard` halt-trigger class" | [PRD 10](10-feature-parity.md) disposition table (delivered/delegated/waived, complete) | owner | per release |
| C-11 | "Free forever: all modes, receipts, verification, and drills — Apache-2.0" | LICENSE + [PRD 24](24-pricing-and-packaging-thesis.md) product law | owner | static |
| C-12 | "Every failure mode fails closed" | Fuzzed failure-injection matrix green ([PRD 25](25-test-strategy.md)) | security | per release |

## Forbidden claims (never, in any material)

| ID | Forbidden wording | Why |
|---|---|---|
| F-01 | "Stops any agent, anywhere" | It stops what the composed layers reach; the readout states the rest (R19) |
| F-02 | "Undoes / rolls back agent actions" | No undo exists (R13); the category's core lie |
| F-03 | "Guarantees zero survivors" | Verified-in-drill is the ceiling of honesty; guarantees are for ads |
| F-04 | "H.R. 9917 / NCSC / Art. 14 **compliant**" | Those instruments bind operators/providers, not tools (RK-18) |
| F-05 | "Sub-second" without hardware/method | DD-29: measured numbers only |
| F-06 | "Detects rogue agents" | agenthalt detects nothing (DD-07) |
| F-07 | "Court-admissible evidence" | Courts decide admissibility; we provide the documented format |
| F-08 | "Unhackable stop / tamper-proof" | Tamper-*evident* is the claim; "proof" against future attacks is not |

## Linter rules (CI-enforced)

A machine-readable registry (`claims.yaml`) drives a docs/README linter in CI:

1. Every public capability sentence maps to a **C-id** with a green artifact; unmatched capability sentences
   fail the lint ("claim without ledger entry").
2. Forbidden phrases are matched as **literal strings + close variants** across README, docs, and release
   notes; a hit fails the build with the F-id.
3. Numeric claims (C-02) are **read from the CI artifact**, not the repo — hand-typed numbers fail.
4. The compatibility table and coverage matrix must carry a **generated-at** stamp; an unstamped table fails.
5. Ledger rows without an artifact for two consecutive releases are **demoted to forbidden** automatically
   (stale proof = no proof).

## Ownership & review

- **Owner column** names the role responsible for the artifact existing at each release (release manager,
  security, or project owner per row).
- The ledger is reviewed with the coverage-matrix regeneration ([PRD 20](20-standards-and-claims.md) §G) and on
  any RK-18 trigger (regulatory movement, a competitor claim war, a field miss).
- **A field miss against a C-claim is a Sev-1**: the claim is pulled from public material *that day*, the miss
  is disclosed with the artifact trail, and the release-blocking review follows ([PRD 28](28-failure-mode-runbook.md)
  escalation tree). Claims don't wait for the next release cycle to become honest.
