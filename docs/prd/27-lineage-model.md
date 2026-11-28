# PRD 27 — Lineage Model

**BLUF:** Lineage is agenthalt's load-bearing data structure: **containment walks it, proof is built from it,
and the drill interrogates it.** This document defines what counts as a descendant, where edges come from (hook,
runtime adapter, process observation — with a fixed priority), how conflicts resolve, how orphans are handled,
and the exact guarantees: **resolution is best-effort; detection is mandatory.** The rule that governs
everything: **no edge, no containment — and therefore edge discovery is a first-class finding, never a quiet
gap.**

**Status:** Draft — v0.1.0 (2026-11-14) · **Owner:** @deghosal-2026 · **Parent:** agentic-suite #209 · PRD #216

## What counts as a descendant

| Node kind | Examples | Edge source |
|---|---|---|
| `run` | an agent run / session / sub-agent | harness hook or runtime adapter; process observation as fallback |
| `proc` | subprocess, shell, spawned helper | process adapter (pid/ppid tracking) |
| `mcp` | MCP server **spawned by** the agent (stdio transports) | process adapter + gateway inventory |
| `agent` | a delegated child agent (A2A/framework) | runtime adapter; agentwatch inventory cross-check |
| `grant` | credentials **issued to** a member (not a descendant — an attachment) | agentkeys inventory |

**Not descendants (by design):** shared services the agent *calls* but did not spawn (a system-wide MCP
gateway, a database) — those are *routes*, handled by the choke and the blast map, not by subtree kill. A
halt that killed shared infrastructure would be its own incident (RK on collateral damage).

## Edge sources and priority

Multiple sources can record the same spawn; when they disagree, the working rule (the [PRD 21](21-evidence-register-and-method.md)
tension-1 hypothesis, adopted for v0.1.0):

| Priority | Source | Why |
|---|---|---|
| 1 | **Process observation** (pid/ppid, process groups, cgroup membership) | It is what containment *acts on* — if the process layer can't see it, it can't stop it, regardless of what a hook claims |
| 2 | **Runtime adapter** (framework spawn events) | Richer semantics (run ids, delegation), used to *annotate* the process graph |
| 3 | **Harness hook** (where one exists) | Optional accelerant; never load-bearing (DD-06, R5) |

Union, don't intersect: an edge from **any** source enters the graph; the priority resolves *conflicting
attributes* (who spawned whom), never whether the child exists. Duplicate edges are deduplicated by
`(parent, child)` with the highest-priority source recorded.

## Conflict & anomaly resolution

| Case | Resolution |
|---|---|
| Two sources disagree on parentage | Process observation wins; disagreement is journaled as a `lineage_conflict` finding |
| A child appears with no parent (orphan) | Adopts into an `orphans[]` watchlist; surfaced in the readout; **never silently killed** (wrong-direction collateral) and **never silently ignored** (survivor risk) |
| An edge disappears (deletion attempt) | Append-only chain makes the deletion visible; the *attempt* is a self-tamper trigger (`tamper_lineage`, DD-36) |
| An edge is forged (poisoning attempt) | Edge writes authenticate to the adapter identity; a forged edge fails validation; the attempt is journaled |
| Process re-parenting (double-fork daemons) | **Linux:** a double-fork stays in the run's cgroup. A same-user child with write access to a sibling cgroup (a delegated hierarchy) can still move out; the move is detected as `lineage_gap`, and `run --user` (DD-46) prevents it. **macOS:** process groups are escapable (`setsid`); the enrollment supervisor adds ancestry polling + session/uid scoping, and a child that leaves the observed set is a `lineage_gap` finding. Containment there is best-effort until agentseatbelt (Endpoint Security) is deployed (RK-23) |
| Spawn racing the halt | Halt-time subtree snapshot + the **post-halt spawn rule:** any member of a blocked scope that spawns is blocked by inheritance (the choke denies by scope, not by enumerated id) |

## The post-halt spawn rule (the race closer)

The subtree enumeration is a *snapshot*; the choke is *scope-based*. A descendant spawned after the halt
resolves inherits the blocked scope by construction (its parent's scope), so the race window is closed at the
choke even when enumeration missed it — and any post-halt spawn by a halted run is itself a `survivors[]`
signal (a blocked run shouldn't be spawning).

## Guarantees vs best-effort (the honesty table)

| Claimed | Status |
|---|---|
| Every edge is authenticated, append-only, and tamper-evident | **Guaranteed** (chain, PRD 06) |
| A halted scope blocks new actions for members *and* their future spawns | **Guaranteed** (scope inheritance at the choke) |
| The subtree enumeration includes every descendant | **Best-effort** — dependent on spawn-surface visibility (RK-2); gaps are **mandatory findings** |
| Orphans are flagged, never guessed about | **Guaranteed** |
| Zero surviving descendants | **Verified in the drill** — never claimed as an a-priori guarantee ([PRD 14](14-non-goals.md)) |

## Storage & lifecycle

- `lineage/` segments: append-only JSONL, hash-chained with the journal; rotation anchors the head
  ([PRD 15](15-data-model.md)).
- Edges carry `spawn_source` + `recorded_at`; the halt-time snapshot freezes the resolution into the receipt's
  `verifier_input` so offline verification re-derives the same walk.
- Retired runs age out of the hot graph into segments; the chain preserves the history.

## Threats (from [PRD 06](06-security-baseline.md), restated for lineage)

- **Edge deletion** (hide a child) → append-only chain + deletion-as-trigger.
- **Edge poisoning** (halt someone else's subtree) → adapter-authenticated writes + blast-scope proofs.
- **Hidden child** (spawn via an unobserved surface) → orphan watchlist + drill survivor detection + the
  `uncovered_routes` readout.
- **Enumeration flooding** (spawn thousands of children to blow the deadline) → the drill's adversarial leg
  caps enumeration; the deadline produces honest `incomplete`, never a hang.

## Test cases (the lineage suite)

| Test | Asserts |
|---|---|
| `test_edges_append_only` | deleted/reordered segments fail chain verification |
| `test_forged_edge_rejected` | unauthenticated edge write is refused + journaled |
| `test_double_fork_stays` | a daemonizing child is still contained (Linux), or contained / reported as `lineage_gap` — never silent (macOS) |
| `test_orphan_surfaced` | an orphaned run appears in `orphans[]` + readout, is not killed, is not ignored |
| `test_spawn_race` | a child spawned mid-halt is choke-blocked by scope inheritance |
| `test_conflict_priority` | process-observation parentage wins; conflict journaled |
| `test_enumeration_flood` | 10k-member subtree completes or reports `incomplete` within deadline — never hangs |
| `test_drill_survivor` | a deliberately hidden descendant fails the drill (the L4 gate) |
