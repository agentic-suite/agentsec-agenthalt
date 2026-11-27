# WBS v0.1.0 — Part 3: Executors & Evidence (M4–M5)

**BLUF:** **M4** completes the composed stop by adding the **credential, gateway, and kernel executors** — the
cuts that stop what a process kill cannot (the identity problem). **M5** delivers the **evidence snapshot**: a
hash-chained, redacted, offline-verifiable forensic artifact written **before** the scene is destroyed
(ADR-0006). Everything here is v0.1.0.

> **Standard exit criteria + closure apply to every milestone** — see the [index](wbs-v0.1.0-index.md):
> **design docs first (`.D0`)**, then implement, then close with **`.T` · `.C` · `.L` · `.CR` · `.D` · `.CI` ·
> `.W`**.

---

## Milestone M4 — Credential, gateway & sandbox executors

**Goal:** the remaining cuts. **agentkeys** revocation (incl. already-issued grants) with **residual-window
honesty** for unrevocable static keys; **agentgate** session termination (both directions); the **agentkernel**
kill-trigger interface (capability-gated); the **adapter degradation matrix** (`unsupported`/`failed` honesty →
`partial-layer`); and **enforcement-point signing keys** so confirmations are verifiable (feeds M6's receipt).

**CUJ:** **CUJ-5** (kill the credentials), **CUJ-6** (disconnect at the gateway) · **Requirements:**
[PRD 02](../../prd/02-architecture.md), [PRD 32](../../prd/32-build-vs-integrate.md),
[PRD 26](../../prd/26-receipt-schema-and-examples.md) (confirmation signing), **R1**;
[PRD 11](../../prd/11-decisions.md) DD-01/18; [PRD 19](../../prd/19-harness-compatibility.md) (degradation honesty).

**Work items**

| # | Task | Description | Deliverable | Acceptance | Issue | CUJ | Req |
|---|---|---|---|---|---|---|---|
| 4.D0 | **Design docs first** | Executor designs: revoke semantics, gateway terminate, kernel trigger, degradation matrix, signing model; closes open decisions #10 (verification-key publication) and #13 (self-attestation key custody) | docs | reviewed before code | #448 | — | — |
| 4.1 | **Credential executor** (agentkeys) | Revoke every grant the subtree holds, incl. already-issued tokens where the issuer supports revocation; inventory of subtree grants | executor | revoke issued + confirmed; inventory complete | #449 | CUJ-5 | R1 |
| 4.2 | Revoke confirmations + residual windows | `confirmed` vs `requested`; **unrevocable static keys reported with expiry windows** (never claimed revoked) | reporting | static key listed under `unrevocable_grants` | #450 | CUJ-5 | R1 |
| 4.3 | **Gateway executor** (agentgate) | Session termination; refuses calls both directions; when absent, `unsupported` in ≤1 ms | executor | gateway refuses both directions; absent ⇒ unsupported | #451 | CUJ-6 | R1 |
| 4.4 | Kernel executor interface (agentkernel) | Capability-gated eBPF kill-trigger wiring; degrades to `unsupported` where not deployed | interface | kill trigger wired where present; honest otherwise | #452 | — | R1 |
| 4.5 | **Adapter degradation matrix** | `unsupported`/`failed` honesty → receipt `partial-layer`; no padding, no silent skip | matrix + logic | partial-layer reported, never hidden | #453 | — | R1 |
| 4.6 | Enforcement-point signing keys | Per-adapter key model; confirmation signatures; rotation via the release attestation bundle; the built-in OS executor signs with a separate key and labels `attestation: self` (DD-40) | signing | confirmations verify against published keys | #454 | — | R1 |
| 4.T | Tests | Revoke + confirm, residual-window reporting, gateway both-directions, kernel degrade, degradation matrix, signature verification | tests | all new paths covered; coverage ≥ 95% | #455 | — | — |
| 4.C | Coverage gate | Enforce coverage ≥ 95% on this milestone's modules | coverage report | ≥ 95%; no untested new path | #456 | — | — |
| 4.L | Lint & type gate | `ruff` zero; `mypy --strict` clean | CI | zero violations | #457 | — | — |
| 4.CR | Code review | Findings in [codereview-log.md](codereview-log.md), resolved | review log | no open findings | #458 | — | — |
| 4.D | Docs | Executor reference, degradation matrix, confirmation-signing model | docs | docs updated + linked here | #459 | — | — |
| 4.CI | Commit & push | On the feature branch | git | pushed | — | — | — |
| 4.W | Update WBS | Checkpoint appended to the index Progress | WBS | checkpoint recorded | — | — | — |

**Exit criteria**

- [ ] Design docs first · all tests pass · coverage ≥ 95% · lint strict clean · docs updated · committed+pushed
- [ ] The composed stop cuts process + credentials + gateway + sandbox; unrevocable grants are reported honestly
- [ ] An absent layer reports `unsupported` → receipt `partial-layer` (never a silent skip)
- [ ] Confirmations are signed and verifiable

---

## Milestone M5 — Evidence snapshot & hash chain

**Goal:** the **evidence snapshot** — trace window + process tree + open connections + credential inventory —
captured **before termination** (ADR-0006), **redacted before persistence** (typed placeholders, proven by the
canary), **hash-chained** and timestamped, and exportable as an **offline-verifiable bundle** with a manifest
([PRD 17](../../prd/17-evidence-and-proof-format.md)).

**CUJ:** **CUJ-8** (preserve the evidence) · **Requirements:** [PRD 17](../../prd/17-evidence-and-proof-format.md),
[PRD 38](../../prd/38-evidence-privacy-and-data-handling.md), [PRD 15](../../prd/15-data-model.md), **R3**;
[PRD 11](../../prd/11-decisions.md) DD-10; ADR-0006.

**Work items**

| # | Task | Description | Deliverable | Acceptance | Issue | CUJ | Req |
|---|---|---|---|---|---|---|---|
| 5.D0 | **Design docs first** | Snapshot design: components, chain math, redaction pipeline, ordering, export bundle; closes open decisions #5 (retention + encryption) and #9 (remote anchoring) | docs | reviewed before code | #460 | — | — |
| 5.1 | **Snapshot collector** | Trace window (agentwatch ref) + process tree (lineage) + open connections + credential inventory | collector | all four components captured | #461 | CUJ-8 | R3 |
| 5.2 | Hash chain + timestamp + rotation anchor | `snapshot.json` + `chain.jsonl` (`seq`/`prev_hash`/`entry_hash`); anchored rotation (truncate-rebuild detectable) | chain | chain verifies; rotation anchors head | #462 | — | R3 |
| 5.3 | **Redaction pipeline** + canary | Typed placeholders (`secret:<kind>[redacted ×n]`), redact-**before**-persistence; **canary test** proves zero raw secrets land | redaction | canary absent from snapshot + export; placeholder present | #463 | — | R3 |
| 5.4 | Snapshot-before-termination ordering | Enforce the fixed order: choke → suspend → cut network → first-segment commit → terminate → revoke | coordinator | termination cannot precede first-segment commit | #464 | — | R3 |
| 5.5 | Evidence export + manifest + offline verify | `evidence export/verify`; tarball with detached hashes + manifest (content hashes) + data-handling notice | CLI + verifier | third party verifies the bundle offline | #465 | CUJ-8 | R3 |
| 5.6 | Retention & encryption config | Retention window (default 90 d hot → archive); trace-window encryption at rest; retention documented | config | retention + encryption honored; erasure journaled | #466 | — | R3 |
| 5.T | Tests | Collector components, chain + rotation, redaction canary, ordering, export/offline verify, retention/erasure | tests | all new paths covered; coverage ≥ 95% | #467 | — | — |
| 5.C | Coverage gate | Enforce coverage ≥ 95% on this milestone's modules | coverage report | ≥ 95%; no untested new path | #468 | — | — |
| 5.L | Lint & type gate | `ruff` zero; `mypy --strict` clean | CI | zero violations | #469 | — | — |
| 5.CR | Code review | Findings in [codereview-log.md](codereview-log.md), resolved | review log | no open findings | #470 | — | — |
| 5.D | Docs | Evidence & proof-format reference, redaction rules, retention/encryption | docs | docs updated + linked here | #471 | — | — |
| 5.CI | Commit & push | On the feature branch | git | pushed | — | — | — |
| 5.W | Update WBS | Checkpoint appended to the index Progress | WBS | checkpoint recorded | — | — | — |

**Exit criteria**

- [ ] Design docs first · all tests pass · coverage ≥ 95% · lint strict clean · docs updated · committed+pushed
- [ ] The snapshot is written before termination; the chain verifies and detects a seeded edit
- [ ] The canary is absent from snapshot and export (redaction proven, not claimed)
- [ ] An exported bundle verifies offline without agenthalt installed

---

Part 3 green ⇒ every cut exists and the scene is preserved; proceed to
[Part 4 (M6–M7)](wbs-v0.1.0-part4-receipt-triggers.md).
