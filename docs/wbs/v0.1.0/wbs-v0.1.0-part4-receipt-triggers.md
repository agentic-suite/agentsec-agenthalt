# WBS v0.1.0 — Part 4: Proof & Triggers (M6–M7)

**BLUF:** **M6** delivers the **proof-of-stop receipt** (confirmations-only, ADR-0003), the **09:01 readout**,
the **compensation list**, and the **offline verifier** — the differentiator the whole category lacks. **M7**
wires the **triggers** (CLI, panic key, webhook, PagerDuty, Slack), the **halt events** (agentwatch schema,
ADR-0007), and the **journal integration**. Everything here is v0.1.0.

> **Standard exit criteria + closure apply to every milestone** — see the [index](wbs-v0.1.0-index.md):
> **design docs first (`.D0`)**, then implement, then close with **`.T` · `.C` · `.L` · `.CR` · `.D` · `.CI` ·
> `.W`**.

---

## Milestone M6 — Receipt, proof-of-stop & readout

**Goal:** the **receipt** (`agenthalt.receipt.v1`) assembled **only from enforcement-point confirmations** —
`incomplete` when any descendant is unconfirmed (a schema-level invariant), with the **readout** (unrevocable
grants + windows, queued work, siblings, downstream, uncovered routes), the **compensation list** (no-undo
honesty), and the **offline verifier** (`prove`). This is the product's trust artifact.

**CUJ:** **CUJ-9** (verify the stop), **CUJ-10** (the 09:01 readout), **CUJ-17** (irreversibility honesty) ·
**Requirements:** [PRD 26](../../prd/26-receipt-schema-and-examples.md),
[PRD 17](../../prd/17-evidence-and-proof-format.md), [PRD 37](../../prd/37-cli-and-output-ux-spec.md), **R10,
R11, R13**; [PRD 11](../../prd/11-decisions.md) DD-04/11; ADR-0003.

**Work items**

| # | Task | Description | Deliverable | Acceptance | Issue | CUJ | Req |
|---|---|---|---|---|---|---|---|
| 6.D0 | **Design docs first** | Receipt schema v1, status vocabulary, readout fields, compensation model, verifier semantics | docs | reviewed before code | #78 | — | — |
| 6.1 | **Receipt builder** | Assemble from **confirmations only**; fields per [PRD 26](../../prd/26-receipt-schema-and-examples.md); trigger/subtree/confirmations/refused-calls/evidence | builder | a `requested` never appears as a stop | #79 | CUJ-9 | R10 |
| 6.2 | Status vocabulary + survivors invariant | `complete`/`incomplete`/`partial-layer`/`failed`; non-empty `survivors[]` **forces** `incomplete` | invariant | survivor ⇒ incomplete (schema-enforced) | #80 | CUJ-9 | R10 |
| 6.3 | **Readout builder** | Unrevocable grants + residual windows, queued work, siblings, downstream agents, uncovered routes | readout | every residual named with its window | #81 | CUJ-10 | R11 |
| 6.4 | **Compensation-list builder** | Already-landed side effects (kind/ref/`reversible:false`); never offers reversal | compensation | landed effects listed; no undo claim | #82 | CUJ-17 | R13 |
| 6.5 | **Offline verifier** (`prove`) | Re-derive receipt hash, verify confirmation signatures, cross-check evidence chain; emits `VERIFIED (…)`/`TAMPERED` | CLI | third party verifies without agenthalt installed | #83 | CUJ-9 | R10 |
| 6.6 | Receipt one-liner + `--json` | Human one-liner + full `--json` (the same object `prove` verifies); exit-code tie-in (0/1/2) | CLI output | one-liner accurate; `--json` matches schema | #84 | CUJ-10 | R11 |
| 6.T | Tests | Receipt assembly, survivors invariant, readout fields, compensation, `prove` (golden + tamper), output modes | tests | all new paths covered; coverage ≥ 95% | #85 | — | — |
| 6.C | Coverage gate | Enforce coverage ≥ 95% on this milestone's modules | coverage report | ≥ 95%; no untested new path | #86 | — | — |
| 6.L | Lint & type gate | `ruff` zero; `mypy --strict` clean | CI | zero violations | #87 | — | — |
| 6.CR | Code review | Findings in [codereview-log.md](codereview-log.md), resolved | review log | no open findings | #88 | — | — |
| 6.D | Docs | Receipt reference, status vocabulary, readout, offline verification | docs | docs updated + linked here | #89 | — | — |
| 6.CI | Commit & push | On the feature branch | git | pushed | — | — | — |
| 6.W | Update WBS | Checkpoint appended to the index Progress | WBS | checkpoint recorded | — | — | — |

**Exit criteria**

- [ ] Design docs first · all tests pass · coverage ≥ 95% · lint strict clean · docs updated · committed+pushed
- [ ] Receipts are built from confirmations; a survivor forces `incomplete`
- [ ] The readout answers the 09:01 question; the compensation list never claims reversal
- [ ] `prove` verifies a receipt offline; a seeded edit reports `TAMPERED`

---

## Milestone M7 — Triggers, halt events & journal integration

**Goal:** every way a halt is **raised** (CLI, alert webhook, PagerDuty, Slack, keyboard panic key), each
authenticated and journaled; the **halt event emission** in the agentwatch security-event schema (ADR-0007);
and the **journal integration** (`journal show/verify`) — including the scope ceilings and fleet-confirmation
pattern that keep the switch from being a DoS lever.

**CUJ:** **CUJ-2** (halt everything), **CUJ-11** (trigger from an alert), **CUJ-12** (panic key), **CUJ-14**
(halt as a first-class event) · **Requirements:** [PRD 16](../../prd/16-trigger-catalogue.md),
[PRD 20](../../prd/20-standards-and-claims.md), [PRD 37](../../prd/37-cli-and-output-ux-spec.md), **R4, R6, R12**;
[PRD 11](../../prd/11-decisions.md) DD-09/25; ADR-0007.

**Work items**

| # | Task | Description | Deliverable | Acceptance | Issue | CUJ | Req |
|---|---|---|---|---|---|---|---|
| 7.D0 | **Design docs first** | Trigger catalogue (auth per path, replay windows, scope ceilings), halt-event schema, journal integration | docs | reviewed before code | #90 | — | — |
| 7.1 | **Halt event emitter** (agentwatch) | `halt.raised`/`halt.completed`/`trigger.rejected` in the security-event schema; join on common id | emitter | SOC test alarms on a halt; events join | #91 | CUJ-14 | R6 |
| 7.2 | CLI trigger + **panic key** | CLI halt; panic key bound to the **interactive session** (non-interactive rejected + journaled; no-op when idle) | triggers | panic key fires; non-interactive rejected | #92 | CUJ-12 | R4 |
| 7.3 | **Alert webhook trigger** | HMAC-signed webhook, ±5 min replay window, per-source rate limit | trigger | signed accepted; replay/unsigned rejected | #93 | CUJ-11 | R4 |
| 7.4 | PagerDuty + Slack triggers | PagerDuty button (incident-bound); Slack action (signed + principal) | triggers | both fire + journal actor/channel | #94 | CUJ-11 | R4 |
| 7.5 | Scope ceilings + fleet confirmation | `max_scope` structural; `--all` requires typed confirmation or `--yes`; CI non-tty fleet halt ⇒ exit 4 | guardrails | scope cannot widen; fleet halt gated | #95 | CUJ-2 | R4 |
| 7.6 | Journal integration | `journal show`/`journal verify`; trigger record written **before** resolution; every raise/execute/lift/resume journaled | CLI + journal | journal-first enforced; verify detects tamper | #96 | — | R12 |
| 7.T | Tests | Each trigger path + auth/replay/rate-limit, scope ceilings, event emission/join, journal-first, verify | tests | all new paths covered; coverage ≥ 95% | #97 | — | — |
| 7.C | Coverage gate | Enforce coverage ≥ 95% on this milestone's modules | coverage report | ≥ 95%; no untested new path | #98 | — | — |
| 7.L | Lint & type gate | `ruff` zero; `mypy --strict` clean | CI | zero violations | #99 | — | — |
| 7.CR | Code review | Findings in [codereview-log.md](codereview-log.md), resolved | review log | no open findings | #100 | — | — |
| 7.D | Docs | Trigger catalogue reference, halt-event schema binding, journal commands | docs | docs updated + linked here | #101 | — | — |
| 7.CI | Commit & push | On the feature branch | git | pushed | — | — | — |
| 7.W | Update WBS | Checkpoint appended to the index Progress | WBS | checkpoint recorded | — | — | — |

**Exit criteria**

- [ ] Design docs first · all tests pass · coverage ≥ 95% · lint strict clean · docs updated · committed+pushed
- [ ] All five launch triggers fire, authenticate, and journal actor/channel/reason
- [ ] Halts + triggers emit agentwatch events that join on a common id
- [ ] The journal is written first and verifies; scope ceilings and fleet confirmation hold

---

Part 4 green ⇒ the stop is provable and raisable from anywhere; proceed to
[Part 5 (M8–M9)](wbs-v0.1.0-part5-hostile-pause.md).
