# ADR-0008 — Lineage edge priority: process observation wins over hooks and runtimes

**Status:** accepted · **Date:** 2026-11-14 · **Maps to:** DD-23 · **PRD:** [27](../prd/27-lineage-model.md), [06](../prd/06-security-baseline.md)

## Context

Three sources can record the same spawn, and they disagree under stress: (a) **harness hooks** — richest
semantics, but removed or lying exactly when the harness is compromised (ADR-0005's premise); (b) **runtime
adapters** — framework-native run ids and delegation chains, but framework-scoped and spoofable by a hostile
orchestrator; (c) **process observation** (pid/ppid, process groups, cgroup membership) — the *only* source
aligned with what containment actually acts on: if the process layer cannot see the child, it cannot suspend
it, whatever a hook claims. The disagreement case is not hypothetical: a double-fork daemon, a re-parented
orphan, or a lying hook each produce contradictory edges.

## Decision

**Edges union for existence; process observation wins for parentage.** An edge from any authenticated source
enters the graph (union — a child any source saw is a child we track), but when sources disagree on parentage,
the process-observed edge is authoritative, and the disagreement is journaled as a `lineage_conflict` finding.
All edge writes authenticate to the adapter identity and are append-only + hash-chained; deletion attempts are
themselves self-tamper triggers (`tamper_lineage`, ADR-0010; [PRD 06](../prd/06-security-baseline.md)).

## Consequences

- Containment and lineage can never desynchronize: the graph containment walks is the graph the process layer
  can act on — a lying hook cannot hide a child from the subtree resolver.
- Hook/runtime metadata keeps its value as *annotation* (run ids, delegation semantics, receipt readability)
  without ever being load-bearing for parentage.
- Honest costs: process observation is best-effort at the edges (unobserved spawn surfaces → orphan watchlist,
  `uncovered_routes`, drill survivor detection); enumerations remain bounded by the halt deadline, never a
  hang ([PRD 27](../prd/27-lineage-model.md) `test_enumeration_flood`).
- On macOS, process groups are escapable (`setsid`); the enrollment supervisor (ADR-0009) adds ancestry
  polling, and an escaped child is a `lineage_gap` finding, never a silent loss (RK-23).
- The conflict cases are first-class drill/test cases (`edge-forgery`, `test_double_fork_stays`,
  `test_conflict_priority`) — this ADR's priority rule is CI-enforced, not documented aspiration.
