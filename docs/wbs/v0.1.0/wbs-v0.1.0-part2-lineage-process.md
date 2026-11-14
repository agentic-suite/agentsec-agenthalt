# WBS v0.1.0 — Part 2: Lineage & Process Containment (M2–M3)

**BLUF:** **M2** builds the **lineage registry** and the **subtree resolver** — the graph containment walks and
the proof is built from (ADR-0008: process observation wins for parentage). **M3** delivers the **process-tree
executor** and the first end-to-end composed stop — the moment "we couldn't stop it" becomes "we stopped it."
Everything here is v0.1.0.

> **Standard exit criteria + closure apply to every milestone** — see the [index](wbs-v0.1.0-index.md):
> **design docs first (`.D0`)**, then implement, then close with **`.T` · `.C` · `.L` · `.CR` · `.D` · `.CI` ·
> `.W`**.

---

## Milestone M2 — Lineage registry & subtree resolution

**Goal:** the **lineage registry** (append-only, hash-chained edges; adapter-authenticated writes) and the
**subtree resolver** that turns a halt target into the full member set + their grants. Rules fixed here: **no
edge, no containment**; process observation wins for parentage (ADR-0008); orphans are surfaced, never guessed
about; a child spawned mid-halt is blocked by **scope inheritance** (the post-halt spawn rule).

**CUJ:** **CUJ-3** (contain the lineage) · **Requirements:** [PRD 27](../../prd/27-lineage-model.md),
[PRD 15](../../prd/15-data-model.md), [PRD 06](../../prd/06-security-baseline.md) (edge tamper defenses),
**R2, R9**; [PRD 11](../../prd/11-decisions.md) DD-24.

**Work items**

| # | Task | Description | Deliverable | Acceptance | Issue | CUJ | Req |
|---|---|---|---|---|---|---|---|
| 2.D0 | **Design docs first** | Lineage model: node kinds, edge sources + priority, conflict/orphan rules, post-halt spawn rule, segment format | docs | reviewed before code | #30 | — | — |
| 2.1 | Lineage edge model + chained segments | `parent_run → child_run` edges with `spawn_source`/`recorded_at`; append-only JSONL segments hash-chained with the journal; rotation anchor | registry | edges verify; a deleted edge is detectable | #31 | — | R9 |
| 2.2 | Edge ingestion adapters | Process observation (pid/ppid, process groups, cgroup membership) as primary; runtime/hook as annotation; **adapter-authenticated writes** | ingestion | forged edge refused; process edges win | #32 | — | R9 |
| 2.3 | **Subtree resolver** | Walk the lineage from a target to every descendant + collect member grants; **deadline-bounded** enumeration (flood-safe, never a hang) | resolver | resolves a 3-level subtree; flood completes or reports incomplete | #33 | CUJ-3 | R2 |
| 2.4 | Conflict resolution + `lineage_conflict` finding | Sources disagree on parentage ⇒ process-observed edge authoritative; the conflict is journaled | resolution | conflict test: process wins + finding logged | #34 | — | R9 |
| 2.5 | Orphan watchlist + **post-halt spawn rule** | Orphans surfaced in the readout (never silently killed/ignored); a member of a blocked scope that spawns is blocked by **scope inheritance** | resolver + choke hook | orphan surfaced; post-halt child never acts | #35 | CUJ-3 | R2 |
| 2.6 | Edge tamper defenses | Deletion attempt ⇒ tamper finding (dead-man trigger hook); forged-edge rejection; append-only enforcement | defenses | `test_edges_append_only`, `test_forged_edge_rejected` | #36 | — | R9 |
| 2.T | Tests | Edge chain, ingestion priority, subtree walk, conflict priority, double-fork, orphan surfacing, spawn race, enumeration flood | tests | all new paths covered; coverage ≥ 95% | #37 | — | — |
| 2.C | Coverage gate | Enforce coverage ≥ 95% on this milestone's modules | coverage report | ≥ 95%; no untested new path | #38 | — | — |
| 2.L | Lint & type gate | `ruff` zero; `mypy --strict` clean | CI | zero violations | #39 | — | — |
| 2.CR | Code review | Findings in [codereview-log.md](codereview-log.md), resolved | review log | no open findings | #40 | — | — |
| 2.D | Docs | Lineage-model reference, edge-priority rules, orphan/post-halt semantics | docs | docs updated + linked here | #41 | — | — |
| 2.CI | Commit & push | On the feature branch | git | pushed | — | — | — |
| 2.W | Update WBS | Checkpoint appended to the index Progress | WBS | checkpoint recorded | — | — | — |

**Exit criteria**

- [ ] Design docs first · all tests pass · coverage ≥ 95% · lint strict clean · docs updated · committed+pushed
- [ ] Subtree resolution walks the full lineage; process observation wins on conflict
- [ ] Orphans are surfaced; a mid-halt spawn is choke-blocked by scope inheritance
- [ ] Edge deletion/forgery is detected; the chain verifies

---

## Milestone M3 — Process-tree containment (executor core)

**Goal:** the **executor adapter contract** + registry, and the **process-tree executor** (macOS process groups,
Linux cgroups) that suspends then kills the whole subtree — the first milestone where a halt actually stops a
running agent. Fixes the **block-new-first ordering** and **per-target confirmations** (`confirmed` /
`requested` / `unsupported` / `failed`) with deadline handling.

**CUJ:** **CUJ-1** (stop one runaway agent), **CUJ-7** (freeze the sandbox) · **Requirements:**
[PRD 02](../../prd/02-architecture.md), [PRD 32](../../prd/32-build-vs-integrate.md) (adapter boundary),
[PRD 19](../../prd/19-harness-compatibility.md) (per-OS adapters), **R1, R2**;
[PRD 11](../../prd/11-decisions.md) DD-01/05/23.

**Work items**

| # | Task | Description | Deliverable | Acceptance | Issue | CUJ | Req |
|---|---|---|---|---|---|---|---|
| 3.D0 | **Design docs first** | Executor contract (response shape, signatures, timeouts), per-OS suspend semantics, block-new-first sequencing | docs | reviewed before code | #42 | — | — |
| 3.1 | Executor adapter contract + registry | Documented schema (`confirmed`/`requested`/`unsupported`/`failed`); validated at load (`unknown adapter → ConfigError`); **no inline enforcement allowed** | contract + registry | bad adapter fails load; schema enforced | #43 | — | R1 |
| 3.2 | Process executor — macOS | Process-group suspend (`SIGSTOP`) then kill; subtree via lineage | executor | subtree suspended then killed; zero survivors (probe) | #44 | CUJ-1 | R1, R2 |
| 3.3 | Process executor — Linux | cgroup freeze + kill; process-group semantics | executor | same on Linux runner | #45 | CUJ-1 | R1, R2 |
| 3.4 | Block-new-first sequencing | Choke write synchronous; suspend/kill fan out in parallel within deadline | coordinator | ordering test; block precedes termination | #46 | — | R1 |
| 3.5 | Per-target confirmations + deadline | Each target reports status; deadline miss ⇒ `requested`; never rounds up to a stop | confirmations | requested≠confirmed enforced | #47 | — | R1 |
| 3.6 | Sandbox egress-block executor | agentseatbelt interface: egress block + freeze; open connections fail on next send | executor | egress blocked; open socket fails next send | #48 | CUJ-7 | R1 |
| 3.T | Tests | Adapter contract/load, per-OS suspend/kill, ordering, confirmations/deadline, egress block, first end-to-end halt | tests | all new paths covered; coverage ≥ 95% | #49 | — | — |
| 3.C | Coverage gate | Enforce coverage ≥ 95% on this milestone's modules | coverage report | ≥ 95%; no untested new path | #50 | — | — |
| 3.L | Lint & type gate | `ruff` zero; `mypy --strict` clean | CI | zero violations | #51 | — | — |
| 3.CR | Code review | Findings in [codereview-log.md](codereview-log.md), resolved | review log | no open findings | #52 | — | — |
| 3.D | Docs | Executor adapter reference, per-OS suspend notes, block-new-first order | docs | docs updated + linked here | #53 | — | — |
| 3.CI | Commit & push | On the feature branch | git | pushed | — | — | — |
| 3.W | Update WBS | Checkpoint appended to the index Progress | WBS | checkpoint recorded | — | — | — |

**Exit criteria**

- [ ] Design docs first · all tests pass · coverage ≥ 95% · lint strict clean · docs updated · committed+pushed
- [ ] One command suspends then kills the whole subtree on macOS **and** Linux
- [ ] Block-new precedes termination; confirmations never round `requested` up to a stop
- [ ] Demo 1 (the Replit stop) is runnable on the process + sandbox layers

---

Part 2 green ⇒ the graph and its first cuts exist; proceed to
[Part 3 (M4–M5)](wbs-v0.1.0-part3-executors-evidence.md).
