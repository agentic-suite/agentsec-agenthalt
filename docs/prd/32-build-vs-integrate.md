# PRD 32 — Build vs. Integrate

**BLUF:** agenthalt builds exactly **six things** — the coordinator, the halt store, the lineage registry, the
receipt/proof machinery, the drill runner, and the journal — and **integrates everything else** through the
composed layers' documented action surfaces. It deliberately builds **no** policy engine, gateway, broker,
sandbox, detector, or protocol. This boundary is the product: a composition tool that grew a layer would be two
products, and a fleet that runs five half-switches instead of one composed one is the status quo we exist to
replace.

**Status:** Draft — v0.1.0 (2026-11-14) · **Owner:** @deghosal-2026 · **Parent:** agentic-suite #209 · PRD #216

## What agenthalt builds (owns outright)

| Component | Why it must be ours |
|---|---|
| **Halt coordinator** (`haltd`) | Sequencing (block-new-first), deadline handling, and confirmation assembly are the product's core loop (PRD 02) |
| **Halt store + choke protocol** | The single source of stop truth; its fail-closed semantics are the safety spine (R8) |
| **Lineage registry** | Containment walks it and proof is built from it; append-only + adapter-authenticated ([PRD 27](27-lineage-model.md)) |
| **Receipt + evidence machinery** | The proof-of-stop is the differentiator; the format is ours to keep open and append-only ([PRD 26](26-receipt-schema-and-examples.md), [PRD 17](17-evidence-and-proof-format.md)) |
| **Drill runner + self-halt pack** | The drill is the product's credibility; nobody else ships it (K9, R14) |
| **Halt journal** | The tamper-evident record of who stopped what (R12) |

## What agenthalt integrates (and the exact surface)

| Layer | Integrated surface | Degrades when absent |
|---|---|---|
| **agentkeys** | revoke actions + credential inventory for the subtree | credentials confirmations → `unsupported`; readout carries unrevocable grants |
| **agentgate** | session termination + per-call refusal (the gateway half of the dual choke) | gateway step → `unsupported` (Wave-0 default, DD-18) — receipt `partial-layer` |
| **agentseatbelt** | process suspend/freeze + egress block (macOS/local) | process/sandbox confirmations degrade; manual fallback runbook leg |
| **agentkernel** | eBPF kill triggers + kernel-level containment (Linux, Wave 2) | kernel kill dead-man unavailable; uncovered routes named |
| **agentwatch** | event emission/join + the evidence trace window | evidence → degraded (`evidence: failed`), loudly; halt events never blocked by telemetry failure |
| **agentpolicy** | budget-exhaustion + tamper triggers (dead-man sources, v0.2.0) | dead-man switches inert; manual triggers only |
| **agentinbox** | halt authorization ask-gate + mobile/Slack triggers (v0.2.0) | RBAC falls back to local principal + scope ceilings |
| **agentdrill** | the shared pack-runner pattern; agenthalt's drill is a drill pack consumer/producer peer | drills remain runnable standalone (local-first) |

**Integration rule:** every adapter speaks the *other tool's documented action surface* (the same surface a
human operator uses in [PRD 28](28-failure-mode-runbook.md)'s manual fallback). If a layer changes its surface,
the adapter breaks loudly at load — never silently degrades into wrong behavior.

## What agenthalt deliberately does NOT build

| Not built | Owner | The boundary reason |
|---|---|---|
| Policy engine / decision logic | agentpolicy | "Should this halt fire?" is a decision; agenthalt executes (DD-01) |
| MCP proxy / routing | agentgate | A proxy inside a stop tool is scope creep with a network stack attached |
| Credential issuance/brokerage | agentkeys | The stop consumes credential *authority*; it never holds secrets |
| Sandbox / confinement tech | agentseatbelt / agentkernel | Confinement is a layer; we drive it, we don't reimplement it |
| Detection / classification | agentwatch, SIEM, (nobody, honestly) | Detection and enforcement stay separate (DD-07) |
| Escalation / model routing | `ai-loopguard` | The absorbed predecessor keeps its job; it may *raise* our trigger ([PRD 10](10-feature-parity.md) P3) |
| New protocol / event format | agentwatch schema | The halt event is the entire standard surface (DD-09) |
| Forensic analysis | AgentDFIR-class tooling, agentcomply | We produce evidence; we don't investigate it ([PRD 14](14-non-goals.md)) |

## Why this boundary matters

1. **The thesis is composition** ([PRD 03](03-landscape.md)): the whitespace is the *composed stop* (row #18),
   not another layer. Every layer we build is a layer we're now competing with our own ecosystem on.
2. **Trust minimization:** agenthalt holds stop *authority* but no secrets, no routing, no policy state — a
   smaller blast radius for the control plane itself ([PRD 30](30-threat-model.md)).
3. **Honest degradation:** because every capability is an adapter, absence is expressible (`unsupported`) —
   which is exactly what makes Wave-0 shippable with agentgate still pending (DD-18).
4. **Partner extensibility:** a new layer (a vendor EDR, a custom runner) is **one adapter + one drill case +
   one PR** — the same one-PR rule as agentpolicy's packs.

## Boundary-blur risks (and the guardrails)

| Blur | Symptom | Guardrail |
|---|---|---|
| An adapter grows inline enforcement ("just this once") | adapter code deciding policy | Adapter schema forbids enforcement; review rule (RK-13) |
| A layer ships its own halt path | gateway "disconnect" becomes a parallel kill | DD-33: agenthalt is the single composed-stop entry; governance escalation (RK-21) |
| agenthalt accumulates fleet state | the store becomes a config DB | Store holds **only** kill state; everything else is journaled artifacts |
| The receipt becomes a product feature farm | fields for marketing, not proof | Append-only schema + claims ledger: a field must be verifiable to exist ([PRD 31](31-claims-ledger.md)) |
