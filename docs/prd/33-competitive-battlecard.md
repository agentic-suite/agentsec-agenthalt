# PRD 33 — Competitive Battlecard

**BLUF:** The 2026 kill-switch field is **crowded with single-layer switches and empty of composed ones**. Every
competitor's own documentation concedes our thesis — Okta's release notes say identity governs the *next* login;
Grip's post says killing the agent isn't enough; Tigera's drill shows no single row empties the grid. This
battlecard fights from those concessions: what each vendor actually stops (their words), where agenthalt wins,
where **they** win today (stated honestly — a battlecard that admits no losses is a brochure), and what closes
each gap by v0.2/v0.3. Positioning line: **"They ship a switch. We ship the breaker box — and the proof it
worked."**

**Status:** Draft — v0.1.0 (2026-11-14) · **Owner:** @deghosal-2026 · **Parent:** agentic-suite #209 · PRD #216

## The one-liner matrix (elevator encounters)

| If they say… | We say… |
|---|---|
| "We have an AI kill switch too" | "Yours stops one wire. What's still running at 09:01? Ours reads you the list — and proves the rest is dead." |
| "We revoke tokens at the gateway" | "What about the calls that never cross your gateway, the key in the env, and the children with their own sessions?" |
| "We're deploying at enterprise scale" | "Can your on-call prove the stop worked at 3 a.m., to an auditor, without you on the call? The receipt is the product." |
| "Open source can't do this seriously" | "The evidence format, the drill, and the receipt are the standard surface. Open is why a SOC can verify it without trusting us." |

## Per-competitor cards

### CrowdStrike — Falcon Guardian AI Kill Switch (2026-11-03)
- **What it stops (their words):** terminate the running agent **at the gateway**; block relaunch; cut
  credentials/network to the enterprise.
- **Their edge:** the Falcon estate — endpoint telemetry, existing SOC muscle, enterprise sales motion.
- **Where we win:** gateway-scoped vs composed layers; the proof (their "every step is tracked" is console
  telemetry; ours is an offline-verifiable receipt); no Falcon deployment required; open evidence format.
- **Where they win today:** orgs already all-in on CrowdStrike; kernel/endpoint depth via Falcon sensor.
- **Closes by:** v0.2.0 (drills-in-a-box, authorization) makes us the *composable layer under their console* —
  an adapter, not a war, if they ever want a proof layer.

### Okta — Agent Gateway kill switch (2026-09-22)
- **What it stops (their words):** deactivation "immediately blocks new sessions"; token revocation at the
  gateway; **in-flight session shutdown "planned for Q4"** — their own release notes are the gap statement.
- **Their edge:** identity plane ownership; every SaaS trusts the IdP; enterprise distribution.
- **Where we win:** issuance ≠ the current session (E8); we cut process + sandbox + children now, not next
  login; confirmations vs promises; harness-agnostic (Okta helps agents *inside* its estate).
- **Where they win today:** fleet-wide identity revocation at SaaS scale; agentkeys is young.
- **Closes by:** agentkeys maturing (Wave 0/1) + our credential adapter; we remain the composition layer above
  identity — a halt composes *their* revocation too.

### Zenity ($125M Series C, 2026-08-03)
- **What it stops:** per-step policy enforcement (Boundaries) + a kill switch that stops tool calls/data access
  mid-flow.
- **Their edge:** the governance platform (surface→enforce→protect), enterprise buyers, copilot/agent estate
  coverage.
- **Where we win:** **lineage containment** (their per-step stop vs our graph stop — their own runbook guidance
  asks for exactly our proof: "stop every instance, sub-agent, and scheduled trigger, without wiping memory or
  logs," E21); open vs proprietary; the drill.
- **Where they win today:** platform breadth, compliance surface, SaaS-agent coverage inside major platforms.
- **Closes by:** v0.2.0 SaaS-coverage records (R19) + agentcomply for the governance half (their lane, our
  evidence feed).

### Tigera Lynx (2026-11-02)
- **What it stops (their words):** gateway 403 both directions + kernel lockdown (no egress, no new processes,
  no writes), per-agent identity, 10-min tokens, Agent Trail audit.
- **Their edge:** the closest to the bar — kernel + gateway dual enforcement on K8s; honest engineering prose.
- **Where we win:** **K8s-only vs harness-agnostic**; the composed credential cut (their own text: a stop
  "does nothing about the task already handed to another agent or the work already on a queue" — our readout
  names exactly that); OSS receipt vs console; laptop/dev-machine scope (their model needs a cluster).
- **Where they win today:** Kubernetes-native shops; eBPF depth (agentkernel is Wave 2 for us).
- **Closes by:** agentkernel (Wave 2) for the kernel half; our readout already answers their named gap today.

### Aembit / Grip (identity-led)
- **What they stop:** identity/session revocation (Aembit, with the vendor's own caveat that static keys
  survive); SaaS/OAuth/NHI containment (Grip, "kill the agent, its credentials, its NHI, its SaaS access").
- **Their edge:** the identity problem is real and they own it in the enterprise (E7/E14 confirm the thesis).
- **Where we win:** composition — we *drive* identity revocation as one cut among four, then prove the whole
  stop; process containment; local/OSS reach.
- **Where they win today:** SaaS sprawl containment; NHI governance at org scale.
- **Closes by:** composing agentkeys + their concerns via adapters; our readout is the honest cross-check for
  any identity vendor's claim.

### Salesforce / JetStream (platform-scoped switches)
- **What they stop:** one agent on their estate (Agent Fabric GA + auto-fire Jan 2027; JetStream "surgical"
  single-agent shutdown).
- **Where we win:** harness-agnostic; **our dead-man switches beat their announced auto-fire to market**
  (E22); proof + evidence.
- **Where they win today:** zero-friction inside their platform; distribution.
- **Closes by:** they don't need closing — platform switches are **choke points we compose**; the pitch to
  their customers is "keep the switch; add the proof and the rest of the graph."

### OSS loop breakers (intutic, LongGuard, stoke, loopguard, agent-killswitch)
- **What they stop:** the *loop* — KILL verdicts, budget caps, in-flight breakers, proxy blocks.
- **Where we win:** in-loop ≠ out-of-band (a verdict the loop renders is a suggestion with better branding,
  [PRD 01](01-why.md)); no credential/process/graph containment; no proof.
- **Where they win today:** install simplicity inside one framework; cost/loop features are genuinely useful.
- **Closes by:** we don't — **`ai-loopguard` composes** ([PRD 10](10-feature-parity.md)); the OSS story is
  "your breaker may pull our switch."

## Why now / why us / where we lose today

- **Why now:** the regulatory clock (H.R. 9917 in committee, NCSC published, Art. 14 in force, CA EO due
  2026-11-16) + the vendor wave just named the category. Every vendor will have a switch by the end of the
  quarter — the open, provable, composed one has a narrow window to become the standard surface ([PRD 01](01-why.md)).
- **Why us:** the only composed stop (row #18), the only lineage proof (#19), the only confirmations-based
  receipt (#20), the only planned drill (#25; not yet shipped) — and the ecosystem gives us every layer for free
  ([PRD 03](03-landscape.md) coverage map).
- **Where we lose today (say it in the room):** enterprise sales motion (they have one, we have a repo);
  K8s/kernel depth until agentkernel (Tigera); SaaS/NHI estate until agentkeys matures (Aembit/Grip); platform
  distribution (Salesforce/Okta). Every loss closes on the roadmap, not in the prose ([PRD 09](09-roadmap.md)).

## Battlecard discipline

- Every "their words" quote links the primary source — this card cites like the rest of the PRD set, it does
  not paraphrase competitors into strawmen.
- The card is **internal-facing** (design partners, fundraising, positioning); public comparisons follow the
  claims ledger ([PRD 31](31-claims-ledger.md)) — nothing here becomes marketing copy without a C-id artifact.
- Refresh cadence: with the coverage-matrix regeneration per release + on any RK-18 trigger.
