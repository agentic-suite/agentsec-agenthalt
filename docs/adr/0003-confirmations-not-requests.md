# ADR-0003 — Receipt semantics: confirmations, never requests; `incomplete` is a first-class status

**Status:** accepted · **Date:** 2026-11-14 · **Maps to:** DD-04 · **PRD:** [26](../prd/26-receipt-schema-and-examples.md), [07](../prd/07-success-metrics.md)

## Context

The category reports stops that haven't finished. Vendors announce "revoking every active token" and "shutting
down every session in flight" as *planned* capabilities (Okta's own release notes); SOC consoles show
"parent status = stopped" while children keep spending; a `kill -9` returns success the moment the signal is
sent, not when the graph is dead. The practitioner bar: *"If you cannot show every descendant stopped, you did
not kill."* A receipt assembled from *requests* inherits all of this — and the proof, our sharpest
differentiator (coverage row #20), dies with it.

## Decision

**Receipts assemble exclusively from enforcement-point-signed confirmations.** A layer that received a request
but reported nothing reports `requested`; a target unconfirmed at the deadline appears in `survivors[]` and
**forces** `status=incomplete` — a schema-level invariant, not a UI choice. The status vocabulary is exhaustive
(`complete` / `incomplete` / `partial-layer` / `failed`) and contains **no state meaning "probably stopped."**
Confirmation entries are signed by the enforcement point that produced them and re-derivable offline
([PRD 17](../prd/17-evidence-and-proof-format.md)).

## Consequences

- The receipt is verifiable by a third party with no trust in the operator's environment (CUJ-24) — the
  trust artifact the category lacks.
- Enforcement points must sign/report inside the halt deadline (RK-3); adapters that can't, report honestly.
- Some halts *will* read `incomplete` — that is the product working, not failing: the alternative is a lie.
- Marketing can never round up: the claims ledger (C-04) binds public wording to the same artifact
  ([PRD 31](../prd/31-claims-ledger.md)).
