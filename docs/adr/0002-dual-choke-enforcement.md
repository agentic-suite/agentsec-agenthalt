# ADR-0002 — Dual-choke enforcement: the runtime and the gateway both read the halt state

**Status:** accepted · **Date:** 2026-11-14 · **Maps to:** DD-02 · **PRD:** [02](../prd/02-architecture.md), [39](../prd/39-performance-budget.md)

## Context

The halt state must be *checked* somewhere before an action executes. Candidates: (a) **runtime-only** — the
agent's runtime checks before each step: bypassed by any path that leaves the runtime (a direct provider call,
a spawned process, a second harness); (b) **gateway-only** — the MCP proxy refuses calls: bypassed by every
route that doesn't cross it (the Tigera drill's own finding: gateway denial leaves direct connections, local
models, and volume writes alive); (c) **feature flag with cache** — the category's known failure: a multi-minute
cache in front of a kill state means the stop propagates after the damage; (d) **dual choke** — both the runtime
and the tool gateway check the store before an action executes. The practitioner bar is explicit: *"one check
the model can talk past is a suggestion with better branding."*

## Decision

**The halt state is read at two independent chokes — in the runtime (before an action) and at the gateway
(agentgate, before a call leaves) — and at no other single point.** Any cache in front of the store has a
**seconds-scale TTL, never minutes**; the choke read is a local operation inside the ≤50 ms synchronous budget
([PRD 39](../prd/39-performance-budget.md)).

## Consequences

- A bypass of one choke is covered by the other; direct-provider routes fall to the sandbox egress block, and
  the readout names whatever neither choke sees (`uncovered_routes`).
- Wave 0 ships without agentgate: the gateway half reports `unsupported`, the receipt says `partial-layer`
  honestly (DD-18) — the architecture is chosen now so adding agentgate closes a leg, not a redesign.
- Two enforcement points to maintain and drill; the per-platform drill legs cover both.
- Scope-based checking (not enumerated-id matching) makes the choke race-proof against post-halt spawns
  ([PRD 27](../prd/27-lineage-model.md)).
