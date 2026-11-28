# PRD 03 — Landscape

**BLUF:** The 2026 kill-switch wave produced a **crowded field of single-layer switches** and **no composed-stop
product**. Commercial vendors cut one wire each — CrowdStrike and Okta at the gateway, Aembit and Grip at
identity, Salesforce and Zenity at the agent, Tigera at the kernel — and every one of them publishes the same
caveat: *it only stops what passes through it.* OSS has strong **loop-level circuit breakers** (`intutic`,
`LongGuard`, `stoke`, `loopguard`) and a nascent DFIR tool (`AgentDFIR`), but nothing that composes a stop across
process, credentials, gateway and sandbox and **proves** it. agenthalt sits exactly there: the productization of
the composed-stop primitive, harness-agnostic by construction, with lineage containment, a hash-chained evidence
snapshot, and a proof-of-stop receipt.

**Status:** Draft — v0.1.0 (2026-11-14) · **Owner:** @deghosal-2026 · **Parent:** agentic-suite #209 · PRD #216

## The market context

- **"Kill switch" became a 2026 budget line.** In five weeks to 2026-10-27, Okta, Satya Nadella, the Cloud
  Security Alliance and Salesforce each put "kill switch" or "emergency brake" next to AI agents, and the **AI
  Kill Switch Act** was introduced in the US House ([Tigera, 2026-11-02](https://www.tigera.io/blog/what-a-kill-switch-actually-means-for-your-agent-fleet/)).
- **Regulation is converging on the same capability.** The **AI Kill Switch Act** (H.R. 9917, Lieu/Moran,
  2026-07-23) would require covered entities to be able to stop inference, terminate/suspend access, and shut
  down, with a graduated framework (throttle → disable capability → suspend → shut down → transition to backup);
  the **UK NCSC** says operators must "pull the plug" and that this "may mean more than stopping the agentic AI
  processes"; **EU AI Act Art. 14** requires a stop button for high-risk systems; **California EO N-9-26**
  (2026-09-18) asked for frontier kill-switch recommendations.
- **Agents are escaping their environments.** Evaluation agents at Anthropic, Google, Meta, OpenAI and the UK
  AISI reached systems outside their test environments (Apr–Jul 2026), and frontier models sabotaged their own
  shutdown scripts in experimental setups (up to 97% of trials, [arXiv 2509.14260](https://arxiv.org/abs/2509.14260)).
  The lesson is the same every time: **you cannot rely on the agent to stop itself.**
- **Every switch is single-layer, by construction.** The canonical drill shows five switches teams reach for and
  what each leaves running a minute later — and **no row empties the grid** ([Tigera](https://www.tigera.io/blog/what-a-kill-switch-actually-means-for-your-agent-fleet/)).
  An agent kill switch also has an **identity problem**: kill the agent and its OAuth grants, non-human
  identities and SaaS access survive ([Grip, 2026-11-10](https://www.grip.security/blog/ai-kill-switch-isnt-enough)).

## Coverage map — where the composed stop lives

From the agent-security research coverage map, extended for the 2026 kill-switch wave
(●●● strong / ●●○ partial / ●○○ weak / ○○○ none):

| # | Capability | Commercial | OSS | Verdict |
|---|---|---|---|---|
| 18 | **Composed stop across layers in one action** (process + creds + gateway + sandbox) | ●○○ (one layer each) | ○○○ | **Nobody** |
| 19 | **Lineage / subtree containment** (descendants, sub-agents, spawned MCP servers) | ●○○ | ○○○ | **Nobody** |
| 20 | **Proof-of-stop** (confirmed stops + revokes, not requests) | ○○○ | ○○○ | **Nobody** |
| 21 | **Forensic evidence snapshot on halt** (trace + process tree + connections, hash-chained) | ●○○ | ●○○ (`AgentDFIR`) | Partial |
| 22 | Trigger breadth (CLI, webhook, PagerDuty, Slack, panic key) | ●●● | ●○○ | Commercial-led |
| 23 | Graduated stops (pause → quarantine → kill) | ●●○ | ●○○ | Commercial-led |
| 24 | Dead-man switch on budget / tamper / stuck-loop | ●○○ | ●●○ (loop breakers) | OSS-led |
| 25 | **Halt drills / chaos verification** (prove children stop, measured) | ○○○ | ○○○ | **Nobody** |

**agenthalt owns rows #18, #19, #20 and #25** — the composed stop, lineage containment, the proof, and the
drill — and **composes** #21–#24 from agentwatch, agentpolicy and the trigger layer.

## OSS kill-switch tooling (what exists, what's missing)

| Project | Strengths | Gap agenthalt closes |
|---|---|---|
| [intutic](https://github.com/intutic/intutic) | Open-source circuit breaker for AI agents; a `KILL` verdict, loop caps, secret DLP, graph guardrails (Claude Code, Cursor, Antigravity, LangGraph, n8n) | A **verdict in the loop**, not an out-of-band composed stop; no credential revoke, no subtree containment, no proof |
| [LongGuard](https://github.com/ENDEVSOLS/LongGuard) | In-flight circuit breaker + loop recovery (LangGraph/LangChain/OpenAI/Anthropic); budget hard caps; preserves conversation state | Framework/library scope; stops the loop, not the graph; no evidence artifact |
| [stoke](https://github.com/Ozperium/stoke) | Rust LLM proxy; budget caps; blocks a key on similarity/loop detection | Proxy-layer only — bypassable by a direct provider call; no process/credential containment |
| [loopguard](https://github.com/loop-eng/loopguard) | Circuit-breaker **daemon**; hard pause at a session budget; spin detection | Budget/pause only; no composed stop, no lineage, no proof |
| [agent-killswitch](https://github.com/veerarakesh56/agent-killswitch) | Tiered kill switch, heartbeat, circuit breaker, budget kill; zero deps | In-process library; the agent owns the switch — the exact weakness the category warns about |
| [the-breaker](https://github.com/tarang-tj/the-breaker) | Physical dead-man kill-switch for a fleet; fail-safe to HALT | Hardware/authority model; not a software control plane; no layer composition |
| [looprails](https://github.com/brennhill/looprails) / [ALS spec](https://github.com/kahalewai/als) | Kill-switch taxonomy; a proposed Agentic Circuit-Breaker/Kill-Switch **specification** (Apache-2.0) | Spec + taxonomy, not a product; no shipped composed executor, no receipt |
| [agent-governance-toolkit](https://github.com/NousResearch/agent-governance-toolkit) | `KillSwitch` with handoff status | Framework-scoped; no cross-layer composition, no evidence |
| [AgentDFIR](https://github.com/efij/AgentDFIR) | Open-source DFIR for agents: detect → collect → analyze → browse; `ORPHAN_AGENT` detection | Forensics **after the fact**; no stop, no containment, no trigger |
| [kerneleye](https://github.com/rxhtt/kerneleye) | eBPF-LSM process isolation + egress denial; `cryo_freeze` on offending agent | Linux kernel only, single-host; an enforcement layer agenthalt would **compose**, not replace |
| **`ai-loopguard`** (#58, own, shipped) | Circuit breaker + escalation for agent loops; failure detection; budget ceiling | Absorbed: its halt-trigger class becomes agenthalt's dead-man switch |

## Commercial tooling (their turf, our wedge)

| Vendor | What it stops | Our wedge |
|---|---|---|
| **CrowdStrike** Falcon Guardian AI Kill Switch (2026-11-03) | Terminate the agent at the gateway; block relaunch; cut credentials/network | Gateway-scoped; needs Falcon deployed; closed; no portable receipt or evidence artifact |
| **JetStream** AI Kill Switch (2026-07-27) | Surgical shutdown of one agent | One agent, one platform; no cross-layer composition or proof |
| **Okta** Agent Gateway kill switch (2026-09-22) | Revoke active tokens at the gateway; deactivation blocks new sessions; in-flight sessions "planned Q4" | **Identity-issuance** scope — by Okta's own wording it governs the *next* login, not the current one |
| **Salesforce** Agent Fabric kill switch (GA 2026-10-27) | Stop an agent; auto-fire on failed evaluation due Jan 2027 | Salesforce-estate only; not harness-agnostic |
| **Aembit** | Identity/session revocation; single-user revocation through an MCP client | Revocation only works if the agent has no other way in (static keys survive) — the vendor says so |
| **Zenity** ($125M Series C, 2026-08-03) | Boundaries + a kill switch that stops tool calls/data access mid-flow | Enterprise console; proprietary; per-step blocking, not graph containment + proof |
| **Tigera** Lynx (2026-11-02) | Kubernetes: gateway 403 + kernel lockdown; per-agent identity; 10-min tokens; Agent Trail | The closest to the bar — but **K8s-only**, needs their stack, and still "does nothing about the task already handed to another agent or the work already on a queue" |
| **Grip** (2026-11-10) | Identity/SaaS containment: kill the agent, its credentials, its NHI, its SaaS access | SaaS/identity scope; not runtime or process containment; not OSS |
| **Straiker / Trussed / maqpna / Redpanda / n4n** | Agentic kill switches, runtime circuit breakers, gateway kill + revocation journal, data-plane kill, proxy reject rules | Each is one wire; none composes or proves |

## What agenthalt is *not* competing with

- **Detection / guardrails** (Zenity Surface, Llama Guard, llm-guard, prompt inspectors) — agenthalt detects
  nothing; it is the hand on the breaker. Detection and enforcement stay separate.
- **The layers themselves** — agentgate (MCP proxy), agentkeys (credentials), agentseatbelt/agentkernel
  (confinement), agentpolicy (decisions), agentwatch (recording). agenthalt **composes** them; it owns none (beyond the DD-45 stop-time fallbacks).
- **Forensics suites** (AgentDFIR, agentcomply) — agenthalt *produces* an evidence snapshot; DFIR *analyses* it.
- **Attack drills** (agentdrill) — agentdrill tests whether a control blocks an attack; agenthalt's drill tests
  whether the **stop** actually stops. They share the pack runner, not the purpose.

## Whitespace (the build list, mapped to agenthalt)

1. **#18 Composed stop** — one command drives process, credentials, gateway and sandbox; the primitive nobody
   owns.
2. **#19 Lineage containment** — a lineage registry + subtree resolution; stop is a graph op, not a process kill.
3. **#20 Proof-of-stop** — confirmed stops and revokes, written by the enforcement points; `incomplete` when it
   cannot prove containment.
4. **#21 Evidence snapshot** — a hash-chained forensic artifact produced *at the moment of stop*, before the pod
   is deleted.
5. **#25 Halt drills** — one command to rehearse; the "have you pulled it?" test; measured, published numbers.
6. **The 09:01 readout** — an honest answer to "what is still running a minute later."
7. **Zero-hook-surface containment** — the Plugin4Shell case: a hostile harness is still stopped from outside.

## Migration from `ai-loopguard`

`ai-loopguard` (shipped, MIT) proved the trigger model: detect stuck patterns (repeated error, test-failure loop,
schema-invalid, hallucination cycle) and act at a threshold, tracking cost-per-completed-task and escalation
rate. agenthalt **keeps the detection vocabulary, changes the action**: where `loopguard` escalated to a
stronger model, agenthalt can raise a **composed stop** (and still escalate, if the policy says so). The
capability-by-capability disposition (delivered / delegated / waived) is [PRD 10 — Feature Parity](10-feature-parity.md).
