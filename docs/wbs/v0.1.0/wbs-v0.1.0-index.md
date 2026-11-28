# WBS — agenthalt v0.1.0 (Index)

**BLUF:** agenthalt v0.1.0 delivers the **composed stop**: the halt store + dual choke + fail-closed spine, the
lineage registry + subtree containment, the four executor adapters (process, credential, gateway, sandbox), the
hash-chained evidence snapshot, the proof-of-stop receipt + the 09:01 readout, the trigger set, zero-hook-surface
containment, pause/resume, and the **release-blocking CI chaos drill (≤ 1 s, zero survivors)** — plus the
world-class additions (performance budget, observability + SOC pack, privacy/data-handling, claims ledger,
regulatory crosswalk). **Fourteen milestones (M0–M13)** across **seven detail files**; **field tests (M12) and
release readiness (M13) are last.**

> **Milestone ranges by intent:** **M0–M11** = the v0.1.0 core (P0 requirements R1–R14) · **M12–M13** = field
> tests + release. The WBS builds the whole v0.1.0 set to one release. **This WBS supersedes the PRD-side
> milestone column in [PRD 12](../../prd/12-traceability.md)** — it renumbers and expands (M0–M10 → M0–M13) and
> is the operational source of truth; the PRD remains the requirement-side source of truth. v0.2.0 work
> (graduated modes R15, dead-man R16, drills-in-a-box R17, authorization R18, SaaS coverage R19, blast map R20,
> offline bundles R21, halt-from-anywhere R22) is **out of scope here** and tracked in [PRD 09](../../prd/09-roadmap.md).

## Standard milestone exit criteria (applies to EVERY milestone)

Every milestone is worked in this order:

1. **Design docs written first** — the milestone's `.D0` work item opens it (design + reference docs for the
   subsystem, written before code).
2. **Implement** the milestone's work items (one ticket at a time: test first (RED) → implement (GREEN)).
3. **Close with the standing gates:**
   - [ ] **All tests pass** (`make test`) — the `.T` work item
   - [ ] **Coverage ≥ 95%** (enforced in CI) — the `.C` work item
   - [ ] **Lint strict clean** — `ruff` zero violations; `mypy --strict` clean — the `.L` work item
   - [ ] **Code review complete** — findings in [codereview-log.md](codereview-log.md), all resolved — `.CR`
   - [ ] **Docs updated** — design/reference docs + the [PRD 12](../../prd/12-traceability.md) requirement → test
     row moves with the work — `.D`
   - [ ] **Committed & pushed** — the work is on the feature branch — `.CI`
   - [ ] **WBS updated** — a dated checkpoint (commit refs + gate result) appended to the Progress section — `.W`

> Every milestone therefore carries **eight standing gate work items** — `.D0` design · `.T` tests · `.C`
> coverage · `.L` lint/types · `.CR` review · `.D` docs · `.CI` commit · `.W` WBS — in addition to its
> implementation items.

## Standard milestone closure (applies to EVERY milestone)

A milestone is **closed** only when all of these hold:

1. **Implemented** — every work item done; no "core slice", no partials.
2. **Tests green** — the milestone's tests pass, and the standard gates run **once at milestone end** (full
   suite, coverage ≥95%, `ruff`, `mypy --strict`) — not per ticket.
3. **Committed & pushed** — the work is on the feature branch, pushed.
4. **Tracking issue closed** — or explicitly commented with status.
5. **Docs updated** — the milestone's design/reference docs updated and linked from this WBS.
6. **Checkpoint recorded** — a dated line appended to the Progress section (commit refs + gate result).
7. **The drill stays green** — once M10 lands, no milestone closes with a red drill (a survivor anywhere is a
   release-blocker, RK-3).
8. **Field tests (M12) and release readiness (M13) are the final milestones** — **M13 tags `v0.1.0`**.

> **One ticket at a time:** per work item, write the test first (RED) → implement (GREEN) → next. Do **not** run
> the full suite between tickets; run it at milestone end only.

## Milestones

| M | Name | Detail file |
|---|---|---|
| **M0** | Foundation, CLI & halt journal | [Part 1](wbs-v0.1.0-part1-foundation-store.md) |
| M1 | Halt store, dual choke & fail-closed | [Part 1](wbs-v0.1.0-part1-foundation-store.md) |
| M2 | Lineage registry & subtree resolution | [Part 2](wbs-v0.1.0-part2-lineage-process.md) |
| M3 | Process-tree containment (executor core) | [Part 2](wbs-v0.1.0-part2-lineage-process.md) |
| M4 | Credential, gateway & sandbox executors | [Part 3](wbs-v0.1.0-part3-executors-evidence.md) |
| M5 | Evidence snapshot & hash chain | [Part 3](wbs-v0.1.0-part3-executors-evidence.md) |
| M6 | Receipt, proof-of-stop & readout | [Part 4](wbs-v0.1.0-part4-receipt-triggers.md) |
| M7 | Triggers, halt events & journal integration | [Part 4](wbs-v0.1.0-part4-receipt-triggers.md) |
| M8 | Zero-hook-surface containment & hostile-harness | [Part 5](wbs-v0.1.0-part5-hostile-pause.md) |
| M9 | Pause/resume & the mode engine | [Part 5](wbs-v0.1.0-part5-hostile-pause.md) |
| M10 | Drill runner, catalogue & CI chaos gate | [Part 6](wbs-v0.1.0-part6-drill-hardening.md) |
| M11 | NFRs, hardening, observability & claims | [Part 6](wbs-v0.1.0-part6-drill-hardening.md) |
| **M12** | **Field tests** (last) | [Part 7](wbs-v0.1.0-part7-fieldtest-release.md) |
| **M13** | **Release readiness** (last; tags `v0.1.0`) | [Part 7](wbs-v0.1.0-part7-fieldtest-release.md) |

## Issues & milestones (GitHub)

Every work item ships as a **GitHub issue** under milestone `0.1.0 — M<n> <name>` (labels `0.1.0`, `wbs`). Body
standard: Context · Why · What · How · Data & schema impact · Security & privacy · Edge cases · Testing · Risks &
mitigations · Acceptance criteria · Dependencies · References · Definition of done; marker
`<!-- wbs:<item> -->`. **The `Issue` column in each part file holds the live number.** The two process items per
milestone (`.CI` commit, `.W` WBS checkpoint) are tracked here, not as issues.

**14 milestones · 170 issues** (`agentic-suite/agentsec-agenthalt`). The 2026-11-27 PRD consistency pass added
work item 2.7 (#569) and updated the affected issues in place.

| M | Milestone | Issues | M | Milestone | Issues |
|---|---|---|---|---|---|
| M0 | Foundation, CLI & halt journal | #399–#411 | M7 | Triggers, halt events & journal integration | #484–#495 |
| M1 | Halt store, dual choke & fail-closed | #412–#423 | M8 | Zero-hook-surface containment & hostile-harness | #496–#506 |
| M2 | Lineage registry & subtree resolution | #424–#435, #569 | M9 | Pause/resume & the mode engine | #507–#518 |
| M3 | Process-tree containment (executor core) | #436–#447 | M10 | Drill runner, catalogue & CI chaos gate | #519–#530 |
| M4 | Credential, gateway & sandbox executors | #448–#459 | M11 | NFRs, hardening, observability & claims | #531–#543 |
| M5 | Evidence snapshot & hash chain | #460–#471 | M12 | Field tests | #544–#555 |
| M6 | Receipt, proof-of-stop & readout | #472–#483 | M13 | Release readiness | #556–#567 |

## Progress

**✅ M0 — Foundation, CLI & halt journal.** Closed 2026-11-27.
**✅ M1 — Halt store, dual choke & fail-closed.** Closed 2026-11-27.
**✅ M2 — Lineage registry & subtree resolution.** Closed 2026-11-27.
**⬜ M3 — Process-tree containment (executor core).** Next.

### Checkpoints

- **2026-11-27 — M0 closed.** Commit `dd7bf7b` (`feat/m0-foundation`). Gate: 184 tests passed · coverage 99.91% ·
  `ruff` zero · `mypy --strict` clean; CI green on Python 3.10–3.13 × ubuntu/macos + install smoke
  ([run 46000026091](https://github.com/agentic-suite/agentsec-agenthalt/actions/runs/46000026091)). Review: 7 findings resolved ([log](codereview-log.md)). Decisions added:
  DD-41, DD-42. Issues #399–#411 closed with evidence (#405 after CI went green on PR #570,
  [run 46000606887](https://github.com/agentic-suite/agentsec-agenthalt/actions/runs/46000606887)). Landed on
  `docs/v0.1.0-planning` via #570 (`f509632`).
- **2026-11-27 — M1 closed.** Commits `0876349` (M1) + `9417027` (CI now runs on `docs/v0.1.0-planning` pushes), both
  directly on the integration branch. Gate: 313 tests passed · coverage 100% · `ruff` zero · `mypy --strict` clean;
  CI green on Python 3.10–3.13 × ubuntu/macos + install smoke ([run 46003485274](https://github.com/agentic-suite/agentsec-agenthalt/actions/runs/46003485274)).
  Review: 6 findings resolved ([log](codereview-log.md)). Decisions added: DD-43, DD-44. Issues #412–#423 closed with
  evidence.
- **2026-11-27 — M2 closed.** Commit `952011c`, directly on the integration branch. Gate: macOS 453 passed, 2 skipped
  (Linux-root-only) · coverage 99% (M2 modules 96–99%) · `ruff` zero · `mypy --strict` clean; Linux container as root
  451 passed, 4 skipped, including real cgroup containment and the real `--user` drop (CI skips both); CI green on
  Python 3.10–3.13 × ubuntu/macos + install smoke
  ([run 46101028681](https://github.com/agentic-suite/agentsec-agenthalt/actions/runs/46101028681)). Review: 14 findings
  resolved ([log](codereview-log.md)). Decisions added: DD-46, DD-47, DD-48. Issues #424–#435 and #569 closed with
  evidence.

## PRD coverage matrix (every doc 00–40)

| PRD | Topic | Milestone(s) |
|---|---|---|
| **PRD 00** | Press Release / FAQ | narrative; validated at M13 |
| **PRD 01** | Why | context (all milestones) |
| **PRD 02** | Architecture (halt pipeline, contract) | M1–M9 |
| **PRD 03** | Landscape | context; battlecard refreshed at M13 |
| **PRD 04** | Users & CUJs (CUJ-1..25) | M2–M10 |
| **PRD 05** | What (Features) R1–R24 | M1–M11 (R1–R14 v0.1.0) |
| **PRD 06** | Security baseline / adversarial sub-matrix | M8, M11 |
| **PRD 07** | Success metrics / release gate | M10, M12, M13 |
| **PRD 08** | Risks (RK-1..RK-22) | cross-cutting; M11 |
| **PRD 09** | Roadmap | M13 |
| **PRD 10** | Feature parity (`ai-loopguard` absorption) | M11 (parity closure) |
| **PRD 11** | Decisions DD-01..DD-53 | cross-cutting (honored every milestone) |
| **PRD 12** | Traceability (maintained) | every milestone |
| **PRD 13** | Non-Functional Requirements | M0, M1, M11 |
| **PRD 14** | Non-goals (scope guard) | every milestone |
| **PRD 15** | Data model + lifecycle | M2, M5, M6 |
| **PRD 16** | Trigger catalogue | M7 |
| **PRD 17** | Evidence & proof format | M5, M6 |
| **PRD 18** | Stop modes | M9 (pause/resume; ladder v0.2.0) |
| **PRD 19** | Harness compatibility | M8, M12, M13 |
| **PRD 20** | Standards, claims & interop | M7, M11 |
| **PRD 21** | Evidence register & method | cross-cutting |
| **PRD 22** | Demo scenarios | M3, M8, M9, M12 |
| **PRD 23** | Persona objections & adoption | M12 (eval kit) |
| **PRD 24** | Pricing & packaging thesis | M13 (product law honored) |
| **PRD 25** | Test strategy (5-level pyramid) | M0–M11 (gates), M10 (drill) |
| **PRD 26** | Receipt schema & examples | M6 |
| **PRD 27** | Lineage model | M2 |
| **PRD 28** | Failure-mode runbook | M11 (manual-fallback leg) |
| **PRD 29** | Regulatory crosswalk | M11 |
| **PRD 30** | Threat model | M8, M11 |
| **PRD 31** | Claims ledger | M11 |
| **PRD 32** | Build vs integrate | M3–M4 (adapter boundary) |
| **PRD 33** | Competitive battlecard | M13 |
| **PRD 34** | Design-partner evaluation guide | M12 |
| **PRD 35** | Drill pack catalogue & format | M10 |
| **PRD 36** | Observability & SOC pack | M11 |
| **PRD 37** | CLI & output UX spec | M0, M6 |
| **PRD 38** | Evidence privacy & data-handling | M5, M11 |
| **PRD 39** | Performance budget | M11 |
| **PRD 40** | Support, versioning & deprecation | M13 |

## Requirements → milestone (R1–R24)

| Req | Milestone(s) | Req | Milestone(s) |
|---|---|---|---|
| R1 composed stop | M3, M4 | R13 irreversibility honesty | M6 |
| R2 lineage containment | M2, M3 | R14 CI chaos drill | M10 |
| R3 evidence snapshot | M5 | R15 graduated stops (v0.2.0) | — |
| R4 trigger sources | M7 | R16 dead-man switches (v0.2.0; self-tamper subset ships v0.1.0, DD-36) | M1, M2, M8 (subset only) |
| R5 zero-hook-surface containment | M8 | R17 drills-in-a-box (v0.2.0) | — |
| R6 halt as agentwatch event | M7 | R18 halt authorization (v0.2.0) | — |
| R7 pause/resume | M9 | R19 SaaS coverage (v0.2.0) | — |
| R8 store + dual choke + fail-closed | M1, M11 (fuzz matrix) | R20 blast map (v0.2.0) | — |
| R9 lineage registry + enrollment | M0, M2 | R21 offline bundles (v0.2.0) | — |
| R10 proof-of-stop receipt | M4 (signing), M6 | R22 halt-from-anywhere (v0.2.0) | — |
| R11 the 09:01 readout | M6 | R23 fleet halt policies (v0.3.0) | — |
| R12 tamper-evident journal | M0, M7 | R24 external attestation (v0.3.0) | — |

> **Out of scope for v0.1.0** (tracked in [PRD 09](../../prd/09-roadmap.md)): requirements **R15–R24** (except
> the R16 self-tamper subset, DD-36) and the
> drill case **`fleet-drill`** (graduated modes, dead-man switches, drills-in-a-box, authorization, SaaS
> coverage, blast map, offline bundles, halt-from-anywhere, fleet policies, external attestation) — these are
> **v0.2.0/v0.3.0** and are deliberately absent from the v0.1.0 milestone work.

## CUJ → milestone (CUJ-1..25) — the explicit map

| CUJ | Journey (short) | Milestone |
|---|---|---|
| **CUJ-1** | Stop one runaway agent | **M3** |
| **CUJ-2** | Halt everything | **M7** |
| **CUJ-3** | Contain the lineage | **M2** |
| **CUJ-4** | Pause and resume | **M9** |
| **CUJ-5** | Kill the credentials | **M4** |
| **CUJ-6** | Disconnect at the gateway | **M4** |
| **CUJ-7** | Freeze the sandbox | **M3** |
| **CUJ-8** | Preserve the evidence | **M5** |
| **CUJ-9** | Verify the stop (proof-of-stop) | **M6** |
| **CUJ-10** | Read the 09:01 readout | **M6** |
| **CUJ-11** | Trigger from an alert | **M7** |
| **CUJ-12** | Panic key | **M7** |
| **CUJ-13** | Stop a zero-hook-surface harness | **M8** |
| **CUJ-14** | Halt as a first-class event | **M7** |
| **CUJ-15** | Run a halt drill | **M10** |
| **CUJ-16** | Fail closed | **M1** |
| **CUJ-17** | Irreversibility honesty | **M6** |
| **CUJ-18** | Graduate a stop (pause→quarantine→kill) | v0.2.0 — R15 |
| **CUJ-19** | Dead-man switch on budget exhaustion | v0.2.0 — R16 |
| **CUJ-20** | Dead-man switch on tamper | v0.2.0 — R16 |
| **CUJ-21** | Authorize the halt (RBAC / dual-control / break-glass) | v0.2.0 — R18 |
| **CUJ-22** | Halt a third-party / SaaS-hosted agent | v0.2.0 — R19 |
| **CUJ-23** | Blast map ("what could it still reach") | v0.2.0 — R20 |
| **CUJ-24** | Prove a halt offline (the auditor) | v0.2.0 — R21 |
| **CUJ-25** | Halt from anywhere (Slack / mobile) | v0.2.0 — R22 |

> Every v0.1.0 CUJ appears in exactly one milestone's **CUJ** column in its part file, and every milestone lists
> the CUJs it closes. No CUJ is orphaned; no milestone claims a CUJ it does not deliver.

## Decisions (PRD 11 / ADRs)

DD-01..DD-53 are honored across milestones; the twelve accepted ADRs carry the *why* in depth. Every decision
maps to the milestone(s) that implement it:

| Decision | Milestone(s) | ADR |
|---|---|---|
| **DD-01** Compose-not-own (agenthalt owns no layer; DD-45 fallbacks excepted) | M3, M4 (adapter boundary) | ADR-0001 |
| **DD-02** Halt store + dual choke (single source of stop truth) | M1 | ADR-0001, ADR-0002 |
| **DD-03** Fail-closed everywhere | M1 | ADR-0004 |
| **DD-04** Confirmations, not requests; `incomplete` first-class | M6 | ADR-0003 |
| **DD-05** Block-new-first ordering | M3 | — |
| **DD-06** Hooks optional, never load-bearing | M8 | ADR-0005 |
| **DD-07** No ML in the stop path | all (M7 triggers are events, not classifiers) | — |
| **DD-08** Harness-agnostic by construction | M8, M12 | — |
| **DD-09** Halt signal = agentwatch event (no new protocol) | M7 | ADR-0007 |
| **DD-10** Snapshot-before-termination | M5 | ADR-0006 |
| **DD-11** Irreversibility stated (compensation list) | M6 | — |
| **DD-12** v0.1.0 scope = the composed stop | all (M0–M13) | — |
| **DD-13** All three rungs at v0.1.0 as explicit commands; graduated semantics v0.2.0 | M9 | — |
| **DD-14** External dead-man switches v0.2.0 (self-tamper at v0.1.0, DD-36) | v0.2.0 (out of scope) | ADR-0010 |
| **DD-15** No console/UI beyond CLI in v1 | M0 | — |
| **DD-16** Fleet dual-control v0.2.0; v0.1.0 interim: `all` local-CLI-only, remote `max_scope ≤ agent` | M7 | — |
| **DD-17** macOS + Linux at v0.1.0; Windows dated | M3, M12 | — |
| **DD-18** agentgate degrades honestly until Wave 1 | M1, M4 | — |
| **DD-19** Python core (library + daemon + CLI + MCP) | M0 | — |
| **DD-20** `pip install agentsec-agenthalt` / CLI `agenthalt` | M0 | — |
| **DD-21** Local artifacts under `.agenthalt/` | M0 | — |
| **DD-22** ≤1 s measured budget | M10, M11 | — |
| **DD-23** Per-OS executor adapters | M3 | ADR-0008 (lineage) |
| **DD-24** Lineage edges append-only | M2 | ADR-0008 |
| **DD-25** Triggers authenticate (HMAC/mTLS/interactive) | M7 | — |
| **DD-26** Hash-chained journal + signed confirmations | M0, M4, M5 | — |
| **DD-27** Idempotent halts | M1 | — |
| **DD-28** Apache-2.0 | M0 | — |
| **DD-29** Measured numbers only | M10 | — |
| **DD-30** Every release ships artifacts | M13 | — |
| **DD-31** Flag, never silently change | M11, M13 | — |
| **DD-32** The drill is release-blocking | M10 | — |
| **DD-33** Single composed-stop entry point | M4 | — |
| **DD-34** Claims vocabulary enforced in CI | M11 | — |
| **DD-35** Signed releases + provenance | M13 | — |
| **DD-36** Self-tamper triggers at v0.1.0 (`tamper_store`/`tamper_hooks`/`tamper_lineage`) | M1, M2, M8 | ADR-0010 |
| **DD-37** Pause max-TTL 24 h → `kill` (`pause_expired`) | M9 | — |
| **DD-38** Enrollment via `agenthalt run` / `attach` | M0, M2 | ADR-0009 |
| **DD-39** Receipt status precedence `failed` > `incomplete` > `partial-layer` > `complete` | M0 (exit codes), M6 | ADR-0011 |
| **DD-40** Self-attested confirmations labelled `attestation: self` | M4, M6 | ADR-0011 |
| **DD-41** Config file format is TOML | M0 | — |
| **DD-42** Unknown config keys rejected; unknown env names warn | M0 | — |
| **DD-43** Strictest mode wins when halts overlap | M1 | — |
| **DD-44** M1 store same-OS-user + tamper-detected; separation with enrollment | M1, M2 | ADR-0009 |
| **DD-45** Built-in egress fallback (amends DD-01) | M3, M9 | ADR-0012 |
| **DD-46** Opt-in separate agent user (`run --user`) | M2 | ADR-0009 |
| **DD-47** `run` returns the agent's exit status | M2 | — |
| **DD-48** Authenticated lineage, head checkpointed in the journal | M2 | ADR-0008 |
| **DD-49** Provisional executor signing key | M3, M4 (4.6) | ADR-0011 |
| **DD-50** Marker-only members are cut | M3 | ADR-0008 |
| **DD-51** macOS network cut to 0.3.0 | M3, M9 | ADR-0012 |
| **DD-52** `lift` releases what the halt cut | M3, M9 | — |
| **DD-53** Re-raising cuts again | M3 | ADR-0003 |

## Risks → milestone (PRD 08, RK-1..RK-25)

| Risk | Milestone(s) | Risk | Milestone(s) |
|---|---|---|---|
| RK-1 fail-open | M1, M11 | RK-14 store availability | M1, M11 (manual fallback) |
| RK-2 lineage gap | M2, M8, M10 | RK-15 pause-limbo | M9 |
| RK-3 false success | M4, M6 | RK-16 drill theater | M10, M12 |
| RK-4 ≤1 s budget blown | M3, M10, M11 | RK-17 harness/OS churn | M12, M13 |
| RK-5 trigger abuse / DoS | M7 | RK-18 regulatory overreach | M11, M13 |
| RK-6 evidence destroyed | M5 | RK-19 irreversibility misunderstanding | M6 |
| RK-7 unrevocable credentials | M4, M6 | RK-20 kill by default | M9 (pause-first), M0 (kill requires reason) |
| RK-8 gateway bypass | M3 (egress), M4 | RK-21 ecosystem divergence | M4 (adapter boundary) |
| RK-9 cross-platform semantics | M3, M12 | RK-22 self-halt pack rots | M11 |
| RK-10 shutdown sabotage | M8 | RK-23 macOS lineage escape | M2, M11 |
| RK-11 journal tamper | M0, M7 | RK-24 remote listener exposure | M7, M11 |
| RK-12 receipt forgery | M4, M6 | RK-25 self-attestation | M3, M4, M6 |
| RK-13 scope creep into enforcement | M3, M4 (adapter contract) | | |

## Claims → milestone (PRD 31, C-01..C-12)

Each claim is publishable only when the milestone that produces its proof artifact has closed.

| Claim | Proof artifact | Milestone |
|---|---|---|
| C-01 composes four layers | compatibility table | M4, M13 |
| C-02 ≤1 s (with drill artifact) | CI perf artifact | M10 |
| C-03 zero survivors verified in drill | survivor gate | M8, M10 |
| C-04 receipts from confirmations | `prove` goldens + signatures | M4, M6 |
| C-05 zero-hook-surface harnesses | `hostile-harness` case | M8 |
| C-06 agentwatch events | event-join test | M7 |
| C-07 offline-verifiable evidence | chain + `prove` offline | M5 |
| C-08 regulatory alignment | crosswalk | M11 |
| C-09 pause/resume with full context | 24 h leg | M9 |
| C-10 absorbs `ai-loopguard` triggers | parity closure | M11 |
| C-11 free forever, Apache-2.0 | LICENSE + PRD 24 | M13 |
| C-12 every failure mode fails closed | fuzz matrix | M1, M11 |

**Open decisions** are tracked in the [PRD 21 open decisions register](../../prd/21-evidence-register-and-method.md)
with the milestone that must close each one. #2 pause max-TTL is decided (DD-37). Due in v0.1.0 milestones:
#1 lineage edge priority (adopt at 2.D0, revisit at 12.6), #5 snapshot retention/encryption (5.D0, 5.6, M11),
#7 agentgate co-shipping (12.4 partner eval), #9 remote anchoring (5.D0), #10 verification-key publication
(4.D0, M13), #11 enrollment mechanism (2.D0), #12 survivor-probe method (8.D0), #13 self-attestation key custody
(4.D0), #14 reference hardware (11.D0). Out of v0.1.0 scope: #3 fleet quorum and #4 escalate-on-act (v0.2.0),
#6 Windows (v0.2.0 planning), #8 stuck-loop triggers (v0.3.0). Each is recorded as a DD entry
before its milestone closes. Design docs per milestone are indexed in [docs/design](../../design/README.md).

## v0.1.0 release gate (all milestones)

- [ ] M0–M13 exit criteria satisfied (incl. design docs + parity closure)
- [ ] Full PRD coverage delivered + tested; every R1–R14 demonstrated by an acceptance test
- [ ] The composed stop works end-to-end; **alert → full stop ≤ 1 s** measured in CI (R1, R14)
- [ ] **Zero surviving descendants** in the drill (R2); a survivor fails the build
- [ ] The hostile-harness fixture (hooks removed) is still contained (R5)
- [ ] Evidence snapshot hash-chained, redact-before-persistence, canary-proven (R3)
- [ ] Receipt built from **confirmations**; `incomplete` on any survivor; offline-verifiable (R10)
- [ ] The readout answers the 09:01 question (R11); halts emitted in the agentwatch schema (R6)
- [ ] Pause/resume survives the 24 h wall-clock test (R7); fail-closed on every failure path (R8)
- [ ] The journal verifies as an unbroken chain; a seeded edit is detected (R12)
- [ ] The self-halt adversarial pack passes with zero crafted escapes (PRD 06)
- [ ] The three self-tamper triggers fire in the drill (DD-36); no remote trigger can raise `all` (DD-16)
- [ ] Every receipt carries status precedence, `attestation`, `survivor_probe` and `readout.coverage` (DD-39/40)
- [ ] Field tests pass (M12); security audit + compatibility table + coverage matrix + standards/regulatory
      matrix + measured drill numbers + release notes (M13)
- [ ] SBOM + signed artifacts (SLSA/Sigstore); OpenSSF Scorecard grade recorded

Review log: [codereview-log.md](codereview-log.md).
