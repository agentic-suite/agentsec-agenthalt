# PRD 23 — Persona Objections & Adoption

**BLUF:** Every adopter of a kill switch asks the same five questions in different words: *will it slow me
down, will it break things, will it fight my stack, can I trust it, and what happens when it's wrong?* This
document answers each objection per persona **before** it becomes roadmap churn — with the requirement, doc,
or deliberate trade-off that answers it, and the churn trigger that means we got the answer wrong.

**Status:** Draft — v0.1.0 (2026-11-14) · **Owner:** @deghosal-2026 · **Parent:** agentic-suite #209 · PRD #216

## P1 Maya — platform/DevEx lead

| Objection | Answer | Where |
|---|---|---|
| "Will it slow my agents down?" | The choke is a local read with a seconds-TTL cache; halt-path cost is zero when no halt is active; the ≤1 s budget applies **to the stop**, not to the loop | [PRD 13](13-non-functional-requirements.md) §Speed |
| "Will it break my dev workflows?" | Monitor-first: the store can be armed without a halt ever firing; drills run against a demo agent, not your fleet; pause is resumable | CUJ-4, [PRD 18](18-stop-modes.md) |
| "Do I need to install the whole ecosystem first?" | v0.1.0 is local-first: process + evidence work standalone; credential/gateway layers light up when agentkeys/agentgate exist and report `unsupported` honestly otherwise | DD-18, [PRD 19](19-harness-compatibility.md) |
| "Is this another agent-process tool I'll have to rip out?" | It composes the layers you already run and owns none — no parallel stack, no rip-out path | [PRD 32](32-build-vs-integrate.md) |
| "What if it halts something wrongly?" | `pause` is the first-move default (RK-20); every halt is journaled with actor + reason; lift/restore returns to the prior state (E18) | [PRD 18](18-stop-modes.md) |

## P2 Ravi — security engineer / SecOps

| Objection | Answer | Where |
|---|---|---|
| "How do I trust the receipt?" | Confirmations are signed by the enforcement points, not self-reported; `agenthalt prove` re-derives offline; `requested` is never rounded up to `confirmed` | [PRD 17](17-evidence-and-proof-format.md), DD-04 |
| "What if the stop path itself is attacked?" | The adversarial sub-matrix is the sanctioned attack surface; suppression is itself a dead-man trigger; the manual fallback runbook ships with the tool | [PRD 06](06-security-baseline.md), [PRD 28](28-failure-mode-runbook.md) |
| "Can I trigger it from my existing incident tooling?" | Webhook (HMAC), PagerDuty button, Slack action — all journaled; SIEM rules can fire it today | [PRD 16](16-trigger-catalogue.md) |
| "Will it show up in my SIEM?" | Halt + trigger are first-class agentwatch events; the refused-call log is written by the enforcement points | R6, [PRD 15](15-data-model.md) |
| "What if a descendant survives?" | It can't hide: `survivors[]` non-empty ⇒ `incomplete`, the readout names it, and the drill fails the build | R10, RK-2 |

## P3 Dana — compliance / GRC lead

| Objection | Answer | Where |
|---|---|---|
| "Is this evidence actually auditor-usable?" | Hash-chained, timestamped, redacted, offline-verifiable; the verifier's output is designed to paste into an incident report | [PRD 17](17-evidence-and-proof-format.md), R21 |
| "Does it satisfy Art. 14 / NCSC / H.R. 9917?" | It **aligns to** the capability sets, documented clause-by-clause; compliance is your counsel's claim, never our README's (forbidden claim) | [PRD 29](29-regulatory-crosswalk.md), [PRD 20](20-standards-and-claims.md) §F |
| "Who stopped what, and can they prove it?" | Actor, channel, reason, scope, mode history — all journaled, tamper-evident | R12, [PRD 15](15-data-model.md) |

## P4 Sam — solo developer

| Objection | Answer | Where |
|---|---|---|
| "Can I use this without a fleet/SIEM/team?" | Panic key + CLI + local store; evidence on your own disk; free forever for local use | CUJ-12, [PRD 24](24-pricing-and-packaging-thesis.md) |
| "Will it phone home?" | No; local-first, no cloud dependency for any P0 requirement | [PRD 13](13-non-functional-requirements.md) §Portability |

## P5 Alex — platform builder / embedder

| Objection | Answer | Where |
|---|---|---|
| "Can I embed this without adopting your ecosystem?" | Library + MCP + HTTP surfaces; the halt contract is one operation; layer adapters are pluggable and report `unsupported` gracefully | [PRD 02](02-architecture.md) §contract |
| "Will you compete with my layer?" | agenthalt owns no layer (DD-01); your enforcement point can be a composed executor adapter — one schema, one PR | [PRD 32](32-build-vs-integrate.md) |
| "Is the format going to break under me?" | Receipt/evidence schemas are append-only; a v0.1.0 receipt verifies forever | [PRD 26](26-receipt-schema-and-examples.md) §compat |

## Adoption path (per persona)

| Week | P1 Maya | P2 Ravi | P4 Sam |
|---|---|---|---|
| 1 | install; run `doctor`; run Demo 1 on the demo agent; arm the store | point the SIEM webhook at it; page-test the PagerDuty trigger | install; bind the panic key; run Demo 5 |
| 2 | drills on one real (non-prod) harness; read receipts; set pause-TTL policy | alarm on `halt.*` events; verify a receipt offline (CUJ-24) | halt one runaway loop; inspect the snapshot |
| 4 | write the runbook entry ([PRD 28](28-failure-mode-runbook.md)); pause-first posture | dry-run the self-halt pack with the team | — |
| later | enforce dead-man switches with agentpolicy budgets; graduate modes | fleet dual-control (R18) with agentinbox | — |

## Churn triggers (what would mean we got it wrong)

- **Latency complaints in the agent loop** ⇒ the choke-cache design failed (RK on [PRD 13]; revisit cache TTL).
- **"The receipt doesn't match reality"** once in the field ⇒ RK-3 escalation; proof-of-stop audit.
- **Pause-limbo complaints** ⇒ TTL defaults wrong (RK-15).
- **Partners halt-then-never-drill** ⇒ the "drill is the product" thesis is failing (PRD 21 falsifier #5).
- **A layer ships its own kill path** ⇒ DD-33 breach; ecosystem governance conversation.

## Objections we will not "fix" with features

- *"Can you make it undo the damage?"* — No. There is no undo (R13); the compensation list is the honest
  answer, and pretending otherwise is forbidden ([PRD 14](14-non-goals.md)).
- *"Can you detect rogue agents for us?"* — No. Detection is another layer's job (DD-07); wiring a switch to a
  noisy detector breaks legitimate work ([PRD 01](01-why.md)).
- *"Can it stop the vendor's SaaS process?"* — Only what the layers reach; the receipt says what it couldn't
  (R19), and we won't claim otherwise.
