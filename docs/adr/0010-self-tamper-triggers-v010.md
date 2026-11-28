# ADR-0010 — Self-tamper triggers ship at v0.1.0; external dead-man switches stay v0.2.0

**Status:** accepted · **Date:** 2026-11-27 · **Maps to:** DD-36 (amends the scope of DD-14) · **PRD:** [16](../prd/16-trigger-catalogue.md), [06](../prd/06-security-baseline.md), [30](../prd/30-threat-model.md)

## Context

DD-14 deferred all dead-man switches to v0.2.0. But several v0.1.0 commitments assume that an attack on the
stop itself raises a halt:

- ADR-0001: suppression attempts are triggers.
- ADR-0005: hook removal is tamper detection.
- ADR-0008: edge deletion is a trigger.
- The `edge-forgery` drill case.
- The PRD 30 self-halt case "kill the store mid-drill ⇒ tamper halt fires".

The PRD set therefore contradicted itself. The two kinds of trigger differ: budget, kernel and stuck-loop
triggers need an **external producer** (agentpolicy, agentkernel, a loop detector), while self-tamper
conditions are seen by agenthalt's own integrity checks, inside trust boundary 2.

## Decision

**Three self-tamper triggers ship at v0.1.0:**

| Trigger | Condition | Default mode |
|---|---|---|
| `tamper_store` | Store suppression | `quarantine` |
| `tamper_hooks` | Hook/config hash mismatch | `quarantine` |
| `tamper_lineage` | Lineage-edge deletion | `quarantine` |

They are executed through the process/sandbox layers and journaled with the tampered artifact's identity.
Inputs: the store integrity signal (WBS 1.6), the lineage-edge deletion finding (WBS 2.6), and the hook/config
hash check (WBS 8.2).

External dead-man switches (budget exhaustion, policy tamper, kernel kill, stuck loop) remain v0.2.0+ as DD-14
states.

## Consequences

- ADR-0001, 0005 and 0008 hold at v0.1.0 as written, and the drill cases that assert them are valid.
- The default is `quarantine`, not `kill`: a tamper false positive is recoverable (`agenthalt lift`) and
  evidence is preserved.
- These triggers depend on the basic `quarantine` rung shipping at v0.1.0 (DD-13).
- They need neither R18 authorization nor agentpolicy, so the v0.2.0 dependency chain is unchanged.

## Amendment (2026-11-27, ADR-0012)

The network cut behind the `quarantine` default is made by a composed sandbox layer or by the built-in fallback
([ADR-0012](0012-built-in-egress-fallback.md)). Where neither can make it (including a default macOS setup), a
tamper halt still blocks at the choke and suspends the subtree, and reports the network cut as `unsupported`.
