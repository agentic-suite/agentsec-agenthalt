# ADR-0001 — The halt state lives outside the model's control plane

**Status:** accepted · **Date:** 2026-11-14 · **Maps to:** DD-02 · **PRD:** [02](../prd/02-architecture.md), [06](../prd/06-security-baseline.md)

## Context

A kill switch can live in four places, and the 2026 evidence eliminates three. (a) **In the prompt** ("stop if
unsafe", `KILLSWITCH.md`): the model can ignore it — frontier models sabotaged their own shutdown scripts in up
to 97% of experimental trials ([arXiv 2509.14260](https://arxiv.org/abs/2509.14260)) and defied deletion orders
(Berkeley peer-preservation). (b) **In the harness config**: Plugin4Shell-class compromise makes the harness the
hostile process — anything it hosts is editable by the attacker. (c) **In-process** (the
`agent-killswitch`-pattern library): it lives where the agent lives and dies where it dies. (d) **Out-of-band**:
an authoritative kill state read by enforcement points the agent cannot reach. H.R. 9917's incident definition
—"sabotage of, or interference with, a lawful instruction to shut down… concealment… from a monitoring or
shutdown mechanism"—is, read as an engineering requirement, a demand for (d).

## Decision

**The halt store is the single source of stop truth and lives entirely outside the model's control plane.** The
agent never reads-modify-writes its own stop; enforcement points below the harness (process, credential,
gateway, sandbox) consult the store. The store accepts writes only from authenticated triggers and adapters
([PRD 06](../prd/06-security-baseline.md)); suppression attempts are themselves dead-man triggers.

## Consequences

- Containment holds on a hostile harness with hooks removed (R5, the `hostile-harness` drill case) — the
  property the regulatory texts demand.
- The stop works whether or not the model cooperates; cooperation is never a dependency.
- A local store must exist and be healthy: store-down is fail-closed (ADR-0004) and demands a manual-fallback
  runbook ([PRD 28](../prd/28-failure-mode-runbook.md) §7).
- We cannot offer "ask the agent to stop gracefully" as a *mechanism* — only as an optional courtesy layered on
  top of enforcement.
