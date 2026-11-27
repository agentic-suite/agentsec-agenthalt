# WBS v0.1.0 — Part 1: Foundation & Halt Store (M0–M1)

**BLUF:** **M0** establishes agenthalt's identity, CLI surface, config model, and the **tamper-evident halt
journal** every later milestone writes to. **M1** delivers the safety spine: the **halt store**, the **dual
choke** protocol, and **fail-closed** semantics — the properties ADR-0001/0002/0004 fix and every other
milestone assumes. Everything here is v0.1.0.

> **Standard exit criteria + closure apply to every milestone** — see the [index](wbs-v0.1.0-index.md):
> **design docs first (`.D0`)**, then implement, then close with **`.T` tests · `.C` coverage ≥95% · `.L` ruff +
> `mypy --strict` · `.CR` review · `.D` docs + traceability · `.CI` commit · `.W` WBS checkpoint**.

---

## Milestone M0 — Foundation, CLI & halt journal

**Goal:** agenthalt's identity, CLI, configuration, packaging, and CI — plus the **append-only, hash-chained
halt journal** ([PRD 15](../../prd/15-data-model.md), ADR-0007's record side) and the `doctor` preflight that
every later milestone builds on. The CLI's **reserved exit codes** are fixed here because runbooks and scripts
depend on them forever ([PRD 37](../../prd/37-cli-and-output-ux-spec.md), Tier-0 in [PRD 40](../../prd/40-support-versioning-and-deprecation.md)).

**CUJ:** — (foundation; no user journey) · **Requirements:** [PRD 13](../../prd/13-non-functional-requirements.md)
(portability, cost), [PRD 37](../../prd/37-cli-and-output-ux-spec.md), [PRD 11](../../prd/11-decisions.md)
(DD-19..DD-21, DD-28), **R12** (journal).

**Work items**

| # | Task | Description | Deliverable | Acceptance | Issue | CUJ | Req |
|---|---|---|---|---|---|---|---|
| 0.D0 | **Design docs first** | Foundation design: CLI surface (incl. `run`/`attach`), config model, exit-code contract + precedence, journal chain format, `doctor` semantics | docs | reviewed before code | #399 | — | — |
| 0.1 | Scaffold & identity | `pyproject.toml` for `agenthalt` / `agentsec-agenthalt`, CLI entry point, `make setup`/`lint`/`typecheck`/`test`/`cov`; README/LICENSE/CODEOWNERS/SECURITY finalized | packaging | `pip install -e .` works; `make setup` green | #400 | — | — |
| 0.2 | CLI framework + subcommands | Full command surface (`run`/`attach`/`halt`/`pause`/`quarantine`/`kill`/`resume`/`escalate`/`lift`/`status`/`prove`/`drill`/`journal`/`evidence`/`doctor`/`runbook`) with **reserved exit codes 0–5** and the DD-39 precedence (`3` > `1` > `2` > `0`) | CLI | `agenthalt --help` lists commands; exit codes reserved + documented | #401 | — | — |
| 0.3 | Configuration model | Precedence **flags > `AGENTHALT_*` env > config file > defaults**; schema-validated; **fail-closed** on invalid config (exit 5) | config loader | invalid config fails closed (exit 5); precedence tested | #402 | — | — |
| 0.4 | **Halt journal** (append-only, hash-chained) | Entry model (`seq`/`prev_hash`/`entry_hash`/actor/scope/reason/mode/action), JSONL segments, **rotation anchor** committing the prior head | journal | chain verifies; a seeded edit is detected; rotation never breaks the chain | #403 | — | R12 |
| 0.5 | `doctor` + structured logging | Environment/store/adapter preflight with a verdict; `--migrate` hook stub; structured JSON logs with `halt_id` correlation; no secrets at any level; platform checks: macOS Accessibility permission (panic key), Linux cgroup v2 delegation (enrollment), hook surface present/absent | CLI + logs | `doctor` reports a verdict; logs parse; redaction asserted; each platform check reports pass/fail with the fix | #404 | — | — |
| 0.6 | CI & quality gate | `ruff` + `mypy --strict` + `pytest` + coverage ≥95% + DCO | GitHub Actions | CI green on PR | #405 | — | — |
| 0.7 | Identity & governance docs | README/SECURITY finalized; PRD traceability wired; `.agenthalt/` layout documented | docs | docs match identity | #406 | — | — |
| 0.T | Tests | Config fail-closed + precedence, CLI smoke, exit-code contract, journal chain + tamper detection, `doctor` verdict | tests | all new paths covered; coverage ≥ 95% | #407 | — | — |
| 0.C | Coverage gate | Enforce coverage ≥ 95% on this milestone's modules | coverage report | ≥ 95%; no untested new path | #408 | — | — |
| 0.L | Lint & type gate | `ruff` zero; `mypy --strict` clean | CI | zero violations | #409 | — | — |
| 0.CR | Code review | Findings in [codereview-log.md](codereview-log.md), resolved | review log | no open findings | #410 | — | — |
| 0.D | Docs | Development guide, CLI reference, exit-code contract, journal format | docs | docs updated + linked here | #411 | — | — |
| 0.CI | Commit & push | On the feature branch | git | pushed | — | — | — |
| 0.W | Update WBS | Checkpoint appended to the index Progress | WBS | checkpoint recorded | — | — | — |

**Exit criteria**

- [x] Design docs first · all tests pass · coverage ≥ 95% · lint strict clean · docs updated · committed+pushed
- [x] `agenthalt --help` lists the full command surface; exit codes 0–5 reserved and documented
- [x] Bad config fails closed (exit 5); the journal chain verifies and detects a seeded edit
- [x] Exit-code precedence `3` > `1` > `2` > `0` (DD-39) tested; `run`/`attach` reserved in the CLI

**Docs (0.D):** [M0 design](../../design/m0-foundation.md) · [CLI reference](../../reference/cli.md) ·
[exit codes](../../reference/exit-codes.md) · [configuration](../../reference/configuration.md) ·
[journal format](../../reference/journal-format.md) · [state layout](../../reference/state-layout.md) ·
[development guide](../../guides/development.md) · [code review](codereview-log.md)

**Status: ✅ closed 2026-11-27** — `dd7bf7b` on `feat/m0-foundation`; landed on `docs/v0.1.0-planning` via #570; CI green on branch and PR ([run 46000026091](https://github.com/agentic-suite/agentsec-agenthalt/actions/runs/46000026091)).

---

## Milestone M1 — Halt store, dual choke & fail-closed

**Goal:** the **safety spine**. The halt store is the single source of stop truth (ADR-0001); the **dual choke**
reads it at the runtime *and* the gateway before an action executes (ADR-0002); every failure path is
**fail-closed** with a distinct `reason_code` (ADR-0004). After M1, the fleet is stoppable in principle — M2–M7
add the graph, the cuts, the evidence, and the proof.

**CUJ:** **CUJ-16** (fail closed) · **Requirements:** [PRD 02](../../prd/02-architecture.md),
[PRD 13](../../prd/13-non-functional-requirements.md), [PRD 39](../../prd/39-performance-budget.md) (choke budget),
**R8**; [PRD 11](../../prd/11-decisions.md) DD-02/03/05/27.

**Work items**

| # | Task | Description | Deliverable | Acceptance | Issue | CUJ | Req |
|---|---|---|---|---|---|---|---|
| 1.D0 | **Design docs first** | Halt-store design: scopes, TTL, persistence, choke-read path, fail-closed contract, reason codes | docs | reviewed before code | #412 | — | — |
| 1.1 | **Halt store** | Authoritative kill state with scopes (`session`/`agent`/`run`/`subtree`/`tenant`/`global`/`tool:<name>`/`writes-disabled`), local-first, persisted + rotation | store | state survives restart; scope resolution correct | #413 | — | R8 |
| 1.2 | **Runtime choke** | Read API the runtime calls before an action; **short-TTL cache (seconds, never minutes)**; local read inside the ≤50 ms budget | choke API | halt visible ≤ 50 ms; cache TTL enforced | #414 | — | R8 |
| 1.3 | **Gateway choke interface** | Dual-choke abstraction; agentgate adapter **stub** that reports `unsupported` honestly until Wave 1 | interface + stub | gateway half reports unsupported, never silently skipped | #415 | — | R8 |
| 1.4 | **Fail-closed semantics + reason codes** | Store unreachable / adapter failure / lineage gap → deny high-impact actions with `halt_store_unavailable`/`adapter_failed`/`lineage_gap` | reason-code registry | every failure path denies; distinct codes | #416 | CUJ-16 | R8 |
| 1.5 | Idempotency & scope composition | Re-raising the same halt returns the existing receipt (no-op); concurrent different halts compose (tighter scope wins within its subtree); halt lifecycle `pending`/`blocking`/`executing`/`finished`/`lifted`, with the outcome carried by the receipt status (PRD 15) | coordinator logic | duplicate ⇒ idempotent; concurrent ⇒ no corruption | #417 | — | R8 |
| 1.6 | Store health + `status` skeleton | Store health + integrity signal (unreachable / truncated / head ≠ journal while a halt is armed), consumed by the `tamper_store` self-tamper trigger wired in 8.2 (DD-36); `agenthalt status` showing live halt state | CLI + health | status reports live state; health surfaces store-down; the integrity signal tells a restart from tampering | #418 | — | R8 |
| 1.T | Tests | Store scopes/TTL, choke latency, cache-TTL enforcement, fail-closed fuzz matrix, idempotency, concurrent scopes | tests | all new paths covered; coverage ≥ 95% | #419 | — | — |
| 1.C | Coverage gate | Enforce coverage ≥ 95% on this milestone's modules | coverage report | ≥ 95%; no untested new path | #420 | — | — |
| 1.L | Lint & type gate | `ruff` zero; `mypy --strict` clean | CI | zero violations | #421 | — | — |
| 1.CR | Code review | Findings in [codereview-log.md](codereview-log.md), resolved | review log | no open findings | #422 | — | — |
| 1.D | Docs | Halt-store reference, choke protocol, fail-closed contract + reason codes | docs | docs updated + linked here | #423 | — | — |
| 1.CI | Commit & push | On the feature branch | git | pushed | — | — | — |
| 1.W | Update WBS | Checkpoint appended to the index Progress | WBS | checkpoint recorded | — | — | — |

**Exit criteria**

- [ ] Design docs first · all tests pass · coverage ≥ 95% · lint strict clean · docs updated · committed+pushed
- [ ] The halt store is the single source of stop truth; both chokes read it; cache TTL is seconds-scale
- [ ] Every failure path is fail-closed with a distinct reason code; store-down ⇒ high-impact actions denied
- [ ] The store integrity signal exists and is consumable by `tamper_store` (DD-36)

---

Part 1 green ⇒ the safety spine exists; proceed to [Part 2 (M2–M3)](wbs-v0.1.0-part2-lineage-process.md).
