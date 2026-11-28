# PRD 12 — Traceability

**BLUF:** Every v0.1.0 requirement traces to a critical user journey, a work-breakdown milestone, an acceptance
test, and its parity disposition. No requirement is orphaned and no absorbed capability is silently dropped.

**Status:** Draft — v0.1.0 (2026-11-14) · **Owner:** @deghosal-2026 · **Parent:** agentic-suite #209 · PRD #216

## Foundation milestone (M0)

M0 carries no new R-items beyond the journal (R12); it establishes the CLI, config, enrollment surface, journal,
and `doctor` that every later milestone builds on.

| Milestone | Foundation deliverable | Acceptance test |
|---|---|---|
| M0 | CLI surface + reserved exit codes 0–5, fail-closed config loader, halt journal (hash chain), `doctor`, structured logs | `tests/test_cli_surface.py`, `tests/test_exit_codes.py`, `tests/test_config.py`, `tests/test_journal.py`, `tests/test_doctor.py`, `tests/test_logs.py`, `tests/test_packaging.py`, `tests/test_ci_workflow.py`, `tests/test_docs.py` (WBS 0.T) |

## Requirement → CUJ → WBS → test → parity

Milestones follow the authored WBS (`docs/wbs/v0.1.0/`, M0–M13). Named tests come from
[PRD 25](25-test-strategy.md) and [PRD 27](27-lineage-model.md); drill cases from [PRD 35](35-drill-pack-catalogue.md).

| Req | Requirement (short) | CUJ | WBS | Acceptance test | Parity ([PRD 10](10-feature-parity.md)) |
|---|---|---|---|---|---|
| **R1** | Composed stop across every available layer, ≤1 s | CUJ-1, CUJ-2, CUJ-5, CUJ-6, CUJ-7 | M3, M4 | drill `replit-stop` (≤1 s p95, PRD 39 clock) · `test_deadline_partial` · `test_layer_missing` | New (the unowned primitive) |
| **R2** | Lineage containment — zero surviving descendants | CUJ-3, CUJ-7 | M2, M3 | `test_spawn_race` · `test_double_fork_stays` · `test_drill_survivor` · drill `spawn-race` | New (P17 principle) |
| **R3** | Evidence snapshot, hash-chained + timestamped | CUJ-8 | M5 | `test_snapshot_canary` · `test_evidence_degrade` · drill `evidence-canary` | Re-scoped (P19) |
| **R4** | Trigger sources (CLI, webhook, PagerDuty, Slack, panic key) | CUJ-2, CUJ-11, CUJ-12 | M7 | `test_trigger_replay` · `test_panic_binding` · drills `panic-key`, `trigger-spoof` | New |
| **R5** | Zero-hook-surface containment (hostile harness) | CUJ-13 | M8 | drill `hostile-harness` (Demo 2) · self-tamper `tamper_hooks` | New |
| **R6** | Halt + trigger as agentwatch events | CUJ-14 | M7 | event-join test (C-06); SOC rule fires on `halt.*` | Delivered, superseded (P18) |
| **R7** | Pause/resume (+ basic quarantine), 24 h integrity | CUJ-4 | M9 | drill `pause-ttl` · 24 h leg (nightly + release candidate) | New |
| **R8** | Halt store + dual choke + fail-closed | CUJ-16 | M1 (fuzz matrix M11) | `test_failclosed_store` · fuzzed failure matrix · drill `store-down` | Inverted (P10) |
| **R9** | Lineage registry (append-only edges) + enrollment | CUJ-3 | M2 (enrollment CLI M0) | `test_edges_append_only` · `test_forged_edge_rejected` · `test_conflict_priority` · drill `edge-forgery` | New |
| **R10** | Proof-of-stop receipt (confirmations) | CUJ-9 | M4 (signing), M6 | `test_receipt_verify` · `prove` goldens · drill `receipt-tamper` | New (P5) |
| **R11** | The 09:01 readout | CUJ-10 | M6 | golden receipts ([PRD 26](26-receipt-schema-and-examples.md)) incl. `readout.coverage` | Re-scoped (P14) |
| **R12** | Tamper-evident halt journal | CUJ-9, CUJ-14 | M0, M7 | `test_journal_tamper` · `test_journal_degrade` · `journal verify` | Delivered, extended (P5) |
| **R13** | Irreversibility honesty (compensation list) | CUJ-17 | M6 | golden receipts: compensation present, `reversible: false` | New (the honesty rule) |
| **R14** | CI chaos drill (measured; survivor = fail) | CUJ-15 | M10 | full 12-case catalogue per platform; survivor gate fails the build | New |
| **R15** | Graduated escalation (escalate-on-act) | CUJ-18 | v0.2.0 — not in the v0.1.0 WBS | escalate-on-act tests | New (v0.2.0) |
| **R16** | External dead-man switches (budget/kernel; `ai-loopguard` triggers) | CUJ-19, CUJ-20 | v0.2.0 (self-tamper subset: M1, M2, M8 — DD-36) | each trigger fires with a distinct `reason_code`; drill `fleet-drill` | Delivered, re-pointed (P1, P2) |
| **R17** | Drills-in-a-box (partner runbooks) | CUJ-15 | v0.2.0 | non-author runs the drill; pass/fail + time | New (v0.2.0) |
| **R18** | Halt authorization (RBAC, dual control, break-glass) | CUJ-21 | v0.2.0 | `test_authz_dualcontrol` | Delegated gate (P9) |
| **R19** | Third-party/SaaS agent coverage | CUJ-22 | v0.2.0 | per-agent coverage recorded; limits stated | New (v0.2.0) |
| **R20** | Blast map | CUJ-23 | v0.2.0 | residuals named with windows | New (v0.2.0) |
| **R21** | Offline evidence bundle | CUJ-24 | v0.2.0 | third party verifies without agenthalt installed | New (v0.2.0) |
| **R22** | Halt-from-anywhere (Slack + agentinbox mobile) | CUJ-25 | v0.2.0 | channel + principal journaled; anti-spoofing applies | New (v0.2.0) |
| **R23** | Fleet halt policies ("auto-quarantine X") | later | v0.3.0 | policy match raises a halt with rule id | New (v0.3.0) |
| **R24** | External halt attestation | later | v0.3.0 | signed third-party drill result attachable | New (v0.3.0) |

## CUJ → requirement (reverse)

| CUJ | Serves |
|---|---|
| CUJ-1 Stop one runaway agent | R1, R2, R8, R10 |
| CUJ-2 Halt everything | R1, R12, R18 |
| CUJ-3 Contain the lineage | R2, R9, R10 |
| CUJ-4 Pause and resume | R7 |
| CUJ-5 Kill the credentials | R1, R10, R11 |
| CUJ-6 Disconnect at the gateway | R1, R8 |
| CUJ-7 Freeze the sandbox | R1, R2, R5 |
| CUJ-8 Preserve the evidence | R3 |
| CUJ-9 Verify the stop | R10, R12 |
| CUJ-10 Read the 09:01 readout | R11, R20 |
| CUJ-11 Trigger from an alert | R4 |
| CUJ-12 Panic key | R4 |
| CUJ-13 Zero-hook-surface harness | R5 |
| CUJ-14 Halt as a first-class event | R6, R12 |
| CUJ-15 Run a drill | R14, R17 |
| CUJ-16 Fail closed | R8 |
| CUJ-17 Irreversibility honesty | R13 |
| CUJ-18 Graduate a stop | R15 |
| CUJ-19 Dead-man: budget | R16 |
| CUJ-20 Dead-man: tamper | R5, R16 |
| CUJ-21 Authorize the halt | R18 |
| CUJ-22 Halt a third-party agent | R19 |
| CUJ-23 Blast map | R11, R20 |
| CUJ-24 Prove a halt offline | R21 |
| CUJ-25 Halt from anywhere | R22 |

## Decisions → requirements

| Decision | Enables |
|---|---|
| DD-02 halt store + dual choke | R1, R8, R6 |
| DD-03 fail-closed | R8, R14 |
| DD-04 confirmations | R10, R11 |
| DD-05 block-new-first | R1, R3 |
| DD-06 hooks never load-bearing | R5 |
| DD-09 agentwatch event, no new protocol | R6 |
| DD-10 snapshot before termination | R3 |
| DD-11 irreversibility stated | R13 |
| DD-13 rungs at v0.1.0, graduation v0.2.0 | R7, R15 |
| DD-14 external dead-man v0.2.0 | R16 |
| DD-22 ≤1 s measured | R1, R14 |
| DD-24 append-only edges | R9 |
| DD-32 drill is release-blocking | R14 |
| DD-36 self-tamper triggers at v0.1.0 | R5, R8, R9 (WBS 1.6, 2.6, 8.2) |
| DD-37 pause TTL 24 h | R7 |
| DD-38 enrollment | R9, R2 |
| DD-39 status precedence | R10 |
| DD-40 self-attestation labelled | R10 |
| DD-41 TOML config | — (M0 foundation) |
| DD-42 unknown config keys rejected | R8 (fail-closed) |
| DD-43 strictest mode wins | R8 |
| DD-44 same-user store, tamper-detected until M2 | R8, R12 |
| DD-45 built-in egress fallback | R1, R7 |

## WBS

The authored WBS lives at [`docs/wbs/v0.1.0/`](../wbs/v0.1.0/wbs-v0.1.0-index.md) (M0–M13). It is the operational
source of truth for milestones; this document is the requirement-side source of truth, and the milestone column
above is kept in sync with it. Open decisions are tracked in [PRD 21](21-evidence-register-and-method.md)
§Open decisions register. Risk → milestone and claim → milestone maps live in the WBS index.
