# PRD 14 — Non-Goals

**BLUF:** agenthalt **stops; it does not detect, decide, issue, isolate, or undo.** It is the composed-stop
control plane — the hand that throws the breakers the ecosystem already has. Anything that would make it a
detector, a policy engine, a gateway, a credential broker, a sandbox, or a time machine is out of scope.

**Status:** Draft — v0.1.0 (2026-11-14) · **Owner:** @deghosal-2026 · **Parent:** agentic-suite #209 · PRD #216

## Consolidated non-goals

| Non-goal | Why | Who owns it instead |
|---|---|---|
| **Detection** (spotting a rogue agent, injection, exfiltration) | Detection and enforcement stay separate; wiring a switch to a noisy detector breaks legitimate work | agentwatch (events), agentpolicy (budgets), agentgate (tool verdicts), the org's SIEM |
| **Policy decisions** (whether a halt *should* fire on a condition) | A composition tool that grew a policy engine would be two products | agentpolicy (the PDP); agenthalt *consumes* its triggers |
| **Enforcement-layer ownership** (being the proxy, the broker, the sandbox) | agenthalt drives layers through their documented action surfaces; it never becomes one | agentgate (disconnect), agentkeys (revoke), agentseatbelt/agentkernel (freeze) |
| **Credential issuance / identity** | The stop consumes identity mapping; it never issues or brokers identity | agentkeys; the org's IdP |
| **ML / classifiers in the stop path** | Determinism is a product requirement; the model never gets a vote | — |
| **Rollback / undo** | An already-sent email cannot be un-sent; pretending otherwise is the category's biggest lie | Nobody — irreversibility is stated, and the receipt carries the compensation list (R13) |
| **Synchronous in-flight cancel claims** | Blocking new actions is the hard guarantee; in-flight calls are best-effort per layer | Stated per layer in the receipt (PRD 13) |
| **Stopping what it cannot reach** | Third-party-hosted processes, static keys stored elsewhere, and landed side effects are named, not hidden | Documented limits (R19, the blast map) |
| **New protocols / proprietary formats** | The halt signal is an agentwatch event; the evidence format is documented and open | — |
| **Console/UI beyond CLI** (v1) | The stop is a command; review lives in receipts, events, and git | — |
| **Model escalation / "break the loop" rescue** | In-loop availability tooling is the predecessor's job, not the stop's | `ai-loopguard` (composes: may raise a dead-man trigger) |
| **In-process decorators / agent-embedded switches** | A switch that lives where the agent lives dies where it dies — the "model can ignore it" rule | — |
| **Forensic analysis of the snapshot** | agenthalt produces the evidence; it does not investigate it | AgentDFIR-class tooling; agentcomply (evidence → controls) |
| **Attack simulation / red-teaming** | agentdrill attacks *policies*; agenthalt's drill tests the *stop* — the purposes are different | agentdrill (shares the pack-runner pattern, not the purpose) |
| **Fleet halts without authorization design** (v0.1.0) | `all`-scoped halts need RBAC/dual-control first (RK-5) | R18 at v0.2.0 (with agentinbox) |

## What agenthalt is *not* claiming

- It does **not** "stop any agent anywhere." It stops what the composed layers reach; the receipt and readout
  state the rest. A SaaS-hosted agent is halted at the layers you control — and the tool says so (R19).
- It does **not** guarantee zero survivors as a *proof*. "Zero surviving descendants" is **verified in the
  drill** (no post-halt network call observed), and the receipt says *verified*, never *guaranteed*.
- It does **not** satisfy H.R. 9917, the NCSC advice, or EU AI Act Art. 14 for you. It **aligns to** the
  capability sets those documents describe; compliance is a claim for counsel, not a README badge (RK-18,
  [PRD 20](20-standards-and-claims.md) §G).
- It does **not** replace your incident process. It gives the responder one command, one proof, and one evidence
  bundle; the judgment call ("should this agent be stopped?") stays human at v0.1.0 — the dead-man switches at
  v0.2.0 are explicit, configured conditions, not judgments.
