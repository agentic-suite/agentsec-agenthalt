# ADR-0005 — Harness hooks are optional and never load-bearing

**Status:** accepted · **Date:** 2026-11-14 · **Maps to:** DD-06 · **PRD:** [05](../prd/05-features.md) R5, [19](../prd/19-harness-compatibility.md)

## Context

Harness hooks (Claude Code `PreToolUse`/`Stop`, Codex config surfaces) are the seductive integration path:
fast to build, richest metadata, and the obvious first demo. But the incident record says the switch must
survive the harness: Plugin4Shell gives an attacker code execution *inside* the harness (hooks become editable
attack surface); GitHub Copilot's hooks are closed (no surface at all); H.R. 9917 names "sabotage of a lawful
instruction to shut down" as the incident itself. A stop that depends on the harness dies exactly when it is
needed most. The OSS landscape's in-loop breakers (`intutic`, `agent-killswitch`) are the counter-pattern: a
verdict the loop renders is a suggestion with better branding.

## Decision

**Containment happens at the process, credential, gateway, and sandbox layers — below the harness — and no
hook is ever load-bearing.** Hooks, where they exist, are *accelerants* only: richer lineage edges, a graceful
in-process stop, cleaner run-id semantics. Every v0.1.0 capability must be provable with the hook surface
absent; the `hostile-harness` drill case removes the hooks on camera and asserts full containment.

## Consequences

- agenthalt works on zero-hook harnesses by construction (R5) — the harness-agnostic mandate is satisfied
  architecturally, not by N integrations ([PRD 19](../prd/19-harness-compatibility.md)).
- Hook-removed and hook-tampered cases are *features* of the threat model: removal is tamper detection → the
  `tamper_hooks` self-tamper trigger, shipped at v0.1.0 (ADR-0010).
- Cost: hook-less lineage is process-observation-based (best-effort edges, orphan watchlist —
  [PRD 27](../prd/27-lineage-model.md)); graceful in-process stops are a courtesy, never a mechanism.
- Demo 2 exists to prove this ADR in public ([PRD 22](../prd/22-demo-scenarios.md)).
