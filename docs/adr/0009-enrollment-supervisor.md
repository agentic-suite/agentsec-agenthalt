# ADR-0009 — Enrollment: agents enter the lineage through a supervisor (`agenthalt run` / `attach`)

**Status:** accepted · **Date:** 2026-11-27 · **Maps to:** DD-38 · **PRD:** [02](../prd/02-architecture.md) §Mechanisms, [27](../prd/27-lineage-model.md), [37](../prd/37-cli-and-output-ux-spec.md)

## Context

"No edge, no containment" (R9) assumes every run has a lineage **root**, but nothing in the PRD said how a run
gets one. Hooks can't be the answer: they are optional and never load-bearing (ADR-0005), and zero-hook
harnesses have none. Process observation (ADR-0008) can follow descendants once it knows where to start, but it
needs that starting point. The platforms differ: on Linux an unprivileged child cannot leave its cgroup, but on
macOS a child can leave its process group with `setsid` or a double-fork into a new session.

## Decision

**Agents are enrolled through a supervisor.** `agenthalt run -- <cmd>` launches the agent as a child of the
supervisor, which owns its process group (macOS) or a dedicated cgroup (Linux) and writes the root edge before
the agent runs. `agenthalt attach --pid <pid>` enrolls an already-running agent best-effort: the receipt
reports `lineage_verified: false` until a full walk succeeds. An un-enrolled agent can only be halted by
explicit pid, and the receipt says so.

On macOS the supervisor adds ancestry polling plus session/uid scoping. A child that leaves the observed set is
a `lineage_gap` finding, never a silent loss. Containment there is best-effort until agentseatbelt (Endpoint
Security) is deployed.

## Consequences

- Every enrolled run has an authenticated root edge written by the supervisor, so subtree resolution always
  has a starting point.
- Adoption cost: operators change how they launch agents (`agenthalt run -- claude …`). `attach` is the
  migration path for agents already running.
- On macOS the "zero survivors" claim stays *verified in the drill* rather than structural; an escape is a
  finding and an RK-23 risk, stated in the receipt.
- The supervisor is a new process that must not become a single point of failure. If it dies, the agent keeps
  running under its process group or cgroup, and the store and choke still apply.

## Alternatives considered

- **Hook-based enrollment** — rejected: it breaks ADR-0005 on zero-hook harnesses.
- **System-wide process scanning with heuristics** to guess which processes are agents — rejected: it guesses
  parentage, and the lineage model forbids guessing.

## Amendment (2026-11-27, ADR-0012)

On macOS the built-in egress cut ([ADR-0012](0012-built-in-egress-fallback.md)) filters by user, so it needs the
enrolled run under a dedicated OS user. Whether the supervisor can launch a run that way is open, to be decided
in the M2 design. Until then the cut reports `unsupported` on macOS.
