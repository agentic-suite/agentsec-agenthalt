# ADR-0006 — Snapshot-before-termination: evidence is written before the scene is destroyed

**Status:** accepted · **Date:** 2026-11-14 · **Maps to:** DD-10 · **PRD:** [17](../prd/17-evidence-and-proof-format.md), [39](../prd/39-performance-budget.md)

## Context

The moment of the stop is the moment of maximum forensic value and maximum forensic risk. The obvious
implementation order — terminate first (stop the damage!), collect later — destroys the pod's own record of
what it was doing (the Tigera drill's verdict on pod deletion); forensics research shows raw captures hold
~4× the sensitive material a first scan finds, so capture must happen while the scene exists. But evidence
collection cannot serialize ahead of the stop either: a big snapshot in front of the suspend blows the ≤1 s
budget and delays containment — trading one incident for another.

## Decision

**The order of operations is fixed and architectural: block-new at the choke → suspend → cut network →
commit the snapshot's first chained segment → terminate → revoke → receipt.** Termination cannot complete
before the snapshot's first segment commits; a halt that would destroy evidence first is a bug, not an
optimization. The snapshot's *first segment* commits inside the halt window (≤150 ms,
[PRD 39](../prd/39-performance-budget.md)); full capture completes asynchronously and the receipt reports
`evidence: pending → written` honestly across that transition. Redaction runs between collection
and persistence — raw bytes never touch disk ([PRD 38](../prd/38-evidence-privacy-and-data-handling.md)).

## Consequences

- Evidence survives every mode of the stop — including `kill`, which is precisely when it is hardest to keep.
- Termination is delayed by the first-segment commit only (bounded, budgeted); the ≤1 s claim remains honest
  because the clock's evidence term is defined as the first-segment commit.
- Snapshots of *frozen* (not terminated) processes are consistent — a paused process is a better witness than
  a corpse; `pause` gains forensic value beyond resumability.
- The `evidence-canary` drill case proves the redaction pipeline on every release; a capture field without a
  redaction rule fails CI.
