# PRD 06 — Security Baseline

**BLUF:** agenthalt is the ecosystem's **emergency control** — if it is wrong or compromised, either the stop
fails when it is needed most, or the switch itself becomes a weapon (**denial-of-service on an operator's own
fleet**, or a halt forged by the agent it is meant to stop). Its assets are the halt state, the lineage record,
the trigger paths, the receipt, and the evidence. Its **own attack surface** — halt forgery, halt suppression,
lineage poisoning, trigger spoofing, journal tampering, evidence destruction — is not a footnote but the
**adversarial sub-matrix** of the field test (CUJ-13, CUJ-16). The AI Kill Switch Act's own incident definition
(*"sabotage of, or interference with, a lawful instruction to shut down… concealment of a capability,
intention, or action… from a monitoring or shutdown mechanism"*) is agenthalt's threat model, stated as law.

**Status:** Draft — v0.1.0 (2026-11-14) · **Owner:** @deghosal-2026 · **Parent:** agentic-suite #209 · PRD #216

## Assets

| Asset | Why it matters |
|---|---|
| The **halt state** (halt store) | The single source of stop truth; suppressing or delaying it is how an agent survives a stop |
| The **lineage registry** | The map containment walks; a poisoned edge hides a descendant, a deleted edge orphans one |
| The **trigger paths** (CLI, webhook, PagerDuty, Slack, panic key, dead-man) | A spoofed trigger halts a healthy fleet (DoS); an unauthenticated trigger is a hostile agent's kill button |
| The **receipt / proof-of-stop** | The forensic record; a forged receipt proves a containment that never happened |
| The **evidence snapshot** | The incident record; destroying it is the attacker's post-stop objective |
| The **halt journal** | The audit trail; an edited journal erases who stopped what and why |
| **Authorization state** (who may halt what — P1) | An RBAC failure turns the fleet's emergency brake into anyone's lever |

## Controls

- **Out-of-band by construction** (R8): the halt state lives **outside** the model's control plane — the agent
  cannot read-modify-write its own stop; the dual choke (runtime + gateway) enforces it even with all harness
  hooks removed (R5).
- **Fail-closed everywhere** (R8): halt store unreachable, adapter error, lineage gap → deny new high-impact
  actions with a distinct `reason_code`; the safe direction is always *stopped* (CUJ-16).
- **Confirmations, not requests** (R10): the receipt is built from per-target confirmations written by the
  enforcement points; an unconfirmed descendant reports `incomplete`, never `done`.
- **Tamper-evident journal** (R12): append-only hash chain over the halt journal; a verification command proves
  unedited history; the chain head is anchored at rotation.
- **Evidence before destruction** (R3): the snapshot is written **before** any process is destroyed; a halt that
  would delete evidence first is a bug, not an optimization.
- **Trigger authentication** (R4, R18): every trigger path authenticates its principal and is journaled
  (actor, scope, reason, channel); webhook/PagerDuty/Slack triggers require signed requests and replay
  protection; the panic key is local-only.
- **Least-privilege composition**: agenthalt holds the *authority to ask* each layer to act; each layer's own
  controls (agentkeys revocation policy, agentgate admin surface, kernel confinement) still apply — agenthalt
  never bypasses them.
- **Idempotency** (F1): re-raising the same halt is a no-op returning the existing receipt; an attacker (or a
  flapping alert) cannot multiply or interleave halts into an inconsistent state.

## agenthalt's own attack surface (the adversarial sub-matrix)

Operationalized directly from the ecosystem's own threat model, extended with the kill-switch-specific threats
the 2026 literature documents:

| Surface | Threat | Defense (test) |
|---|---|---|
| Halt store | The agent (or a Plugin4Shell-class compromise) suppresses, delays, or deletes the kill state | Store is outside the agent's control plane; dual choke fails **closed** when unreachable; store write is journaled; a suppression attempt is itself a self-tamper trigger (`tamper_store`, DD-36) |
| Halt store | **DoS via the switch** — a hostile party floods halts (or halts `all`) to stop a healthy fleet | Trigger authentication + rate limits per principal; fleet-wide scope requires dual control (R18); every halt is journaled with its actor |
| Lineage registry | **Edge deletion** — remove the parent→child edge so the child is never enumerated | Lineage edges are append-only + hash-chained with the journal; an unknown descendant found post-halt is a `survivors[]` entry and a loud finding (R10) |
| Lineage registry | **Edge poisoning** — forge edges to halt *other* agents' subtrees (collateral damage) | Edge writes are authenticated (runtime adapter identity); a poisoned edge fails validation; blast scope is proven, not assumed (CUJ-3) |
| Runtime / harness hooks | The agent edits or removes its own hooks — the "shutdown sabotage" the AI Kill Switch Act names | Hooks are **optional and never load-bearing** (R5): containment proceeds via process/credential/sandbox layers; hook removal is tamper detection → self-tamper trigger (`tamper_hooks`, DD-36) |
| Gateway choke | A direct provider connection bypasses agentgate, so the choke never sees the call | Dual choke + sandbox egress block (agentseatbelt/agentkernel); the readout names any uncovered route (R11, CUJ-23) |
| Credential layer | The agent copied a static key outside agentkeys' reach before the halt | The receipt names **unrevocable grants + residual windows** rather than claiming full revoke (CUJ-5); short-lived issuance (agentkeys R9) is the durable fix |
| Trigger paths | **Trigger spoofing** — a forged webhook/PagerDuty halt, or a replayed one | Signed triggers, nonce/timestamp replay protection, principal binding; the halt journal records channel + principal (R4, R18) |
| Trigger paths | **Panic-key squatting** — a hostile local process grabs the panic key first | Panic key requires the local interactive session (P4 Sam's own machine); a non-interactive invocation is rejected and journaled |
| Evidence snapshot | The agent (or attacker) edits or destroys the snapshot post-halt | Snapshot is written before termination, hash-chained, anchored, and exported off-host on completion; chain verification detects any edit (R3) |
| Receipt | **Receipt forgery** — a fake "confirmed stop" for a still-running agent | Receipt entries are signed by the enforcement points that produced them; the offline verifier re-derives the chain (R10, R21) |
| Halt journal | An operator "fixes" the journal after a bad halt | Hash chain + verification command; rotation anchors the head; a missing segment is a loud finding (R12) |
| Dead-man triggers | **False trigger injection** — forged budget-exhaustion/tamper events halt healthy agents | Triggers originate from authenticated ecosystem components (agentpolicy/agentkeys/agentkernel); a trigger event is itself journaled and verifiable (R16) |
| The halt path itself | An attacker races the fan-out — acts between the halt write and the layer cuts | Order of operations: block-new-first at the choke (synchronous), then suspend/revoke (deadline-bounded); the refused-call log closes the race window in the receipt (PRD 02) |
| `haltd` remote listener | The webhook/PagerDuty/Slack endpoints turn the control plane into a network service | Localhost bind by default; remote listeners opt-in, authenticated, rate-limited, `max_scope ≤ agent`; a listener crash never affects local CLI halts or the fail-closed choke (RK-24) |

Anti-tamper principles: the stop lives **outside** the model's control plane; **fail-closed** on integrity
failure; **assume the harness is compromised** (R5 is the test); **separation of duties** between what stops
(agenthalt), what revokes (agentkeys), what refuses (agentgate), and what records (agentwatch). This table is
**operationalized as a shipped pack** — the `self-halt` adversarial pack runs against the deployed stack every
release cycle, misses published, a hit release-blocking (R14, CUJ-15).

## Trigger authentication (the entry security)

| Trigger | Authentication | Anti-abuse |
|---|---|---|
| CLI (local) | OS user + local socket | Halt scopes honored; every invocation journaled |
| Alert webhook | HMAC signature + timestamp (+ optional mTLS) | Replay window (±5 min default); per-source rate limit |
| PagerDuty button | PagerDuty token + incident linkage | Bound to the incident that raised it |
| Slack action | Slack signature + user principal (P1: agentinbox anti-spoofing) | Scope RBAC (R18) |
| Panic key (local) | Interactive session only | Non-interactive invocation rejected + journaled |
| Dead-man (budget/tamper/kernel) | Ecosystem-internal authenticated channel | Trigger event journaled + verifiable |

## Fail-closed contract (the safety spine)

Any exception, unreachable store, adapter failure, or lineage gap → **deny new high-impact actions** with a
distinct `reason_code` (`halt_store_unavailable`, `adapter_failed`, `lineage_gap`), and the halt completes with
`incomplete` status rather than claiming success. Determinism: the same halt request against the same state
produces the same stop plan. This contract is itself a CI test over a fuzzed failure matrix (CUJ-16, RK-1).

## Disclosure

Security problems are reported privately — see [SECURITY.md](../../SECURITY.md) (and the
[organization security policy](https://github.com/agentic-suite/.github/blob/main/SECURITY.md)). Do not open
public issues for security problems. The adversarial sub-matrix is the *sanctioned* way to attack agenthalt
(the `self-halt` pack, CUJ-15); unsanctioned testing follows the org disclosure process. A kill-switch
vulnerability is disclosed with an SLA and, where a stop can be suppressed, a documented **manual fallback**
(the raw per-layer commands an operator runs if agenthalt itself is down — the runbook ships with the tool).
