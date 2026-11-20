# ADR-0007 — The halt signal is an agentwatch event; no new protocol

**Status:** accepted · **Date:** 2026-11-14 · **Maps to:** DD-09 · **PRD:** [20](../prd/20-standards-and-claims.md), [36](../prd/36-observability-and-soc-pack.md)

## Context

A composed stop needs a machine-readable way for the SOC — and for other ecosystem tools — to see halts.
Candidates: (a) a **bespoke halt protocol/API** (the vendor path): a governance burden, an interop wall, and a
fragment of the very fragmentation the ecosystem exists to end; (b) a **SIEM format** (OCSF directly): the
right *mapping*, the wrong *substrate* — it reaches SIEMs but not the ecosystem's own tools; (c) the
**agentwatch security-event schema**: already the ecosystem's single event vocabulary (OTel GenAI-aligned),
already the substrate for agentpolicy decisions, already flowing into SIEMs via OCSF mapping. The ecosystem
PRD #216 states the non-requirement outright: *no new protocol — the halt signal is published as an agentwatch
event; that's the whole standard surface.*

## Decision

**Halts and their triggers are first-class events in the agentwatch security-event schema** (`halt.raised`,
`halt.completed`, `trigger.rejected`…), joinable with the agent's other events on common ids. That is the
**entire** cross-tool standard surface. The receipt and evidence formats are open, documented *artifacts*
(not a wire protocol) verified offline; SIEM interop ships as a mapping pack (ECS/OCSF,
[PRD 36](../prd/36-observability-and-soc-pack.md)).

## Consequences

- The SOC alarm-on-halts requirement (R6) is satisfied by a shipped content pack, not by integration work.
- agenthalt carries no protocol governance burden and inherits agentwatch's versioning discipline.
- The halt vocabulary lives in the ecosystem's schema repo (one more reason agenthalt ships *within* Wave 0
  alongside agentwatch — the dependency is real and stated).
- Tools that want richer stop semantics consume the receipt artifact; the event remains the portable,
  minimal, SIEM-facing summary — the split mirrors agentpolicy's decision/event pairing.
