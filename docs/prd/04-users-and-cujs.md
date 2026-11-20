# PRD 04 — Users and Critical User Journeys

**BLUF:** agenthalt serves the platform/security engineer who owns the agent fleet (**P1 Maya**, **P2 Ravi**),
the compliance lead who must show a stop happened (**P3 Dana**), the solo developer who wants a panic key
(**P4 Sam**), and the ecosystem builder who needs an embeddable stop primitive (**P5 Alex**). The v0.1.0
journeys are: stop one agent now, halt everything, contain the lineage, pause and resume, kill the credentials,
disconnect the gateway, freeze the sandbox, preserve the evidence, verify the stop, read the 09:01 readout,
trigger from SIEM/PagerDuty/webhook, hit the panic key, stop a zero-hook-surface harness, emit a halt event,
run a drill, fail closed, and be honest about irreversibility.

**Status:** Draft — v0.1.0 (2026-11-14) · **Owner:** @deghosal-2026 · **Parent:** agentic-suite #209 · PRD #216

## Users

| Persona | Who | What they need from agenthalt |
|---|---|---|
| **P1 Maya — platform/DevEx engineer** (primary adopter) | Runs coding agents for a 20–200 dev org; owns the incident when it goes wrong | One command that stops an agent **and its whole subtree**, safe defaults, no workflow change; terrified of the Replit/Plugin4Shell headlines |
| **P2 Ravi — security engineer / SecOps on-call** | Owns detection and response; agent activity is a new blind surface in his SIEM | A halt he can trigger from PagerDuty or the CLI, a **proof** it worked, and an evidence snapshot he can hand to IR |
| **P3 Dana — compliance / GRC lead** | Owns SOC 2 / ISO 42001 / EU AI Act evidence for the AI stack | Auditor-ready evidence that a stop happened, with provenance from claim → raw event; the EU AI Act stop button, satisfied |
| **P4 Sam — solo developer** | Personal machine, personal keys, 2–3 harnesses | A **panic key** that stops a runaway agent and saves him from a leaked key once; free forever for local use |
| **P5 Alex — agent platform builder (embedder)** | Builds agents/products on LangChain/MCP/custom stacks | An embeddable `halt()` primitive + MCP surface that makes his product "security-review-ready" in a day |

## Users this is *not* for

- Teams that want a **detection product** or an injection classifier — agenthalt detects nothing
  ([PRD 05](05-features.md) §Non-requirements).
- Anyone who wants a **policy engine** — that is agentpolicy; agenthalt *asks* it when a trigger is a budget or
  tamper condition.
- Anyone who wants a **sandbox / credential broker / gateway** — that is agentseatbelt/agentkernel, agentkeys,
  agentgate; agenthalt composes them and owns none.
- Anyone who wants **rollback** — agenthalt stops the *next* action; it never promises to undo one that landed.

## User problems

1. **"We couldn't stop it."** There is no single action that stops an agent everywhere it is acting; the incident
   keeps running while responders find each layer's owner.
2. **`SIGKILL` leaves the graph alive.** Credentials survive, sessions stay open, spawned MCP servers keep
   answering, and sub-agents keep spending under their own tokens.
3. **Kill switches are single-layer.** A gateway switch misses a direct provider call; an identity switch misses
   the current session; a key revoke cuts every agent that shared the key.
4. **Nobody can prove the stop.** Vendors report requests, not confirmations; "parent status = stopped" hides the
   children that are still running.
5. **The stop destroys the evidence.** Deleting the pod or wiping the process removes the record of what it was
   doing — exactly when you need it most.
6. **Nobody has ever pulled it.** A kill switch nobody has drilled is an assumption, not a control.

## Critical user journeys (v0.1.0)

### CUJ-1 — Stop one runaway agent, now ("one command to a stop")
Maya sees an agent mutating production data. She runs one command and the agent's whole subtree stops.

**Acceptance criteria (P0):**

| Step | What happens | Target |
|---|---|---|
| `agenthalt halt --agent <id> --reason "prod mutation"` | halt store written; new actions blocked at runtime + gateway | ≤ 1 s, alert → full stop |
| Process tree | every process in the subtree suspended then killed | zero surviving descendants |
| Credentials | every grant the subtree holds revoked (agentkeys) | revoke **confirmations** logged |
| Gateway | in-flight and subsequent MCP/session calls refused (agentgate) | no post-halt call passes the choke |
| Sandbox | egress blocked; sandbox frozen (agentseatbelt/agentkernel) | no post-halt network call |
| Evidence + receipt | hash-chained snapshot written; proof-of-stop returned | snapshot accepted as forensic artifact |

### CUJ-2 — Halt everything ("the fleet incident")
A compromised key is shared across agents. Maya runs `agenthalt halt --all --reason "key compromise"` and every
ecosystem-visible agent is stopped, with the reason and actor journaled.

**Acceptance criteria (P0):** one action stops all agents the ecosystem can see; each affected run appears in the
receipt; the halt is authorized (RBAC, P1) and journaled; lifting the halt is a separate, logged action.

### CUJ-3 — Contain the lineage ("stop the graph, not the parent")
Ravi halts a coordinator agent. Its spawned specialists, shells and MCP servers must also stop — and agenthalt
must **prove** they did.

**Acceptance criteria (P0):** the lineage registry is walked from the target to every descendant; each descendant
receives the stop and reports `confirmed`; the receipt lists every run ID and its status; **if any descendant is
unconfirmed, the halt is reported `incomplete`, never `done`**; a test proves zero surviving descendants make a
network call.

### CUJ-4 — Pause and resume ("freeze, don't kill")
Maya wants a resumable quarantine: freeze the agent, keep its context, resume later without state corruption.

**Acceptance criteria (P0):** `pause` freezes the subtree and blocks new actions while preserving session state;
`resume` restores full context; pause/resume survives a **24 h wall-clock test**; a paused session that is never
resumed expires to a logged stop.

### CUJ-5 — Kill the credentials, not just the process ("the identity problem")
Ravi halts an agent; the tokens it already holds must stop working, not just the process.

**Acceptance criteria (P0):** agentkeys revokes every grant the subtree holds, including already-issued tokens
where the issuer supports revocation; **confirmations, not requests**, are recorded; the receipt states which
grants were revoked, which will expire naturally, and which are unrevocable (with the residual window).

### CUJ-6 — Disconnect at the gateway ("stop what crosses the choke")
An agent keeps calling MCP servers after its process is frozen. agentgate must refuse it.

**Acceptance criteria (P0):** once the halt is set, the gateway denies every call to and from the stopped subtree,
on the next request; the refusals are written by the gateway (not the agent); the receipt includes the refused-
call count.

### CUJ-7 — Freeze the sandbox ("SIGKILL isn't enough")
The agent has a live socket and a spawned shell. Containment must reach the sandbox/process layer.

**Acceptance criteria (P0):** the process tree is suspended (not just the parent) and its egress blocked; already-
open connections fail on their next send; no new process starts; the frozen sandbox is preserved for evidence
(never deleted before the snapshot is written).

### CUJ-8 — Preserve the evidence ("the snapshot outlives the stop")
As an incident responder, Ravi needs the scene preserved: the agentwatch trace window, the process tree, and the
open connections.

**Acceptance criteria (P0):** on halt, agenthalt writes a **hash-chained, timestamped** snapshot with an
agentwatch reference; the snapshot is tamper-evident (any edit breaks the chain); it is accepted as a forensic
artifact in a dry-run review; the raw secrets it may contain are handled per the security baseline.

### CUJ-9 — Verify the stop ("proof-of-stop")
Ravi must answer, from evidence: did the stop actually stop it?

**Acceptance criteria (P0):** the receipt names every descendant, its stop status, every revoke confirmation, and
the refused-call log; a reviewer can re-derive the stop offline; a `survivors[]` list is empty on a clean halt and
explicit otherwise. **"Parent status = stopped" is never the whole story.**

### CUJ-10 — Read the 09:01 readout ("what is still running?")
Maya asks the question every postmortem asks: a minute after the switch, what is still true?

**Acceptance criteria (P0):** `agenthalt status --halt <id>` prints the readout: unconfirmed descendants, live
grants, queued work the agent had claimed, sibling agents outside the subtree, and downstream agents the stopped
agent handed work to — each with what agenthalt can and cannot do about it.

### CUJ-11 — Trigger from an alert ("the SIEM pulls the switch")
An agentwatch/agentpolicy alert fires in the SOC; Ravi triggers the halt from PagerDuty (or the webhook) without
opening a terminal on the agent's host.

**Acceptance criteria (P0):** the alert webhook and the PagerDuty button both raise a halt; the trigger is
authenticated and journaled; the halt is idempotent (a duplicate trigger returns the existing receipt).

### CUJ-12 — Panic key ("the red button")
Sam hits a keyboard panic key while an agent runs on his laptop; the agent stops.

**Acceptance criteria (P0):** a configurable keyboard panic key raises `halt --agent <active>`; it works with no
network (local halt store); it is a no-op if no agent is active.

### CUJ-13 — Stop a harness with zero hook surface ("the hostile harness")
The harness has no hooks, or its hooks were removed by a Plugin4Shell-class compromise. The agent must still be
stopped.

**Acceptance criteria (P0):** with all agenthalt hooks removed from the harness, a halt still stops the agent via
the process/credential/sandbox layers; a test ships a hostile-harness fixture that tries to ignore the stop.

### CUJ-14 — Halt as a first-class event ("the SOC can alarm on it")
Every halt and its trigger must land in the SOC.

**Acceptance criteria (P0):** the halt and its trigger are emitted in the **agentwatch security-event schema**;
they join the agent's other events on a common id; a SOC dashboard can alarm on halt events.

### CUJ-15 — Run a halt drill ("have you pulled it?")
Before an incident, Ravi rehearses the full stop against a live deployment and gets a measured number.

**Acceptance criteria (P0):** `agenthalt drill` runs the full stop flow (raise → resolve → fan out → confirm →
snapshot → receipt) and reports alert→full-stop time; the drill runs in **CI** on every release; the published
number is **measured**, never assumed; a drill that leaves a survivor fails the build.

### CUJ-16 — Fail closed ("the control plane hiccups")
The halt store is unreachable. The agent must not keep acting.

**Acceptance criteria (P0):** halt store unreachable → the dual choke **denies** new high-impact actions; the
degradation is logged with a distinct reason; the agent sees a structured refusal it can handle; no failure mode
silently allows.

### CUJ-17 — Be honest about irreversibility ("there is no undo")
Ravi halts an agent mid-workflow and needs to know what already landed.

**Acceptance criteria (P0):** the receipt includes a **compensation list** of side effects already committed
(emails sent, records written, calls made) and never claims to have reversed them; the UX states plainly that
recovery is rescope-and-restart.

## P1 journeys (v0.2.0)

### CUJ-18 — Graduate a stop ("pause → quarantine → kill")
Maya pauses first, sees the readout, then escalates to quarantine (cut network) and finally kill.

**Acceptance criteria (P1):** each mode is a distinct, logged step; escalation is one command; a paused subtree
that tries to act is auto-escalated (dead-man); the receipt records the mode history.

### CUJ-19 — Dead-man switch on budget ("stop when it overspends")
An agent exhausts its agentpolicy blast-radius budget; the halt fires automatically.

**Acceptance criteria (P1):** budget exhaustion raises a halt with `reason_code=budget_exhausted`; the trigger
originates in agentpolicy, the stop in agenthalt; the event chain is auditable end to end.

### CUJ-20 — Dead-man switch on tamper ("stop when the controls are edited")
An agent edits its own hooks/policy (or an attacker does). The dead-man switch fires.

**Acceptance criteria (P1):** tamper detection (hook/policy/config hash mismatch, agentkernel kill trigger) raises
a halt; the halt fires even if the agent's own hooks are gone; the trigger is journaled with the tampered
artifact's identity.

### CUJ-21 — Authorize the halt ("who may stop what")
A fleet-wide halt requires two distinct approvers; a single-tenant halt needs the security on-call.

**Acceptance criteria (P1):** RBAC binds halt scopes to roles; fleet/tenant-wide halts require **dual control**
(default quorum 2); a time-boxed **break-glass** halt is possible with a logged reason and auto-reverts; every
halt names its actor.

### CUJ-22 — Halt a third-party agent ("the one you don't host")
The agent is SaaS-hosted; Ravi can't kill its process. He must know what he *can* stop.

**Acceptance criteria (P1):** for a SaaS-hosted agent, agenthalt halts via the layers it *can* reach (credentials,
gateway) and states plainly what it cannot (the vendor's process); the coverage is recorded per agent.

### CUJ-23 — Blast map ("what could it still reach")
Maya asks what the agent could still reach that the stop did not cut.

**Acceptance criteria (P1):** the readout includes a blast map — live credentials, queued work, siblings,
downstream agents, and any unrevocable grant — each with its residual window.

### CUJ-24 — Prove a halt offline ("the auditor")
Dana hands an auditor the evidence bundle; the auditor verifies it on another machine.

**Acceptance criteria (P1):** the receipt + snapshot + agentwatch ref let a third party re-derive the stop offline
without installing agenthalt; the bundle is hash-bound to the halt id and the policy/trigger versions.

### CUJ-25 — Halt from anywhere ("the phone at 3 a.m.")
Ravi approves and triggers a halt from Slack or mobile via agentinbox.

**Acceptance criteria (P1):** the halt can be raised and confirmed from Slack and from agentinbox mobile; the
anti-spoofing rules of agentinbox apply; the trigger is journaled with the channel and principal.

## Later journeys (not v0.1.0 / v0.2.0)

- **Fleet halt policies** — "auto-quarantine any agent matching X" (P2).
- **External halt attestation** — a third party runs the drill pack against your deployment and publishes the
  result (P2).
- **Cross-org halt** — halt an agent acting on behalf of your org inside a partner's estate (P2).

## Success criteria for v0.1.0 users

CUJ-1..CUJ-17 pass on a clean machine; **alert → full stop ≤ 1 s, measured in CI** (CUJ-15); **zero surviving
descendants** post-halt (CUJ-3); a hostile harness with agenthalt's hooks removed is still stopped (CUJ-13); the
evidence snapshot is accepted as a forensic artifact (CUJ-8); a halt is emitted as an agentwatch event the SOC can
alarm on (CUJ-14); no failure mode silently allows (CUJ-16); and every halt is honest about what it could not
stop (CUJ-10, CUJ-17).
