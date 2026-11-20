# WBS v0.1.0 — Part 5: Hostile Harness & Pause (M8–M9)

**BLUF:** **M8** proves the hardest property — containment on a **hostile harness with the hooks removed**
(ADR-0005) — and builds the **survivor detector**. **M9** delivers the **mode engine** and **pause/resume**
(R7), the resumable stop with the 24 h integrity test. Everything here is v0.1.0.

> **Standard exit criteria + closure apply to every milestone** — see the [index](wbs-v0.1.0-index.md):
> **design docs first (`.D0`)**, then implement, then close with **`.T` · `.C` · `.L` · `.CR` · `.D` · `.CI` ·
> `.W`**.

---

## Milestone M8 — Zero-hook-surface containment & hostile-harness

**Goal:** make the ADR-0005 promise real: the hook adapter is **optional and never load-bearing**; a
hook-removal is **tamper detection → a dead-man trigger**; a **hostile-harness fixture** (hooks removed,
optionally lying) is still fully contained; and the **survivor detector** (post-halt network-call probe) that
M10's drill turns into a release gate.

**CUJ:** **CUJ-13** (stop a zero-hook-surface harness) · **Requirements:**
[PRD 06](../../prd/06-security-baseline.md), [PRD 30](../../prd/30-threat-model.md),
[PRD 19](../../prd/19-harness-compatibility.md), **R5**; [PRD 11](../../prd/11-decisions.md) DD-06; ADR-0005.

**Work items**

| # | Task | Description | Deliverable | Acceptance | Issue | CUJ | Req |
|---|---|---|---|---|---|---|---|
| 8.D0 | **Design docs first** | Hook-as-accelerant design, tamper-detection triggers, hostile-harness fixture, survivor-detector spec | docs | reviewed before code | #496 | — | — |
| 8.1 | Hook adapter (optional, annotation only) | Stop/PreToolUse hooks where present; richer lineage/graceful stop; **never load-bearing** (asserted) | adapter | hook present ⇒ richer; hook absent ⇒ identical containment | #497 | — | R5 |
| 8.2 | Hook-removal tamper detection → dead-man | Hook/config hash mismatch ⇒ tamper finding ⇒ dead-man trigger fires the stop | detection | tamper fires a halt with a distinct reason_code | #498 | — | R5 |
| 8.3 | **Hostile-harness fixture** | Harness with hooks removed (optionally lying); adversarial (ignores stop messages) | fixture | fixture runs; hooks absent confirmed by `doctor` | #499 | CUJ-13 | R5 |
| 8.4 | Zero-hook containment end-to-end | Full halt against the hostile fixture via process/credential/sandbox layers | test + demo leg | full containment with zero hooks; Demo 2 passes | #500 | CUJ-13 | R5 |
| 8.5 | **Survivor detector** | Post-halt network-call probe (any descendant making a call ⇒ survivor) | detector | detects a seeded survivor; reports zero on a clean halt | #501 | — | R5 |
| 8.T | Tests | Hook-accelerant equivalence, tamper trigger, hostile fixture containment, survivor detection | tests | all new paths covered; coverage ≥ 95% | #502 | — | — |
| 8.C | Coverage gate | Enforce coverage ≥ 95% on this milestone's modules | coverage report | ≥ 95%; no untested new path | #503 | — | — |
| 8.L | Lint & type gate | `ruff` zero; `mypy --strict` clean | CI | zero violations | #504 | — | — |
| 8.CR | Code review | Findings in [codereview-log.md](codereview-log.md), resolved | review log | no open findings | #505 | — | — |
| 8.D | Docs | Hook-adapter reference, tamper triggers, hostile-harness fixture, survivor detection | docs | docs updated + linked here | #506 | — | — |
| 8.CI | Commit & push | On the feature branch | git | pushed | — | — | — |
| 8.W | Update WBS | Checkpoint appended to the index Progress | WBS | checkpoint recorded | — | — | — |

**Exit criteria**

- [ ] Design docs first · all tests pass · coverage ≥ 95% · lint strict clean · docs updated · committed+pushed
- [ ] With all hooks removed, a halt still fully contains the agent (Demo 2)
- [ ] Hook removal is tamper detection → a dead-man trigger
- [ ] The survivor detector reports zero on a clean halt and catches a seeded survivor

---

## Milestone M9 — Pause/resume & the mode engine

**Goal:** the **mode engine** (the `pause → quarantine → kill` ladder as strict supersets) with **v0.1.0
shipping `pause` + `kill`** (quarantine escalations fully at v0.2.0 — DD-13), **pause/resume** with full-context
restoration and the **24 h wall-clock test** (R7), the **paused-run registry** with a max-TTL that
auto-escalates to kill (RK-15), and **escalate** + mode history in the journal.

**CUJ:** **CUJ-4** (pause and resume) · **Requirements:** [PRD 18](../../prd/18-stop-modes.md),
[PRD 13](../../prd/13-non-functional-requirements.md), [PRD 15](../../prd/15-data-model.md), **R7**;
[PRD 11](../../prd/11-decisions.md) DD-13; ADR-0001.

**Work items**

| # | Task | Description | Deliverable | Acceptance | Issue | CUJ | Req |
|---|---|---|---|---|---|---|---|
| 9.D0 | **Design docs first** | Mode-ladder semantics (supersets), pause/resume state model, TTL/expiry, escalate, mode history | docs | reviewed before code | #507 | — | — |
| 9.1 | **Mode engine** | `pause`/`quarantine`/`kill` as strict supersets; mode recorded in the store; choke enforces ≥ blocking at every rung | engine | superset property tested; mode in store | #508 | — | R7 |
| 9.2 | **Pause executor** | SIGSTOP / cgroup freeze; session state, handles, sandbox preserved (not terminated) | executor | subtree frozen; state intact | #509 | CUJ-4 | R7 |
| 9.3 | **Resume + paused-run registry + TTL** | Full-context resume; registry lists paused runs; **max-TTL default 24 h → auto-escalate to kill** with `pause_expired` | resume + registry | resume restores context; expiry escalates | #510 | CUJ-4 | R7 |
| 9.4 | Escalate + mode history | One command up the ladder; journaled; the receipt shows the mode timeline | CLI + journal | escalate is one command; history reconstructable | #511 | — | R7 |
| 9.5 | Quarantine (network cut + credential freeze) | Pause + egress cut + no new credential issuance (full escalation semantics land v0.2.0) | executor | quarantine cuts network; issuance frozen | #512 | — | R7 |
| 9.6 | Pause-aware choke + resume preconditions | A paused scope still blocks new actions (no bypass); resume preconditions documented | choke + docs | paused run cannot act; resume safe | #513 | — | R7 |
| 9.T | Tests | Superset property, freeze/resume integrity, **24 h wall-clock**, TTL expiry→kill, escalate, mode history | tests | all new paths covered; coverage ≥ 95% | #514 | — | — |
| 9.C | Coverage gate | Enforce coverage ≥ 95% on this milestone's modules | coverage report | ≥ 95%; no untested new path | #515 | — | — |
| 9.L | Lint & type gate | `ruff` zero; `mypy --strict` clean | CI | zero violations | #516 | — | — |
| 9.CR | Code review | Findings in [codereview-log.md](codereview-log.md), resolved | review log | no open findings | #517 | — | — |
| 9.D | Docs | Stop-modes reference, pause/resume, TTL policy, escalation | docs | docs updated + linked here | #518 | — | — |
| 9.CI | Commit & push | On the feature branch | git | pushed | — | — | — |
| 9.W | Update WBS | Checkpoint appended to the index Progress | WBS | checkpoint recorded | — | — | — |

**Exit criteria**

- [ ] Design docs first · all tests pass · coverage ≥ 95% · lint strict clean · docs updated · committed+pushed
- [ ] `pause` freezes and `resume` restores full context; **24 h wall-clock test passes**
- [ ] Pause TTL expiry auto-escalates to `kill` with `pause_expired` (kills pause-limbo, RK-15)
- [ ] Escalation is one command; the mode history is in the journal

---

Part 5 green ⇒ the stop is hostile-proof and resumable; proceed to
[Part 6 (M10–M11)](wbs-v0.1.0-part6-drill-hardening.md).
