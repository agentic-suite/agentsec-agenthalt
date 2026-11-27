# ADR-0011 — Receipt status precedence and labelled self-attestation

**Status:** accepted · **Date:** 2026-11-27 · **Maps to:** DD-39, DD-40 · **Extends:** ADR-0003 · **PRD:** [26](../prd/26-receipt-schema-and-examples.md), [37](../prd/37-cli-and-output-ux-spec.md)

## Context

ADR-0003 fixed the status vocabulary (`complete` / `incomplete` / `partial-layer` / `failed`) but not what
happens when several apply. The common Wave-0 case is a survivor on a stack with no agentgate, which is both
`incomplete` and `partial-layer`. Exit codes are Tier-0 immutable, so the rule must be set before M6 ships.

Separately, ADR-0003 says confirmations are signed by "the enforcement point that produced them". On a stack
without agentseatbelt or agentkernel, the enforcement point for process and sandbox cuts is agenthalt's own OS
executor. agenthalt would then be its own witness, and the receipt didn't say so.

## Decision

1. **Precedence:** the worst true status wins: `failed` > `incomplete` > `partial-layer` > `complete`. Exit
   codes follow the same order (`3` > `1` > `2` > `0`). Every `unsupported` layer is still listed in
   `confirmations[]` whatever the headline status.
2. **Attestation is labelled:** each confirmation carries `attestation: third_party | self`. The built-in OS
   executor signs with a separate executor key (never the coordinator's) and labels its confirmations `self`.
   `prove` reports self-attested cuts distinctly. A confirmation with `signed_by: null` can never be
   `confirmed`.

## Consequences

- One halt maps to one status and one exit code, deterministically, so runbooks can branch on it.
- A Wave-0 receipt is honest about whose word each cut rests on; third-party attestation arrives with the
  composed layers without a schema change (an additive field, Tier-0 safe).
- Self-attestation is accepted out loud as RK-25. The cross-layer contradiction check (PRD 30) still applies.
