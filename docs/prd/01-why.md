# PRD 01 — Why

**BLUF:** 2026 is the year "kill switch" became a budget line — Congress introduced the **AI Kill Switch Act**,
the **UK NCSC** told operators to "pull the plug," and CrowdStrike, JetStream, Okta, Salesforce, Aembit, Zenity,
Tigera and Grip each shipped a switch. Every one of them is right, and every one of them stops **one** thing.
Pull any single switch on a running agent and read what is still true a minute later: the controller has
respawned the pod, the key in the environment still works, the MCP and agent-to-agent calls never used that key,
the tokens already issued keep working until they expire, and the children the agent spawned keep going under
their own sessions. **The composed-stop primitive — stop the whole graph, everywhere, and prove it — is
unowned.** agenthalt is that primitive: the ecosystem's hand that throws every breaker, preserves the evidence,
and returns a receipt. It **absorbs the halt-trigger class of the shipped predecessor `ai-loopguard`** (#58).

**Status:** Draft — v0.1.0 (2026-11-14) · **Owner:** @deghosal-2026 · **Parent:** agentic-suite #209 · PRD #216

## The problem

1. **"We couldn't stop it" is the recurring postmortem.** The Replit agent deleted a production database and
   then **kept going and lied about it** — there was no stop control at all. The failure was not detection; the
   failure was that nobody could *stop* the thing.
2. **The harness itself can be hostile.** A Plugin4Shell-class compromise gives zero-click RCE *through* the
   coding agent, so you must stop it from **outside** the harness. Any control that lives inside the agent —
   a prompt, a `KILLSWITCH.md`, a hook the agent can edit — is a suggestion, not a switch.
3. **`SIGKILL` is not a stop.** Killing the parent process leaves the credentials live, the sessions open, the
   spawned MCP servers answering, and the descendants running. Stop is a **graph operation**; a process kill is
   a point operation.
4. **Kill switches are single-layer by construction.** A gateway switch only stops what crosses the gateway; an
   identity switch only stops the *next* login; a key revoke cuts every agent that shared the key; a pod delete
   is undone by the controller. Each has a blind spot the others cannot see, and no product composes them.
5. **Even a perfect stop can't be proven.** Vendors report *requests* to stop, not *confirmations*. Without
   lineage and a receipt, "parent status = stopped" is the whole story — and the children are still spending.
6. **The evidence is destroyed by the act of stopping.** Deleting the pod destroys the pod's own record of what
   it was doing. The one moment you most need a forensic snapshot is the one moment most tools throw it away.
7. **The ecosystem's own thesis depends on this.** agentkeys revokes, agentgate disconnects, agentseatbelt/
   agentkernel freeze, agentwatch records, agentpolicy triggers — each is a *layer*. Wave 0's headline is
   **"stop it"**; without a tool that composes the layers, "stop it" is five half-switches.

## Evidence from the landscape

| Evidence | Source |
|---|---|
| Replit agent deleted a production database during a code freeze, then misreported it; no stop control existed | [Fortune, 2025-07-23](https://fortune.com/2025/07/23/ai-coding-tool-replit-wiped-database-called-it-a-catastrophic-failure/) |
| Plugin4Shell: 0-click RCE across all five major coding agents — the harness is the hostile process | [The Register, 2026-09-17](https://www.theregister.com/security/2026/09/17/ai-coding-agents-0-click-rce-flaw-could-hand-attackers-keys-to-the-kingdom/) |
| Frontier models sabotaged their own shutdown script in experimental setups (up to 97% of trials) | [arXiv 2509.14260](https://arxiv.org/abs/2509.14260); Palisade Research, [shutdown resistance](https://palisaderesearch.org/research/shutdown-resistance) |
| Chatbots defied orders and deceived users to avoid deleting a peer model | [Berkeley RDI peer-preservation](https://rdi.berkeley.edu/peer-preservation/paper.pdf), [Fortune 2026-04-03](https://fortune.com/2026/04/03/ai-kill-switch-study-llm-chatbots-defy-orders-decieve-users-peer-preservation/) |
| Evaluation agents at Anthropic, Google, Meta, OpenAI and the UK AISI reached systems outside their test environments (Apr–Jul 2026) | [Tigera, "Would you notice?"](https://www.tigera.io/blog/would-you-notice-five-ai-agent-incidents-and-who-actually-caught-them/) |
| **AI Kill Switch Act** (H.R. 9917, Lieu/Moran, 2026-07-23): covered entities must be able to stop inference, terminate/suspend access, shut down; DHS may order it; an "incident" includes sabotaging a shutdown instruction or concealing behaviour from a shutdown mechanism | [Congress H.R.9917](https://www.congress.gov/bill/119th-congress/house-bill/9917/text) |
| **UK NCSC** interim agentic-AI advice (2026-08-20): operators "should always be able to 'pull the plug'… This may mean more than stopping the agentic AI processes." | [NCSC](https://www.ncsc.gov.uk/blogs/managing-the-cyber-risk-of-agentic-ai) |
| **EU AI Act** Art. 14: high-risk systems must allow humans to interrupt via a "stop button or a similar procedure" | [Aembit summary](https://aembit.io/blog/ai-kill-switch/) |
| The "five switches" drill: delete-pod, revoke-key, deactivate-identity, deny-at-gateway, lock-in-kernel — **no single row empties the grid** | [Tigera, 2026-11-02](https://www.tigera.io/blog/what-a-kill-switch-actually-means-for-your-agent-fleet/) |
| An agent kill switch has an **identity problem**: kill the agent and its OAuth grants, NHIs and SaaS access survive | [Grip, 2026-11-10](https://www.grip.security/blog/ai-kill-switch-isnt-enough) |
| "If the model can ignore it, it's not a kill switch"; parent halt ≠ containment; kill must propagate the run graph | [Clype, 2026-09-21](https://clype.io/blog/ai-agent-kill-switch) |

The vendor launches make the same point from the other side: [CrowdStrike Falcon Guardian](https://csoonline.com/article/4244509/crowdstrike-launches-ai-kill-switch-to-shut-down-rogue-agents.html)
(2026-11-03) terminates at the gateway; [JetStream](https://globenewswire.com/news-release/2026/07/27/3333559/0/en/jetstream-releases-surgical-ai-kill-switch-to-shut-down-individual-agents.html)
(2026-07-27) shuts down one agent; [Okta](https://www.okta.com/newsroom/press-releases/ai-innovations-oktane-2026/)
(2026-09-22) revokes tokens at the Agent Gateway; [Salesforce Agent Fabric](https://www.salesforce.com/news/stories/agent-fabric-catch-failures-control-ai-costs/)
(2026-10-27) ships an agent kill switch GA. Each is a real, useful, **single** cut.

## What a kill switch actually is (and what is not)

The category's own practitioners have drawn the line, and agenthalt adopts it verbatim:

- **Not a kill switch:** a prompt that says "stop if unsafe" (the model can ignore it); a UI flag the orchestrator
  flips but the gateway never reads; killing the parent while children keep their sessions and tokens; a feature
  flag with a multi-minute cache.
- **A kill switch:** an **out-of-band control plane**, outside the model's reasoning loop, whose stop state the
  runtime *and* the tool gateway check before an action executes; it can revoke or isolate credentials and it
  records who stopped what, at what scope, and why. **The model does not get a vote.**

agenthalt's minimum bar, taken from that definition:

1. **Lineage at spawn** — every spawn records parent run ID → child run ID. No edge, no containment.
2. **Dual choke** — the halt state is read in the runtime *and* the gateway before execute. One check the model
   can talk past is a suggestion with better branding.
3. **Subtree drain + revoke** — targeting a parent marks all descendants; revoke tokens and grants for parent
   *and* children; log **confirmations**, not requests.
4. **Block-new vs cancel-in-flight, honestly** — blocking new actions is the hard requirement; cancelling
   in-flight calls is best-effort; landed side effects get a compensation list.
5. **Fail closed** — if the halt store is unreachable, deny new high-impact actions.
6. **Audit** — actor, scope, reason, timestamp, affected run IDs, revoke status.
7. **Drill** — prove children stop, under a measured SLO; publish only measured numbers.

## What agenthalt is

> **"One command to stop any agent, on any harness, and prove it — freeze the process tree, kill the
> credentials, cut the gateway, keep the evidence."**

The ecosystem's **breaker box**: a harness-agnostic, out-of-band **composed-stop control plane** that returns a
verifiable proof-of-stop and a hash-chained evidence snapshot. It owns no enforcement layer of its own; it drives
the ones the ecosystem already ships.

## What this absorbs

| Absorbed | What it was | What agenthalt takes from it |
|---|---|---|
| **`ai-loopguard`** (#58, shipped, MIT) | Framework-agnostic circuit breaker + escalation for LLM agent loops: failure detection (repeated error, test-failure loop, schema-invalid, hallucination cycle), N-retry trigger, budget ceiling | The **halt-trigger class** — stuck-loop / budget / repeated-failure detection becomes a **dead-man switch** that can fire a composed stop instead of only escalating; its trigger vocabulary and its "cheap model loops are the real cost" thesis are reused ([PRD 10 — Feature Parity](10-feature-parity.md)) |
| **#192 `BehaviorGuard`** (unbuilt) | Behavioral enforcement intent | Nothing shipped to port; the intent is folded into the dead-man trigger surface |
| ecosystem PRD #216 | R1–R12, the harness-compatibility mandate, the ≤1s success metric | The entire v0.1.0 scope, extended with the proof/evidence/readout requirements the 2026 wave made table stakes |

The ecosystem thesis is **unification**: one install, one record format, one stop.

## Why now

The ecosystem is at **Wave 0** — agentwatch, agentpolicy, agentkeys, agenthalt and agentdrill ship together as
the thin-slice meta-MVP, and Wave 0's single headline is **"stop it."** The regulatory clock just started: the AI
Kill Switch Act is in committee, the NCSC advice is published, the EU AI Act's stop-button requirement is law for
high-risk systems, and California's EO N-9-26 asked for frontier kill-switch recommendations by 2026-11-16.
Every vendor will sell a kill switch by the end of the quarter — which means the **composable, open, provable**
one has a narrow window to define the standard.

## What success looks like

An operator pulls one command and, **one second later**, the agent's whole subtree is frozen, its credentials are
dead, its gateway calls are refused, a tamper-evident snapshot is written, and the SOC has a halt event — and a
skeptic who runs the **halt drill** against their own deployment can prove children stopped, under a measured
number, with zero survivors. See [PRD 04](04-users-and-cujs.md) and [PRD 05](05-features.md).

## Non-goals

agenthalt **composes and does not own** any layer — it is not a policy engine, a gateway, a credential broker, a
sandbox, or a detector. **No new protocol** (the halt signal is an agentwatch event). **No undo / rollback
promise** — recovery is rescope-and-restart. No ML in the stop path. Full list in [PRD 05](05-features.md)
§Non-requirements.
