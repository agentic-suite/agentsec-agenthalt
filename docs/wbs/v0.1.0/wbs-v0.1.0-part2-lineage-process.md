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

**Goal:** the **enrollment supervisor** (ADR-0009), the **lineage registry** (append-only, hash-chained edges;
adapter-authenticated writes) and the **subtree resolver** that turns a halt target into the full member set + their grants. Rules fixed here: **no
edge, no containment**; process observation wins for parentage (ADR-0008); orphans are surfaced, never guessed
about; a child spawned mid-halt is blocked by **scope inheritance** (the post-halt spawn rule).

**CUJ:** **CUJ-3** (contain the lineage) · **Requirements:** [PRD 27](../../prd/27-lineage-model.md),
[PRD 15](../../prd/15-data-model.md), [PRD 06](../../prd/06-security-baseline.md) (edge tamper defenses),
**R2, R9**; [PRD 11](../../prd/11-decisions.md) DD-24.

**Work items**

| # | Task | Description | Deliverable | Acceptance | Issue | CUJ | Req |
|---|---|---|---|---|---|---|---|
| 2.D0 | **Design docs first** | Lineage model: node kinds, edge sources + priority, conflict/orphan rules, post-halt spawn rule, segment format, **enrollment supervisor** + macOS escape handling (ADR-0009); decides whether `run` can launch under a dedicated OS user (needed by DD-45 on macOS); adopts open decision #1 (process observation wins, ADR-0008) and closes #11 (enrollment mechanism) | docs | reviewed before code | #424 | — | — |
| 2.1 | Lineage edge model + chained segments | `parent_run → child_run` edges with `spawn_source`/`recorded_at`; append-only JSONL segments hash-chained with the journal; rotation anchor | registry | edges verify; a deleted edge is detectable | #425 | — | R9 |
| 2.2 | Edge ingestion adapters | Process observation (pid/ppid, process groups, cgroup membership) as primary; runtime/hook as annotation; **adapter-authenticated writes** | ingestion | forged edge refused; process edges win | #426 | — | R9 |
| 2.3 | **Subtree resolver** | Walk the lineage from a target to every descendant + collect member grants; **deadline-bounded** enumeration (flood-safe, never a hang) | resolver | resolves a 3-level subtree; flood completes or reports incomplete | #427 | CUJ-3 | R2 |
| 2.4 | Conflict resolution + `lineage_conflict` finding | Sources disagree on parentage ⇒ process-observed edge authoritative; the conflict is journaled | resolution | conflict test: process wins + finding logged | #428 | — | R9 |
| 2.5 | Orphan watchlist + **post-halt spawn rule** | Orphans surfaced in the readout (never silently killed/ignored); a member of a blocked scope that spawns is blocked by **scope inheritance** | resolver + choke hook | orphan surfaced; post-halt child never acts | #429 | CUJ-3 | R2 |
| 2.6 | Edge tamper defenses | Deletion attempt ⇒ tamper finding feeding the `tamper_lineage` self-tamper trigger (DD-36, wired in 8.2); forged-edge rejection; append-only enforcement | defenses | `test_edges_append_only`, `test_forged_edge_rejected` | #430 | — | R9 |
| 2.7 | **Enrollment supervisor** (`agenthalt run` / `attach`) | `run -- <cmd>` launches the agent owning its process group (macOS) / cgroup (Linux) and records the root edge; `attach --pid` enrolls best-effort (`lineage_verified: false`); macOS `setsid`/double-fork escape ⇒ ancestry polling + `lineage_gap` finding (DD-38, RK-23); whether `run` can launch under a dedicated OS user is decided in 2.D0 (DD-45) | supervisor + CLI | `run` records a root before the agent starts; an escaped child is reported, never silent | #569 | CUJ-3 | R9 |
| 2.T | Tests | Edge chain, ingestion priority, subtree walk, conflict priority, double-fork, orphan surfacing, spawn race, enumeration flood, enrollment (`run`/`attach`), macOS escape reporting | tests | all new paths covered; coverage ≥ 95% | #431 | — | — |
| 2.C | Coverage gate | Enforce coverage ≥ 95% on this milestone's modules | coverage report | ≥ 95%; no untested new path | #432 | — | — |
| 2.L | Lint & type gate | `ruff` zero; `mypy --strict` clean | CI | zero violations | #433 | — | — |
| 2.CR | Code review | Findings in [codereview-log.md](codereview-log.md), resolved | review log | no open findings | #434 | — | — |
| 2.D | Docs | Lineage-model reference, edge-priority rules, orphan/post-halt semantics | docs | docs updated + linked here | #435 | — | — |
| 2.CI | Commit & push | On the feature branch | git | pushed | — | — | — |
| 2.W | Update WBS | Checkpoint appended to the index Progress | WBS | checkpoint recorded | — | — | — |

**Exit criteria**

- [x] Design docs first · all tests pass · coverage ≥ 95% · lint strict clean · docs updated · committed+pushed
- [x] Subtree resolution walks the full lineage; process observation wins on conflict
- [x] Orphans are surfaced; a mid-halt spawn is choke-blocked by scope inheritance
- [x] Edge deletion/forgery is detected; the chain verifies
- [x] Agents enroll via `agenthalt run` / `attach`; a macOS process-group escape is a `lineage_gap` finding

**Docs (2.D):** [M2 design](../../design/m2-lineage-enrollment.md) · [lineage and enrollment](../../reference/lineage.md) ·
[CLI reference](../../reference/cli.md) · [state layout](../../reference/state-layout.md) · [code review](codereview-log.md)

---

## Milestone M3 — Process-tree containment (executor core)

**Goal:** the **executor adapter contract** + registry, and the **process-tree executor** (macOS process groups,
Linux cgroups) that suspends then kills the whole subtree — the first milestone where a halt actually stops a
running agent. Fixes the **block-new-first ordering** and **per-target confirmations** (`confirmed` /
`requested` / `unsupported` / `failed`) with deadline handling.

**CUJ:** **CUJ-1** (stop one runaway agent), **CUJ-7** (freeze the sandbox) · **Requirements:**
[PRD 02](../../prd/02-architecture.md), [PRD 32](../../prd/32-build-vs-integrate.md) (adapter boundary),
[PRD 19](../../prd/19-harness-compatibility.md) (per-OS adapters), **R1, R2**;
[PRD 11](../../prd/11-decisions.md) DD-01/05/23/45 ([ADR-0012](../../adr/0012-built-in-egress-fallback.md)).

**Work items**

| # | Task | Description | Deliverable | Acceptance | Issue | CUJ | Req |
|---|---|---|---|---|---|---|---|
| 3.D0 | **Design docs first** | Executor contract (response shape, signatures, timeouts), per-OS suspend semantics, block-new-first sequencing, built-in egress fallback (DD-45, ADR-0012: verify the nftables/pf hypotheses, privileges, `unsupported` paths, `doctor` check) | docs | reviewed before code | #436 | — | — |
| 3.1 | Executor adapter contract + registry | Documented schema (`confirmed`/`requested`/`unsupported`/`failed`); validated at load (`unknown adapter → ConfigError`); **no inline enforcement allowed** | contract + registry | bad adapter fails load; schema enforced | #437 | — | R1 |
| 3.2 | Process executor — macOS | Process-group suspend (`SIGSTOP`) then kill; subtree via lineage | executor | subtree suspended then killed; zero survivors (probe) | #438 | CUJ-1 | R1, R2 |
| 3.3 | Process executor — Linux | cgroup freeze + kill; process-group semantics | executor | same on Linux runner | #439 | CUJ-1 | R1, R2 |
| 3.4 | Block-new-first sequencing | Choke write synchronous; suspend/kill fan out in parallel within deadline; on zero-hook harnesses the runtime choke is realised below the agent — scope-based suspension + egress block deny the next action (PRD 02 §Mechanisms, ADR-0002) | coordinator | ordering test; block precedes termination | #440 | — | R1 |
| 3.5 | Per-target confirmations + deadline | Each target reports status; deadline miss ⇒ `requested`; never rounds up to a stop; confirmations are produced signable — the signing hook is defined here and the OS executor's cuts carry `attestation: self`; M3 tests sign with a test key until 4.6 lands the key model | confirmations | requested≠confirmed enforced | #441 | — | R1 |
| 3.6 | Sandbox egress-block executor | agentseatbelt interface **plus the built-in Linux fallback** (DD-45, DD-51, ADR-0012): iptables by cgroup; egress block; open connections fail on next send; `unsupported` when unprivileged or without its own cgroup. **macOS pf cut moved to 0.3.0** | executor | egress blocked; open socket fails next send; honest `unsupported`; operator's own network never blocked; `doctor` reports the fallback's privileges | #442 | CUJ-7 | R1 |
| 3.T | Tests | Adapter contract/load, per-OS suspend/kill, ordering, confirmations/deadline, egress block (incl. `unsupported` paths), first end-to-end halt | tests | all new paths covered; coverage ≥ 95% | #443 | — | — |
| 3.C | Coverage gate | Enforce coverage ≥ 95% on this milestone's modules | coverage report | ≥ 95%; no untested new path | #444 | — | — |
| 3.L | Lint & type gate | `ruff` zero; `mypy --strict` clean | CI | zero violations | #445 | — | — |
| 3.CR | Code review | Findings in [codereview-log.md](codereview-log.md), resolved | review log | no open findings | #446 | — | — |
| 3.D | Docs | Executor adapter reference, per-OS suspend notes, block-new-first order | docs | [executors](../../reference/executors.md), [design](../../design/m3-process-containment.md) | #447 | — | — |
| 3.CI | Commit & push | On the feature branch | git | pushed | — | — | — |
| 3.W | Update WBS | Checkpoint appended to the index Progress | WBS | checkpoint recorded | — | — | — |

**Exit criteria**

- [x] Design docs first · all tests pass · coverage ≥ 95% · lint strict clean · docs updated · committed+pushed
- [x] One command suspends then kills the whole subtree on macOS **and** Linux (macOS: CI runners and dev host;
  Linux: CI plus a privileged container for the cgroup and firewall paths)
- [x] Block-new precedes termination; confirmations never round `requested` up to a stop
- [x] On a zero-hook fixture, suspension + egress block alone deny the next action (where the egress cut is
  available; elsewhere it reports `unsupported` and the receipt is `partial-layer`)
- [x] Demo 1 (the Replit stop) is runnable on the process + sandbox layers
  ([`examples/demo1_replit_stop.py`](../../../examples/demo1_replit_stop.py); sandbox is `unsupported` on macOS, DD-51)

---

Part 2 green ⇒ the graph and its first cuts exist; proceed to
[Part 3 (M4–M5)](wbs-v0.1.0-part3-executors-evidence.md).
