# PRD 05 — What (Features)

**BLUF:** agenthalt v0.1.0 is the **composed stop**: one command that halts an agent's whole subtree across every
ecosystem layer (process tree, credentials, MCP gateway, sandbox), preserves a **hash-chained evidence snapshot**,
returns a **proof-of-stop** receipt, and answers the **09:01 readout** — with **dual-choke, fail-closed**
enforcement and a **CI chaos drill** that proves alert → full stop **≤ 1 s**. It absorbs the halt-trigger class of
the shipped predecessor `ai-loopguard` as its **dead-man switch**. It owns no layer (beyond the DD-45 stop-time fallbacks): it composes agentkeys
(revoke), agentgate (disconnect), agentseatbelt/agentkernel (freeze), agentwatch (evidence) and agentpolicy
(triggers).

**Status:** Draft — v0.1.0 (2026-11-14) · **Owner:** @deghosal-2026 · **Parent:** agentic-suite #209 · PRD #216

## v0.1.0 scope

The composed stop (R1) over the whole lineage (R2), with evidence (R3), the full trigger set (R4), zero-hook-
surface containment (R5), a halt event (R6), and pause/resume (R7) — plus the five things the 2026 wave made
table stakes: the **halt store + dual choke + fail-closed** spine (R8), the **lineage registry** (R9), the
**proof-of-stop receipt** (R10), the **09:01 readout** (R11), and the **halt journal** (R12) — and the two honesty
commitments: **irreversibility** (R13) and a **measured drill** (R14). Local-first, CI-verified.

### Cut line (if the schedule slips)

The release gate is R1–R14. If v0.1.0 must ship leaner, these are the candidate deferrals to v0.1.x, in order.
None of them touches a Tier-0 surface ([PRD 40](40-support-versioning-and-deprecation.md)):

1. The SOC pack's vendor-specific mappings (Splunk/Datadog/Elastic). Keep the Sigma rules and Grafana dashboards.
2. The DSAR stub ([PRD 38](38-evidence-privacy-and-data-handling.md)).
3. The generated regulatory crosswalk. Ship the hand-reviewed [PRD 29](29-regulatory-crosswalk.md) instead.
4. The Slack trigger. R4 then ships four of five paths, stated in the release notes.

Nothing in the halt store, lineage, executors, receipt, evidence, journal, or drill path is on this list.

## Requirements

> Priority: **P0** (v0.1.0) · **P1** (v0.2.0) · **P2** (v0.3.0+). Ecosystem-PRD-216 requirements are marked
> *(#216 Rn)*.

| # | Requirement | Acceptance criterion | Pri |
|---|---|---|---|
| **R1** | `halt <agent\|session\|all>` composes a stop across **every available layer**: process termination, credential revocation (agentkeys), gateway disconnect (agentgate), sandbox freeze (agentseatbelt/agentkernel) *(#216 R1)* | Alert → full stop **≤ 1 s** in the chaos drill | P0 |
| **R2** | **Lineage containment** — halt suspends the *entire* subtree (forks, shells, spawned MCP servers, sub-agents), not just the parent *(#216 R2)* | Post-halt, **zero surviving descendants** make a network call (verified) | P0 |
| **R3** | **Evidence preservation** — on halt, snapshot the scene (trace window, process tree, open connections), **hash-chained** and timestamped *(#216 R3)* | Snapshot accepted as a forensic artifact; tamper-evident | P0 |
| **R4** | **Trigger sources** — CLI, alert webhook, PagerDuty button, Slack action, keyboard panic key *(#216 R4)* | Each trigger path tested in drills | P0 |
| **R5** | **Zero-hook-surface containment** — a harness with no hooks (or hooks removed) is still stopped *(#216 R5)* | A hostile-harness fixture that ignores the stop is still contained | P0 |
| **R6** | Every halt (and its trigger) is a **first-class agentwatch event** *(#216 R6)* | SOC dashboards can alarm on halts | P0 |
| **R7** | **Pause/resume** — a paused session resumes with full context and no state corruption *(#216 R7)* | Pause/resume survives a 24 h wall-clock test | P0 |
| **R8** | **Halt store + dual choke + fail-closed** — the authoritative kill state, read by the runtime *and* the gateway before an action executes; unreachable store → deny high-impact actions | Store down → high-impact actions denied; one check the model can talk past is not shipped | P0 |
| **R9** | **Lineage registry** — every spawn records parent → child run ID; subtree resolution is a walk, not a guess; **enrollment** (`agenthalt run` / `attach`) establishes the root ([PRD 02](02-architecture.md) §Mechanisms) | No edge, no containment: an untracked descendant fails the drill | P0 |
| **R10** | **Proof-of-stop receipt** — confirmed stops and revokes (not requests), the refused-call log, and a `survivors[]` list | An unconfirmed descendant reports the halt `incomplete`, never `done` | P0 |
| **R11** | **The 09:01 readout** — what is still running/reachable after the stop (live grants, queued work, siblings, downstream agents) | `status --halt <id>` names every residual with its window | P0 |
| **R12** | **Tamper-evident halt journal** — append-only log of actor, scope, reason, timestamp, run IDs, mode, revoke status | Any edit breaks the chain; a halt cannot be quietly erased | P0 |
| **R13** | **Irreversibility honesty** — no undo; a **compensation list** of already-landed side effects | The receipt lists committed side effects and never claims to reverse them | P0 |
| **R14** | **CI chaos drill** — one command rehearses the full stop and measures it; a survivor fails the build | Alert→full-stop number is **measured** in CI every release | P0 |
| **R15** | **Graduated stops** — escalate-on-act and auto-escalation across `pause` → `quarantine` → `kill`. The rungs themselves and the manual `escalate` command ship at v0.1.0 (R7, [PRD 18](18-stop-modes.md), DD-13) *(#216 R8)* | A paused/quarantined subtree that acts auto-escalates; escalation defaults are configurable and journaled | P1 |
| **R16** | **Dead-man switches** — automatic halt on agentpolicy budget exhaustion, tamper detection, or agentkernel kill triggers *(#216 R9)*; **absorbs `ai-loopguard`'s stuck-loop/budget triggers**. The **self-tamper** triggers on agenthalt's own surfaces (store suppression, hook removal, lineage-edge deletion) ship at v0.1.0 (DD-36) | Each trigger fires a halt with a distinct `reason_code` and an auditable event chain | P1 |
| **R17** | **Halt drills in a box** — one command to rehearse the full stop flow for partner runbooks *(#216 R10)* | A partner runs the drill and gets a pass/fail + measured time | P1 |
| **R18** | **Halt authorization** — RBAC on halt scopes; **dual control** for fleet/tenant-wide halts; time-boxed **break-glass** with auto-revert | A single approval does not release a dual-control fleet halt; break-glass reverts without manual action | P1 |
| **R19** | **Third-party/SaaS agent coverage** — halt via the layers reachable (credentials, gateway) and state plainly what cannot be stopped | Per-agent coverage recorded; the receipt says what it could not reach | P1 |
| **R20** | **Blast map** — what the agent could still reach that the stop did not cut | Each residual named with its window | P1 |
| **R21** | **Offline-verifiable evidence bundle** — receipt + snapshot + agentwatch ref, re-derivable on another machine | A third party verifies a halt without installing agenthalt | P1 |
| **R22** | **Halt from anywhere** — Slack/PagerDuty and **mobile via agentinbox** (with its anti-spoofing) *(#216 R11)* | The halt is raisable and confirmable from Slack and mobile; the trigger names the channel + principal | P1 |
| **R23** | **Fleet halt policies** — "auto-quarantine any agent matching X" *(#216 R12)* | A policy match raises a halt with a logged rule id | P2 |
| **R24** | **External halt attestation** — a third party runs the drill pack against your deployment and publishes the result | A signed drill result is attachable to a release | P2 |

## Killer features

The ten things agenthalt does that no single-layer switch does — the reason it exists as a separate tool:

1. **Composed stop (K1/R1).** One command drives process, credentials, gateway and sandbox. Every commercial
   switch cuts one wire; **no single row empties the grid**, so the value is in the composition.
2. **Lineage containment (K2/R2).** Stop is a **graph operation**, not a process kill: the whole subtree —
   sub-agents, shells, spawned MCP servers — is drained, and the lineage registry makes containment *provable*
   ("no edge, no containment").
3. **Proof-of-stop (K3/R10).** The receipt reports **confirmations, not requests**, and says `incomplete` when it
   cannot prove containment. *"If you cannot show every descendant stopped, you did not kill."*
4. **Evidence snapshot at the moment of stop (K4/R3).** A hash-chained forensic artifact is written **before** the
   pod/process is destroyed — the one moment most tools throw the evidence away.
5. **Dual choke + fail-closed (K5/R8).** The halt state is read by the runtime *and* the gateway, and an
   unreachable halt store **denies** high-impact actions. The model never gets a vote.
6. **Zero-hook-surface containment (K6/R5).** A hostile harness (Plugin4Shell-class) is still stopped, because
   containment lives below the harness.
7. **Graduated stops (K7/R15).** `pause → quarantine → kill` maps onto the AI Kill Switch Act's five-position
   "dimmer" — and onto the everyday need to freeze without killing.
8. **Dead-man switches (K8/R16).** Budget exhaustion, tamper detection, and stuck-loop detection fire the stop
   automatically — the absorbed `ai-loopguard` trigger class, re-pointed from *escalate* to *stop*.
9. **Halt drills in a box (K9/R14, R17).** The "have you pulled it?" test as one command, measured in CI and
   runnable by partners. **Nobody else ships the drill.**
10. **The 09:01 readout + irreversibility honesty (K10/R11, R13).** agenthalt answers "what is still running a
    minute later" and refuses to promise rollback. In a category full of over-claiming, honesty is the feature.

## Feature catalog (v0.1.0)

| # | Feature | Requirement | Origin |
|---|---|---|---|
| F1 | Halt coordinator (`haltd`) — scope resolution, fan-out, confirmation tracking, idempotency | R1, R10 | new |
| F2 | Halt store — authoritative kill state with scopes (`session`/`agent`/`run`/`subtree`/`tenant`/`global`/`tool:<name>`/`writes-disabled`) | R8 | new |
| F3 | Lineage registry — parent → child run ID edges at spawn | R9 | new |
| F4 | Subtree resolver — walk the lineage from a target to every descendant | R2, R9 | new |
| F5 | Executor adapter — process tree (suspend → kill; process group / cgroup) | R1, R2 | new (composes agentseatbelt/agentkernel) |
| F6 | Executor adapter — credentials (agentkeys revoke, incl. issued grants) | R1, R5 | composes agentkeys |
| F7 | Executor adapter — gateway (agentgate session termination; refuses both directions) | R1, R6 | composes agentgate |
| F8 | Executor adapter — sandbox (freeze + egress block) | R1, R7 | composes agentseatbelt/agentkernel |
| F9 | Executor adapter — harness hooks (Stop/PreToolUse), optional and never load-bearing | R5 | new |
| F10 | Evidence collector — trace window + process tree + open connections | R3 | composes agentwatch |
| F11 | Hash-chain + timestamp writer for the snapshot | R3 | new (agentwatch evidence-bundle pattern) |
| F12 | Proof-of-stop receipt builder (lineage, confirmations, refused calls, survivors) | R10 | new |
| F13 | Offline receipt verifier | R10, R21 | new |
| F14 | Readout builder — survivors, live grants, queued work, siblings, downstream | R11 | new |
| F15 | Compensation-list builder — already-landed side effects | R13 | new |
| F16 | Trigger — CLI (`halt`/`pause`/`resume`/`kill`/`status`/`prove`/`drill`) | R4 | new |
| F17 | Trigger — alert webhook receiver (SIEM/agentwatch/agentpolicy) | R4, R16 | new |
| F18 | Trigger — PagerDuty button | R4 | new |
| F19 | Trigger — Slack action | R4, R22 | new |
| F20 | Trigger — keyboard **panic key** | R4 | new |
| F21 | Trigger — dead-man (agentpolicy budget, tamper detection, agentkernel kill) | R16 | absorbs `ai-loopguard` triggers |
| F22 | Halt journal — append-only, tamper-evident | R12 | new |
| F23 | Drill runner + CI job (measured SLO; survivor = fail) | R14, R17 | new (shares agentdrill's pack runner) |
| F24 | Halt event emitter — **agentwatch security-event schema** | R6 | agentwatch schema (new) |
| F25 | Delivery surfaces — library `halt()`, CLI, MCP server (`halt`/`status`), HTTP + webhook receiver | R1, R4 | new |
| F26 | Adapter registry — executor + trigger adapters, validated at load | R1 | new |
| F27 | Mode controller — pause / quarantine / kill | R7, R15 | new |
| F28 | Authorization — RBAC scopes, dual-control quorum, break-glass + auto-revert | R18 | new (P1) |
| F29 | Blast map | R20 | new (P1) |
| F30 | Offline evidence bundle | R21 | new (P1) |
| F31 | Enrollment — `agenthalt run` supervisor + `agenthalt attach --pid` | R9 | new (DD-38) |
| F32 | Trigger — self-tamper (store suppression, hook removal, lineage-edge deletion) | R5, R8, R9 | new (DD-36) |
| F33 | Executor — built-in egress fallback (used only where no sandbox layer is deployed) | R1, R7 | new (DD-45) |

## P1/P2 feature additions

- **R15 graduated stops / F27** — pause/quarantine/kill, mapped to the regulatory dimmer.
- **R16 dead-man switches / F21** — the absorbed `ai-loopguard` trigger class (repeated error, test-failure loop,
  schema-invalid, hallucination cycle, budget ceiling), re-pointed from escalation to stop.
- **R17 drills in a box / F23** — runbook automation and a drill library.
- **R18 authorization / F28**, **R19 third-party coverage**, **R20 blast map / F29**, **R21 offline bundle /
  F30**, **R22 halt-from-anywhere**.
- **R23 fleet halt policies**, **R24 external attestation** — post-v0.2.0.

## Compatibility (harness-agnostic by construction)

> **Non-negotiable:** agenthalt is agentic-harness-agnostic or explicitly harness-compatible. It is
> harness-agnostic **by construction** — containment happens at the process/credential/sandbox layers, so it
> applies to any harness whose processes it enrolls, including one with **zero hook surface**; the compatibility
> table states which were exercised.

| Tier | Harness / ecosystem | v0.1.0 requirement |
|---|---|---|
| 1 — Coding agents | Claude Code · Cursor · GitHub Copilot · Codex CLI · Gemini CLI | ≥ 2 at v0.1.0, all 5 by v0.3.0 — via the layers agenthalt composes (process/credential/gateway/sandbox), incl. Copilot where hooks are closed |
| 2 — Frameworks | LangGraph · CrewAI · OpenAI Agents SDK · AutoGen · LlamaIndex · PydanticAI · smolagents | Reached through the runtime/credential layers; framework adapters by v0.3.0 where a surface exists |
| 3 — Protocol / enterprise | Generic MCP clients · enterprise platforms | MCP gateway (agentgate) covers MCP clients; enterprise platforms via the credential/identity layers |

Full matrix: [PRD 19](19-harness-compatibility.md); the ecosystem matrix
([00-harness-compatibility.md](https://github.com/agentic-suite/.github)) — agenthalt's row: *"Composes all layers
(harness-agnostic) — the 5 via the layers it composes."*

## Explicit non-requirements

- **No detection / no classifier / no ML in the stop path** — agenthalt is deterministic enforcement; detection
  is somebody else's job.
- **No new protocol** — the halt signal is an agentwatch event; that is the entire standard surface.
- **No undo / rollback** — agenthalt blocks the next action; it never promises to reverse one that landed.
- **No console/UI beyond CLI** in v1.
- **agenthalt owns no layer** — it is not a PEP, a PDP, a gateway, a credential broker, or a sandbox. Its minimal process and egress
  executors are stop-time fallbacks, not a confinement layer (DD-45).
- **No false claim of synchronous cancel** — blocking new actions is the hard guarantee; cancelling in-flight
  calls is best-effort and the UX says so.
- **No claim to stop what it cannot reach** — third-party-hosted processes, static keys stored elsewhere, and
  already-landed side effects are named, not hidden.

## Standards it must meet

- **agentwatch security-event schema** — halt as a first-class event any SIEM can trigger on.
- **Hash-chained, timestamped evidence format** — documented, court-usable.
- **OTel GenAI conventions** — evidence and events align with the ecosystem's telemetry.
- **Regulatory alignment** — the AI Kill Switch Act capability set (stop inference / terminate access / suspend /
  shut down), the UK NCSC "pull the plug" guidance, and EU AI Act Art. 14's stop button map onto agenthalt's
  layers and triggers.

## Fit in the ecosystem

**Pure orchestration** — the composed power of agentkeys (revoke), agentkernel/agentseatbelt (freeze), agentgate
(disconnect), agentwatch (evidence) and agentpolicy (auto-triggers). Dependency position:
`agenthalt ◄── agentkeys + enforcers + watch (composition only)`. It is the ecosystem's most visible tool, its
narrowest primitive, and the emotional close of every demo — Wave 0's headline: **"stop it."**

## Success metrics (outcome-level)

- **Stop time:** alert → full stop (as defined in [PRD 39](39-performance-budget.md): choke blocking, subtree
  suspended, revocable grants confirmed, first evidence segment committed) **≤ 1 s**, continuously
  verified in CI.
- **Containment:** **zero surviving descendants** post-halt, proven in the drill.
- **Reliability:** zero failed halts across a release cycle.
- **Proof:** 100 % of halts return a receipt; a halt that cannot prove containment reports `incomplete`.
- **Evidence:** the snapshot is accepted as a forensic artifact in review.
- **Adoption:** halts appear in real partner runbooks; the drill is run by someone who did not build it.

## Anti-metrics (what we refuse to optimize)

- **"Kill switch" as a marketing label** — a switch nobody has pulled is a label on a box; we measure the drill.
- **False success** — never report `done` on a request; never hide a survivor.
- **Rollback theater** — never imply an undone action.
- **Single-layer shortcuts** — never claim a stop that one layer cannot deliver.
