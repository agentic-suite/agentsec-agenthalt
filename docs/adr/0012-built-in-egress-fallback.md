# ADR-0012 — A minimal built-in egress fallback, so `quarantine` works without agentseatbelt

**Status:** accepted · **Date:** 2026-11-27 · **Maps to:** DD-45 (amends DD-01) · **PRD:** [02](../prd/02-architecture.md) §Mechanisms, [18](../prd/18-stop-modes.md), [32](../prd/32-build-vs-integrate.md)

## Context

`quarantine` ships at v0.1.0 (DD-13) and is defined as pause plus a network cut plus a credential-issuance
freeze. All three self-tamper triggers default to it (ADR-0010). The network cut was routed to agentseatbelt
(macOS) and agentkernel (Linux). agentseatbelt has no implementation yet and agentkernel is Wave 2, so v0.1.0
had no way to make the cut it promised.

## Decision

agenthalt ships a **minimal built-in egress cut**, used only where no composed sandbox layer is deployed. This
amends DD-01 for stop-time fallbacks only: agenthalt confines nothing during normal operation.

- Linux: nftables rules matching the enrolled run's cgroup.
- macOS: pf. It matches by user, not by process tree, so it needs the run under a dedicated OS user, and
  existing connection states must be flushed.
- Both need elevated privileges, which `doctor` checks.
- Where the cut cannot be made safely, the layer reports `unsupported` and the receipt is `partial-layer`. It
  never blocks the operator's own user.
- Confirmations carry `attestation: self` (ADR-0011).

The platform mechanisms are working hypotheses, to be verified in the M3 design before code.

## Consequences

- ADR-0010 holds as written.
- M3 grows by one executor per platform.
- On a default macOS setup (agent running as the operator's user) the network cut is `unsupported`.

## Alternatives considered

- **Defer `quarantine`** — rejected: the self-tamper triggers would need a new default and the ladder would lose
  its middle rung.
- **Ship `quarantine` with the network cut always `unsupported`** — rejected: it would behave as `pause`.

## Amendment (2026-11-27, M3 design, DD-51)

Owner decision: **the macOS pf cut moves to 0.3.0.** v0.1.0 ships the Linux cut only; on macOS the network layer
is `unsupported` and `quarantine` is a freeze.

The Linux hypothesis was tested and changed: Docker Desktop's kernel is built without `nft_socket`, so the cut
uses the iptables cgroup match (`iptables`/`ip6tables -m cgroup --path`) with `REJECT` (TCP reset), which was
verified in a privileged container to refuse new connections and fail an open connection on its next send.
