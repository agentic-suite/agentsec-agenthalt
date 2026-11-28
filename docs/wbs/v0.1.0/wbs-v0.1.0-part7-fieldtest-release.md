# WBS v0.1.0 — Part 7: Field Tests & Release (M12–M13)

**BLUF:** **M12** runs the **field tests** — the platform × harness × trigger × layer-set matrix, the four v0.1.0 demos,
and the design-partner eval kit — and produces the **hand-maintained field-test report** (never overwritten by
automation). **M13** is **release readiness**: the release gate checklist, the security audit, the docs/claims
audit, the release artifacts (compatibility table, coverage matrix, measured drill numbers, SBOM, signed
release), the first-run evidence transcript, and the **`v0.1.0` tag**. Everything here is v0.1.0.

> **Standard exit criteria + closure apply to every milestone** — see the [index](wbs-v0.1.0-index.md):
> **design docs first (`.D0`)**, then implement, then close with **`.T` · `.C` · `.L` · `.CR` · `.D` · `.CI` ·
> `.W`**.

---

## Milestone M12 — Field tests

**Goal:** exercise the composed stop on **real stacks** (not fixtures) across the platform × harness × trigger ×
layer-set matrix, validate the four v0.1.0 demos ([PRD 22](../../prd/22-demo-scenarios.md)), run the design-partner eval
kit ([PRD 34](../../prd/34-design-partner-evaluation-guide.md)), and record per-case verdicts (P/F/D) in a
**hand-maintained report** — the ecosystem's signature release gate.

**CUJ:** — (field validation of all v0.1.0 CUJs) · **Requirements:** [PRD 19](../../prd/19-harness-compatibility.md),
[PRD 22](../../prd/22-demo-scenarios.md), [PRD 34](../../prd/34-design-partner-evaluation-guide.md),
[PRD 07](../../prd/07-success-metrics.md).

**Work items**

| # | Task | Description | Deliverable | Acceptance | Issue | CUJ | Req |
|---|---|---|---|---|---|---|---|
| 12.D0 | **Field-test plan + matrix** | The platform × harness × trigger × layer-set matrix; per-case steps; P/F/D classes; evidence-capture rules | plan | matrix reviewed before running | #544 | — | — |
| 12.1 | Test matrix definition | Name every case (supported + expected-degraded + not-supported), per platform/harness | matrix | matrix complete + honest | #545 | — | — |
| 12.2 | Run the cases | Execute each case; capture receipt + drill + journal artifacts | run artifacts | each case has an artifact | #546 | — | — |
| 12.3 | **Demo validation** | Run the four v0.1.0 demos (Replit, hostile harness, identity, panic key) end-to-end; Demo 4 is v0.2.0 | demo logs | all demos pass in ≤ their timing budget, with the receipt status predicted for the stack | #547 | — | — |
| 12.4 | Design-partner eval kit validation | A **non-author** runs the one-week kit's 10 questions against a real stack (gate item 15); answers open decision #7 (is `partial-layer` without agentgate acceptable to partners?) | eval report | ≥1 partner eval completed | #548 | — | — |
| 12.5 | **Field-test report** (hand-maintained) | Written from the non-author's run (12.4): per-case verdicts (P/F/D), notes, found-issues table; **automation may never overwrite it** | report | report committed + hand-maintained | #549 | — | — |
| 12.6 | Miss triage | Classify findings: blocker / defect / feature / out-of-scope ([PRD 34](../../prd/34-design-partner-evaluation-guide.md)); revisits open decision #1 (lineage edge priority) with field data | triage log | every finding classified | #550 | — | — |
| 12.T | Tests | Field cases re-expressed as regression tests where automatable | tests | automatable cases in the suite; coverage ≥ 95% | #551 | — | — |
| 12.C | Coverage gate | Enforce coverage ≥ 95% (unchanged; field work adds no new untested path) | coverage report | ≥ 95% | #552 | — | — |
| 12.L | Lint & type gate | `ruff` zero; `mypy --strict` clean | CI | zero violations | #553 | — | — |
| 12.CR | Code review | Findings in [codereview-log.md](codereview-log.md), resolved | review log | no open findings | #554 | — | — |
| 12.D | Docs | Field-test plan + report + demo evidence linked | docs | docs updated + linked here | #555 | — | — |
| 12.CI | Commit & push | On the feature branch | git | pushed | — | — | — |
| 12.W | Update WBS | Checkpoint appended to the index Progress | WBS | checkpoint recorded | — | — | — |

**Exit criteria**

- [ ] Design docs first · all tests pass · coverage ≥ 95% · lint strict clean · docs updated · committed+pushed
- [ ] Every supported matrix case passes on its platform/harness; not-supported rows are honest
- [ ] The four v0.1.0 demos pass; ≥1 design-partner eval completed by a non-author
- [ ] The field-test report is committed and **hand-maintained** (no automation overwrite)

---

## Milestone M13 — Release readiness (tags `v0.1.0`)

**Goal:** the release gate. Verify every [PRD 07](../../prd/07-success-metrics.md) gate item, run the security
audit (self-halt results, threat-model review, supply chain), audit docs/claims against the ledger, produce the
release artifacts (compatibility table, coverage matrix, crosswalk, measured drill numbers, SBOM, signed
release), capture first-run evidence, publish to PyPI, and **tag `v0.1.0`**.

**CUJ:** — (release) · **Requirements:** [PRD 07](../../prd/07-success-metrics.md),
[PRD 09](../../prd/09-roadmap.md), [PRD 20](../../prd/20-standards-and-claims.md),
[PRD 24](../../prd/24-pricing-and-packaging-thesis.md), [PRD 33](../../prd/33-competitive-battlecard.md),
[PRD 40](../../prd/40-support-versioning-and-deprecation.md).

**Work items**

| # | Task | Description | Deliverable | Acceptance | Issue | CUJ | Req |
|---|---|---|---|---|---|---|---|
| 13.D0 | **Release plan** | Version pin, gate checklist, artifact list, PyPI/attestation steps | plan | reviewed before release | #556 | — | — |
| 13.1 | Release gate checklist | Verify all 15 gate items ([PRD 07](../../prd/07-success-metrics.md) + the index release gate) | checklist | every item green or explicitly waived with reason | #557 | — | — |
| 13.2 | **Security audit** | Self-halt pack results (misses included); threat-model review; trigger-auth review; supply-chain attestations | audit | no open criticals; misses published | #558 | — | — |
| 13.3 | **Docs/claims audit** | Every README/doc claim → claims-ledger C-id; stale-doc sweep; forbidden-claim check | audit | zero unmatched claims; zero forbidden | #559 | — | — |
| 13.4 | Release artifacts | Compatibility table (harness × layer × version), coverage matrix, regulatory crosswalk, measured drill numbers, SBOM, signed release (SLSA/Sigstore) | artifacts | all present + signed | #560 | — | — |
| 13.5 | **First-run evidence** | Clean-machine transcript: install → `doctor` → Demo 1 → receipt → `prove` (the ≤15-min promise) | transcript | reproduces on a clean machine | #561 | — | — |
| 13.6 | Publish + tag | PyPI `agentsec-agenthalt==0.1.0`; GitHub release; **tag `v0.1.0`** | release | install works from PyPI; tag pushed | #562 | — | — |
| 13.T | Tests | Release smoke on the published artifact; first-run reproducibility | tests | published artifact installs + passes smoke; coverage ≥ 95% | #563 | — | — |
| 13.C | Coverage gate | Final coverage ≥ 95% on the release commit | coverage report | ≥ 95% | #564 | — | — |
| 13.L | Lint & type gate | `ruff` zero; `mypy --strict` clean on the release commit | CI | zero violations | #565 | — | — |
| 13.CR | Code review | Final review; findings in [codereview-log.md](codereview-log.md), resolved | review log | no open findings | #566 | — | — |
| 13.D | Docs | Release notes, compatibility table, coverage matrix, crosswalk, roadmap link | docs | docs updated + linked here | #567 | — | — |
| 13.CI | Commit & push | Release commit + tag on the feature branch | git | pushed | — | — | — |
| 13.W | Update WBS | Final checkpoint appended to the index Progress | WBS | checkpoint recorded | — | — | — |

**Exit criteria**

- [ ] Design docs first · all tests pass · coverage ≥ 95% · lint strict clean · docs updated · committed+pushed
- [ ] All release-gate items satisfied ([PRD 07](../../prd/07-success-metrics.md) + index); security audit clean
- [ ] Artifacts shipped: compatibility table, coverage matrix, crosswalk, measured drill numbers, SBOM, signed release
- [ ] First-run evidence reproduces the ≤15-min promise on a clean machine
- [ ] **`v0.1.0` tagged; PyPI published**

---

Part 7 green ⇒ **v0.1.0 shipped**. v0.2.0 (graduated modes, dead-man switches, authorization, SaaS coverage,
blast map, offline bundles, halt-from-anywhere) begins per [PRD 09](../../prd/09-roadmap.md).
