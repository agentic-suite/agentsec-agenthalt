# WBS v0.1.0 — Part 6: Drill & Hardening (M10–M11)

**BLUF:** **M10** builds the **drill runner**, the **drill pack catalogue** (the 12 launch cases,
[PRD 35](../../prd/35-drill-pack-catalogue.md)), and the **release-blocking CI chaos gate** — the measured ≤1 s /
zero-survivor proof that is the product's credibility. **M11** closes the non-functionals: the **performance
budget**, the **observability + SOC pack**, the **self-halt adversarial pack**, the **claims linter**, the
**privacy/data-handling** enforcement, and **parity closure** for the `ai-loopguard` absorption. Everything here
is v0.1.0.

> **Standard exit criteria + closure apply to every milestone** — see the [index](wbs-v0.1.0-index.md):
> **design docs first (`.D0`)**, then implement, then close with **`.T` · `.C` · `.L` · `.CR` · `.D` · `.CI` ·
> `.W`**.

---

## Milestone M10 — Drill runner, catalogue & CI chaos gate

**Goal:** the **drill pack format** + loader, the **drill runner** with measurement discipline (monotonic clocks,
percentiles, hardware note), the **12 launch cases**, the **survivor detector as a release gate**, and the **CI
job** producing the perf artifact that the claims ledger (C-02/C-03) reads directly. After M10, **the drill is
the gate** — a survivor anywhere fails the build (DD-32).

**CUJ:** **CUJ-15** (run a halt drill) · **Requirements:** [PRD 35](../../prd/35-drill-pack-catalogue.md),
[PRD 25](../../prd/25-test-strategy.md), [PRD 39](../../prd/39-performance-budget.md), **R14**;
[PRD 11](../../prd/11-decisions.md) DD-29/32.

**Work items**

| # | Task | Description | Deliverable | Acceptance | Issue | CUJ | Req |
|---|---|---|---|---|---|---|---|
| 10.D0 | **Design docs first** | Drill pack format, verdict vocabulary, runner measurement method, CI artifact format | docs | reviewed before code | #519 | — | — |
| 10.1 | **Drill pack format + loader** | `metadata.yaml`/`cases.yaml`/goldens; declarative (no imperative scripts); validated at load | format + loader | a pack loads; a bad pack fails loudly | #520 | — | R14 |
| 10.2 | **Drill runner + measurement** | Execute a case end-to-end; monotonic clocks; p50/p95/p99; hardware note; golden match | runner | a case runs; timings + verdict emitted | #521 | CUJ-15 | R14 |
| 10.3 | **The 12 launch cases** | `replit-stop`, `hostile-harness`, `credential-residue`, `panic-key`, `spawn-race`, `store-down`, `trigger-spoof`, `edge-forgery`, `receipt-tamper`, `evidence-canary`, `pause-ttl`, `manual-fallback` | cases | each case maps to its C-id + test; all run | #522 | CUJ-15 | R14 |
| 10.4 | **Survivor detector as release gate** | A survivor anywhere ⇒ build failure; the drill's survivor leg wraps the M8 detector | gate | seeded survivor fails the build | #523 | — | R14 |
| 10.5 | CI job + perf artifact | Per-platform drill job; writes the machine-readable perf artifact (the C-02/C-03 source) | CI + artifact | CI publishes numbers; claims read them | #524 | — | R14 |
| 10.6 | `agenthalt drill` CLI + partner mode | `--case`/`--platform`/`--all`/`--json`; `--private` local run for partners | CLI | CLI runs cases; partner mode works offline | #525 | CUJ-15 | R14 |
| 10.T | Tests | Pack load/validate, runner measurement, each of the 12 cases, survivor gate, artifact shape | tests | all new paths covered; coverage ≥ 95% | #526 | — | — |
| 10.C | Coverage gate | Enforce coverage ≥ 95% on this milestone's modules | coverage report | ≥ 95%; no untested new path | #527 | — | — |
| 10.L | Lint & type gate | `ruff` zero; `mypy --strict` clean | CI | zero violations | #528 | — | — |
| 10.CR | Code review | Findings in [codereview-log.md](codereview-log.md), resolved | review log | no open findings | #529 | — | — |
| 10.D | Docs | Drill pack reference, verdict vocabulary, the 12 cases, CI artifact | docs | docs updated + linked here | #530 | — | — |
| 10.CI | Commit & push | On the feature branch | git | pushed | — | — | — |
| 10.W | Update WBS | Checkpoint appended to the index Progress | WBS | checkpoint recorded | — | — | — |

**Exit criteria**

- [ ] Design docs first · all tests pass · coverage ≥ 95% · lint strict clean · docs updated · committed+pushed
- [ ] The full catalogue runs per platform; **≤1 s p95** and **zero survivors** measured in CI
- [ ] A survivor anywhere fails the build; the perf artifact is the single number source
- [ ] `agenthalt drill --all` is green on the reference laptop (macOS) and reference server (Linux)

---

## Milestone M11 — NFRs, hardening, observability & claims

**Goal:** close the non-functionals and the honesty machinery: **performance-budget enforcement**, the
**metrics registry + SLOs + error-budget policy**, the **SOC content pack**, the **failure-injection fuzz
matrix**, the **self-halt adversarial pack**, the **claims linter** + coverage matrix + regulatory crosswalk,
**privacy/data-handling** enforcement, the **manual-fallback** drill leg, and **parity closure** for the
`ai-loopguard` absorption.

**CUJ:** — (hardening; cross-cutting) · **Requirements:** [PRD 13](../../prd/13-non-functional-requirements.md),
[PRD 36](../../prd/36-observability-and-soc-pack.md), [PRD 39](../../prd/39-performance-budget.md),
[PRD 31](../../prd/31-claims-ledger.md), [PRD 30](../../prd/30-threat-model.md), [PRD 29](../../prd/29-regulatory-crosswalk.md),
[PRD 38](../../prd/38-evidence-privacy-and-data-handling.md), [PRD 10](../../prd/10-feature-parity.md),
[PRD 28](../../prd/28-failure-mode-runbook.md); **R8, R12** (hardening).

**Work items**

| # | Task | Description | Deliverable | Acceptance | Issue | CUJ | Req |
|---|---|---|---|---|---|---|---|
| 11.D0 | **Design docs first** | NFR enforcement, metrics/SLO model, self-halt pack scope, claims linter rules, privacy enforcement | docs | reviewed before code | #531 | — | — |
| 11.1 | Performance budget enforcement | Per-phase histograms; perf gate (a 20% p95 regression in any phase fails even inside the deadline) | perf gate | histograms emitted; regression fails | #532 | — | R8 |
| 11.2 | Metrics registry + SLOs + error budget | The 12 metrics (bounded cardinality); SLOs; **breach ⇒ feature freeze** | metrics + policy | cardinality enforced; breach recorded | #533 | — | — |
| 11.3 | **SOC content pack** | 7 SIEM alert rules + dashboards + ECS/OCSF field mapping; Grafana JSON imports | SOC pack | rules importable; dashboards load | #534 | — | — |
| 11.4 | Failure-injection fuzz matrix | Every failure mode denies (never silently continues); distinct reason codes | fuzz suite | matrix green; no fail-open path | #535 | — | R8 |
| 11.5 | **Self-halt adversarial pack** | Halt suppression, trigger spoof/replay, receipt forgery, journal tamper, snapshot destruction, colluding layer | pack + CI job | a seeded miss blocks the release; misses published | #536 | — | — |
| 11.6 | **Claims linter + coverage matrix + crosswalk** | Registry (`claims.yaml`) checked in CI; coverage matrix + regulatory crosswalk regenerated per release | linter + generators | forbidden claims fail; matrices generated | #537 | — | — |
| 11.7 | Privacy/data-handling enforcement + manual fallback | Canary in CI; retention/encryption honored; DSAR stub; the **manual-fallback** drill leg tested | enforcement + runbook | canary enforced; manual fallback passes | #538 | — | — |
| 11.T | Tests | Perf gate, metrics cardinality, SOC rules, fuzz matrix, self-halt pack, claims lint, manual fallback | tests | all new paths covered; coverage ≥ 95% | #539 | — | — |
| 11.C | Coverage gate | Enforce coverage ≥ 95% on this milestone's modules | coverage report | ≥ 95%; no untested new path | #540 | — | — |
| 11.L | Lint & type gate | `ruff` zero; `mypy --strict` clean | CI | zero violations | #541 | — | — |
| 11.CR | Code review | Findings in [codereview-log.md](codereview-log.md), resolved | review log | no open findings | #542 | — | — |
| 11.D | Docs | NFRs, observability, threat model review, claims ledger, crosswalk, **parity closure** ([PRD 10](../../prd/10-feature-parity.md)) | docs | docs updated + linked here | #543 | — | — |
| 11.CI | Commit & push | On the feature branch | git | pushed | — | — | — |
| 11.W | Update WBS | Checkpoint appended to the index Progress | WBS | checkpoint recorded | — | — | — |

**Exit criteria**

- [ ] Design docs first · all tests pass · coverage ≥ 95% · lint strict clean · docs updated · committed+pushed
- [ ] Perf gate + metrics + SLOs live; an SLO breach freezes features
- [ ] The self-halt adversarial pack passes with zero crafted escapes; misses published
- [ ] The claims linter + coverage matrix + crosswalk are CI-generated; parity closure is complete
- [ ] **This closes the v0.1.0 core** (a leaner release may tag here; the field tests + release follow)

---

Part 6 green ⇒ the stop is measured, hardened, and honest; proceed to
[Part 7 (M12–M13)](wbs-v0.1.0-part7-fieldtest-release.md).
