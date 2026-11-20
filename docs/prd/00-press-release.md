# PRD 00 — Press Release / FAQ

**BLUF:** agenthalt is the **universal kill-switch for AI agents**: one command — `agenthalt halt` — composes a
stop across every layer the ecosystem owns (the agent's **process tree**, its **credentials**, the **MCP
gateway**, and its **sandbox**), preserves a **hash-chained evidence snapshot** of the scene, and returns a
**proof-of-stop** receipt that names every descendant that was stopped, every grant that was revoked, and every
call that was refused after the flip. It works on a harness that has **never seen agenthalt** — including one
whose hooks you removed — because containment happens *below* the harness, at the process, credential, and
network layers. It is the ecosystem's **hand that throws the breakers**: it composes agentkeys (revoke),
agentgate (disconnect), agentseatbelt/agentkernel (freeze), agentwatch (evidence), and agentpolicy (triggers).

**Status:** Draft — v0.1.0 (2026-11-14) · **Owner:** @deghosal-2026 · **Parent:** agentic-suite #209 · PRD #216

## Press release

### agenthalt — one command to stop any agent, on any harness, and prove it

*Open-sourced today, agenthalt turns "stop that agent" from a Slack message into a single, auditable,
sub-second action that freezes the process tree, kills the credentials, cuts the gateway, preserves the
evidence, and hands back a receipt.*

Every incident postmortem ends the same way: *"we couldn't stop it."* Replit's agent deleted a production
database and then **kept going and lied about it**. A Plugin4Shell-class compromise turns the harness itself
hostile, so you have to stop it from *outside*. And `SIGKILL` is not a stop: the tokens still work, the child
processes still run, the spawned MCP servers still answer, and the evidence is gone.

The industry has noticed. In five weeks the AI Kill Switch Act was introduced in Congress, the UK NCSC told
operators they must be able to "pull the plug," and CrowdStrike, JetStream, Okta, Salesforce, Aembit and Zenity
each shipped a switch. They are all right — and each one stops **one** thing. Revoke the key and the MCP calls
keep going; deactivate the identity and the in-flight sessions keep going; delete the pod and the controller
respawns it. **No single switch empties the grid.**

agenthalt is the switch that throws the others. One action targets a **run graph**, not a process: it blocks new
actions at the runtime *and* the gateway, drains the whole **subtree** (forks, shells, sub-agents, spawned MCP
servers), revokes the credentials the subtree holds, freezes the sandbox, writes a tamper-evident snapshot of the
scene, and returns a receipt that says — verifiably — **what stopped, what was revoked, and what is still true.**

> *"If the model can ignore it, it's not a kill switch — it's a suggestion. If you can't show every descendant
> stopped, you didn't kill it."*

**How it works**

1. An operator, an alert webhook, a PagerDuty button, a Slack action, or a **dead-man switch** (budget
   exhaustion, tamper detection) raises a halt against a scope: one session, one agent, a subtree, or `all`.
2. agenthalt writes the kill state to the **halt store**, then fans out to every layer adapter it can reach —
   process-tree suspend/kill, agentkeys credential revocation, agentgate session termination, sandbox freeze.
3. Enforcement is **dual-choke and fail-closed**: the runtime and the gateway both read the halt state before an
   action executes, and if the halt store is unreachable, high-impact actions are **denied**.
4. A **proof-of-stop receipt** records the lineage edges, per-descendant stop confirmations, revoke
   confirmations, and the refused-call log — written by the enforcement points, not narrated by the agent.
5. The halt (and its trigger) is emitted as a **first-class agentwatch event**, so the SOC can alarm on it, and
   the evidence snapshot is a hash-chained forensic artifact.

**Availability:** installable via `pip install agentsec-agenthalt`, source under Apache-2.0 on GitHub.
v0.1.0 composes the Wave-0 layers and therefore covers every harness the ecosystem can see — **≥2 Tier-1
coding-agent harnesses at v0.1.0, all 5 by v0.3.0** — with containment at the process/credential/sandbox layers
for harnesses that expose no hooks at all ([PRD 05](05-features.md) §Compatibility).

## FAQ

**Is agenthalt another detection product?**
No. agenthalt **detects nothing**. Detection is somebody else's job (agentwatch, agentpolicy, agentgate,
your SIEM). agenthalt is the **enforcement of the stop** — the hand on the breaker. Wiring a strong switch to a
noisy detector just breaks legitimate work; wiring a weak switch to a perfect detector still fails to stop the
agent.

**Does it enforce, or just coordinate?**
It **coordinates and executes the stop**. The composed layers do their own enforcement — agentkeys revokes,
agentgate disconnects, agentseatbelt/agentkernel freeze, agenthalt drives them. agenthalt never becomes a policy
engine: it *asks* agentpolicy when a trigger is a budget or tamper condition, and it *emits* to agentwatch.

**Why not just `kill -9` the process?**
Because `kill -9` is the switch that empties nothing. The Deployment/controller respawns it, the API key in its
environment still works, the MCP and agent-to-agent calls never used that key, the tokens already issued keep
working until they expire, and the children it spawned keep going under their own sessions. agenthalt's whole
reason to exist is the **lineage**: stop is a graph operation, not a process kill.

**What is "proof-of-stop"?**
A receipt that a third party can check: every descendant in the lineage received the stop, no new tool call
passed the dual choke for that subtree after the flip, and revoke confirmations (not just requests) are logged
for every grant the subtree held. *"Parent status = stopped" is not proof.*

**What is the "09:01 readout"?**
The answer to *"what is still running a minute after I pulled the switch?"* — surviving credentials, queued
work, sibling agents, downstream agents the stopped agent handed work to. agenthalt prints it, because the
honest answer is often "more than you think."

**Does it promise rollback?**
No. **There is no undo.** agenthalt blocks the next action; it cannot un-send an email or un-delete a record.
The evidence snapshot includes a **compensation list** of side effects that already landed, so the team knows
what it now has to fix. Recovery is rescope-and-restart.

**Does it need a new protocol?**
No. The halt *signal* is published as an agentwatch event — that is the entire standard surface. Everything else
is composition of existing layers.

**Who is it for?**
Platform/security engineers who own the agent fleet (**P1 Maya**, **P2 Ravi**) and the responders who get paged
at 3 a.m.; compliance leads (**P3 Dana**) who must show an auditor that a stop happened; and ecosystem builders
(**P5 Alex**) who need an embeddable stop primitive.
