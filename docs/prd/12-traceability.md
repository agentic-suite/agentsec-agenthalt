# PRD 12 — Traceability

**BLUF:** Every v0.1.0 requirement traces to a critical user journey, a work-breakdown milestone, an acceptance
test, and its parity disposition. No requirement is orphaned and no absorbed capability is silently dropped.

**Status:** Draft — v0.1.0 (2026-11-14) · **Owner:** @deghosal-2026 · **Parent:** agentic-suite #209 · PRD #216

## Foundation milestone (M0)

M0 carries no new R-items; it establishes the coordinator, config, journal, and CLI surface every later milestone
builds on.

| Milestone | Foundation deliverable | Acceptance test |
|---|---|---|
| M0 | Coordinator skeleton, halt config model, halt journal (hash chain), CLI surface + reserved exit codes, fail-closed config loader, `agenthalt doctor` | `tests/test_cli_surface.py`, `tests/test_journal.py`, `tests/test_config.py`, `tests/test_doctor.py` |

## Requirement → CUJ → WBS → test → parity

| Req | Requirement (short) | CUJ | WBS | Acceptance test | Parity ([PRD 10](10-feature-parity.md)) |
|---|---|---|---|---|---|
| **R1** | Composed stop across every available layer, ≤1 s | CUJ-1, CUJ-2 | M1, M3 | Alert → full stop ≤ 1 s in the drill · `tests/test_m1_compose.py`, `tests/test_m3_drill.py` | New (the unowned primitive) |
| **R2** | Lineage containment — zero surviving descendants | CUJ-3, CUJ-7 | M2 | Post-halt network-call probe: zero · `tests/test_m2_lineage.py`, `tests/test_m2_subtree.py` | New (P17 principle) |
| **R3** | Evidence snapshot, hash-chained + timestamped | CUJ-8 | M4 | Snapshot written before termination; chain verifies · `tests/test_m4_snapshot.py` | Re-scoped (P19) |
| **R4** | Trigger sources (CLI, webhook, PagerDuty, Slack, panic key) | CUJ-11, CUJ-12 | M6 | Each trigger path fires + is journaled in the drill · `tests/test_m6_triggers.py` | New |
| **R5** | Zero-hook-surface containment (hostile harness) | CUJ-13 | M3 | Hooks-removed fixture fully contained · `tests/test_m3_hostile.py` | New |
| **R6** | Halt + trigger as agentwatch events | CUJ-14 | M5 | Events join on a common id; SOC test alarms · `tests/test_m5_events.py` | Delivered, superseded (P18) |
| **R7** | Pause/resume, 24 h integrity | CUJ-4 | M7 | 24 h wall-clock resume, no corruption · `tests/test_m7_pause.py` | New |
| **R8** | Halt store + dual choke + fail-closed | CUJ-16 | M1 | Store-down ⇒ deny high-impact; fuzzed failure matrix · `tests/test_m1_failclosed.py` | Inverted (P10) |
| **R9** | Lineage registry (append-only edges) | CUJ-3 | M2 | Edge deletion/poisoning detected · `tests/test_m2_edges.py` | New |
| **R10** | Proof-of-stop receipt (confirmations) | CUJ-9 | M4 | Unconfirmed descendant ⇒ `incomplete`; receipt verifies offline · `tests/test_m4_receipt.py` | New (P5) |
| **R11** | The 09:01 readout | CUJ-10 | M4 | Readout names survivors, grants, queued work · `tests/test_m4_readout.py` | Re-scoped (P14) |
| **R12** | Tamper-evident halt journal | CUJ-9, CUJ-14 | M0, M5 | Seeded edit detected; rotation anchors · `tests/test_journal.py`, `tests/test_m5_chain.py` | Delivered, extended (P5) |
| **R13** | Irreversibility honesty (compensation list) | CUJ-17 | M4 | Receipt lists landed side effects; no reversal claims · `tests/test_m4_compensation.py` | New (the honesty rule) |
| **R14** | CI chaos drill (measured; survivor = fail) | CUJ-15 | M3, M9 | Drill measures ≤1 s p95 in CI; survivor fails build · `tests/test_m3_drill.py`, CI job | New |
| **R15** | Graduated stops (pause/quarantine/kill) | CUJ-18 | M8 | Mode steps logged; escalation one command · `tests/test_m8_modes.py` | New (v0.2.0) |
| **R16** | Dead-man switches (budget/tamper/kernel; `ai-loopguard` triggers) | CUJ-19, CUJ-20 | M8 | Each trigger fires a halt with distinct reason_code · `tests/test_m8_deadman.py` | Delivered, re-pointed (P1, P2) |
| **R17** | Drills-in-a-box (partner runbooks) | CUJ-15 | M9 | Non-author runs the drill; pass/fail + time · `tests/test_m9_partner_drill.py` | New (v0.2.0) |
| **R18** | Halt authorization (RBAC, dual control, break-glass) | CUJ-21 | M10 | One approval ≠ fleet halt; break-glass auto-reverts · `tests/test_m10_authz.py` | Delegated gate (P9) |
| **R19** | Third-party/SaaS agent coverage | CUJ-22 | M10 | Per-agent coverage recorded; limits stated · `tests/test_m10_saas.py` | New (v0.2.0) |
| **R20** | Blast map | CUJ-23 | M10 | Residuals named with windows · `tests/test_m10_blastmap.py` | New (v0.2.0) |
| **R21** | Offline evidence bundle | CUJ-24 | M9 | Third party verifies without agenthalt installed · `tests/test_m9_offline.py` | New (v0.2.0) |
| **R22** | Halt-from-anywhere (Slack + agentinbox mobile) | CUJ-25 | M10 | Channel + principal journaled; anti-spoofing applies · `tests/test_m10_channels.py` | New (v0.2.0) |
| **R23** | Fleet halt policies ("auto-quarantine X") | later | later | Policy match raises a halt with rule id | New (v0.3.0) |
| **R24** | External halt attestation | later | later | Signed third-party drill result attachable | New (v0.3.0) |

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
| DD-13 kill first, modes v0.2.0 | R15, R7 |
| DD-14 dead-man v0.2.0 | R16 |
| DD-22 ≤1 s measured | R1, R14 |
| DD-24 append-only edges | R9 |
| DD-32 drill is release-blocking | R14 |

## WBS (to be authored)

The work breakdown will live at [`docs/wbs/v0.1.0/`](../wbs/v0.1.0/README.md) — the milestones above (M0–M10)
are the PRD-side proposal; the authored WBS is the operational source of truth and supersedes the milestone
column. Open decisions still to resolve are listed in [PRD 21](21-evidence-register-and-method.md) §PRD tensions.
