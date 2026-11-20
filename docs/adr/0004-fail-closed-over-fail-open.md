# ADR-0004 — Fail-closed over fail-open: the deliberate inversion of the predecessor

**Status:** accepted · **Date:** 2026-11-14 · **Maps to:** DD-03 · **PRD:** [10](../prd/10-feature-parity.md), [13](../prd/13-non-functional-requirements.md)

## Context

The shipped predecessor `ai-loopguard` (#58) is an **availability** tool: fail-open paths are correct there — no
escalation model configured, keep the loop running; escalation failed, continue; the point is to rescue work,
not to stop it. agenthalt is the opposite tool: a stop primitive that fails open is an agent that keeps acting
while the operator believes it stopped — the single unforgivable failure for this product class. The two
stances are both correct *for their product* and mutually incompatible in one codebase.

## Decision

**Every failure path fails closed with a distinct `reason_code`:** store unreachable → the dual choke denies
high-impact actions (`halt_store_unavailable`); adapter failure → the target reports unconfirmed, receipt
`incomplete`; lineage gap → loud finding, never a quiet guess. **Evidence failure never cancels the stop** —
the snapshot is a side effect, not a gating dependency; it degrades to `evidence: failed` loudly. The inversion
is documented as the parity set's one semantic change ([PRD 10](../prd/10-feature-parity.md) P10), not
smuggled in.

## Consequences

- "No failure mode silently continues" is a CI test over a fuzzed failure matrix
  ([PRD 25](../prd/25-test-strategy.md)), not a claim.
- Availability cost, stated plainly: a broken store slows the fleet (deny-mode) rather than letting agents run
  unguarded — the correct trade for a safety control, in the docs, not in a footnote.
- The manual fallback runbook ships with the tool and is a tested drill leg (`manual-fallback`): fail-closed
  must never mean "unstoppable because the control plane hiccuped" ([PRD 28](../prd/28-failure-mode-runbook.md)).
- `ai-loopguard` composes rather than merges: it keeps its fail-open availability semantics *in the loop* and
  may raise a dead-man trigger whose *stop* then fails closed.
