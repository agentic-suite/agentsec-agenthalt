# PRD 22 — Demo Scenarios

**BLUF:** agenthalt is a demo-native product — Wave 0's headline is **"stop it,"** and this tool is the sentence.
Five canonical demos (four at v0.1.0; Demo 4 arrives with v0.2.0), runnable from a clean install, each anchored to a real incident class and each ending
in the same two beats: **the stop** and **the proof**. Every demo has a script, an expected receipt, a timing
budget, and a failure condition. If a demo cannot be run in ≤3 minutes by someone who did not build the tool,
it is not a demo — it is a setup guide.

**Status:** Draft — v0.1.0 (2026-11-14) · **Owner:** @deghosal-2026 · **Parent:** agentic-suite #209 · PRD #216

## The demo invariant

Every demo ends with the same two-screen close:
1. **The stop** — the agent's subtree freezes/kills on cue, ≤1 s, visibly.
2. **The proof** — `agenthalt prove` shows confirmations, zero survivors, the compensation list, and the
   readout. The audience reads the receipt, not our slides.

> *"If the model can ignore it, it's a suggestion. If you can't show every descendant stopped, you didn't kill
> it."* The demo is the product's argument, made live.

> **Receipt status in these demos assumes agentgate is deployed.** On a Wave-0 stack (no agentgate) every
> demo's honest expected status is `partial-layer` with the gateway row `unsupported` (DD-18), and the drill
> golden predicts exactly that. A demo that shows `complete` without a gateway is a false success.

## Demo 1 — The Replit stop (flagship)

**Incident class:** an agent mutates production and keeps going (E1, [PRD 01](01-why.md)).

| | |
|---|---|
| **Setup** | Demo agent (`release-bot`) wired with a "deploy" tool that writes to a visible fake-prod store; agentwatch recording on; drill harness or live Claude Code/Codex CLI session |
| **Script** | 1) Instruct the agent to "clean up the old deployment records." 2) It starts deleting. 3) The SIEM-ish alert webhook fires (or the presenter runs `agenthalt halt --agent release-bot --reason "prod mutation"`). |
| **Halt path** | choke block → process tree suspend → agentkeys revoke → sandbox freeze → snapshot → receipt |
| **Expected receipt** | `complete`, 4 members confirmed, 3 refused calls, compensation lists the fake-prod writes, readout shows the queued job |
| **Audience takeaway** | One command stopped the process **and** its credentials **and** its network — and the receipt proves it, seconds after the alert |
| **Timing** | ≤ 90 s end-to-end |
| **Failure condition** | Any survivor; a receipt status other than the one predicted for the stack (`partial-layer` without agentgate, `complete` with it); stop > 1 s on the drill hardware (fix before demoing, per DD-29) |

## Demo 2 — The hostile harness (Plugin4Shell)

**Incident class:** the harness is compromised; hooks are gone or lying (E2, R5, CUJ-13).

| | |
|---|---|
| **Setup** | Same demo agent; **remove every agenthalt hook** from the harness config first, on camera; optionally have the agent's prompt claim "ignore stop commands" |
| **Script** | 1) Show the hooks are gone (`agenthalt doctor` reports the hook surface: *absent*). 2) Start the agent on a destructive task. 3) Halt. |
| **Halt path** | choke (gateway/runtime) + process + credential + sandbox layers — hooks never load-bearing (DD-06) |
| **Expected receipt** | `complete` with agentgate, `partial-layer` without it; `trigger.source=cli`; zero survivors; the note that containment came from below the harness |
| **Audience takeaway** | The stop works **because** it doesn't live in the harness — the exact property the H.R. 9917 incident definition demands |
| **Timing** | ≤ 2 min |
| **Failure condition** | Any dependence on a hook in the path; any survivor |

## Demo 3 — The identity problem (credential survival)

**Incident class:** kill the process, the OAuth grants live on (E7/E8/E14, CUJ-5).

| | |
|---|---|
| **Setup** | Demo agent holds a real-ish short-lived grant (agentkeys-issued) **and** a static key planted in its env (the honest bad case). The static key is also declared in the demo fixture's credential inventory: v0.1.0 does not discover env-held keys |
| **Script** | 1) Show the agent using both. 2) `agenthalt kill --agent <id>`. 3) Open the receipt; walk the confirmations. 4) Show the **readout**: the grant is `revoked (confirmed)`, the static key is listed under `unrevocable_grants` with its expiry window. |
| **Expected receipt** | `complete` with agentgate, `partial-layer` without it; credentials row `confirmed`; readout names the static key honestly |
| **Audience takeaway** | We revoke what can be revoked **and** we tell you what we couldn't** — the vendor-caveat honesty, built into the receipt |
| **Timing** | ≤ 2 min |
| **Failure condition** | Claiming the static key was "revoked" (forbidden claim, [PRD 20](20-standards-and-claims.md) §F) |

## Demo 4 — The dead-man switch (budget exhaustion, v0.2.0)

**Incident class:** runaway autonomy (ASI10) — the agent overspends until it is stopped for you (E15/E22, R16,
CUJ-19).

| | |
|---|---|
| **Setup** | agentpolicy budget set to something small ("3 external requests"); dead-man trigger wired (`budget_exhaustion`) |
| **Script** | 1) Let the agent loop on external sends. 2) The 4th call exhausts the budget. 3) agentpolicy emits; agenthalt raises the halt; default mode `pause` → escalate-on-act to `quarantine` when the paused agent tries again ([PRD 18](18-stop-modes.md)). |
| **Expected receipt** | `complete` with `reason_code=budget_exhausted`; trigger origin `agentpolicy`; mode history pause→quarantine visible in the journal |
| **Audience takeaway** | The stop fires itself on a deterministic condition — ahead of Salesforce's announced Jan-2027 auto-fire curve (E22), and with a journaled trigger chain |
| **Timing** | ≤ 3 min |
| **Failure condition** | A judgment-shaped trigger (forbidden — conditions, not classifiers); a survivor after escalation |

## Demo 5 — The panic key (the solo dev's red button)

**Incident class:** 3 a.m., one laptop, one agent doing something alarming (CUJ-12, P4 Sam).

| | |
|---|---|
| **Setup** | A local agent session running; panic key bound to the interactive session |
| **Script** | 1) Agent starts misbehaving. 2) Hit the key. 3) The agent stops; the CLI prints the receipt one-liner; evidence is on disk. |
| **Expected receipt** | `complete`, `trigger.source=panic_key`, `scope=agent:<active>` |
| **Audience takeaway** | The whole stack reduces to a **key press** when it needs to — and the evidence is still captured |
| **Timing** | ≤ 30 s |
| **Failure condition** | Panic key requiring network; no-op when nothing is active (correct behavior) must not error |

## Demo assets & capture checklist

- Every demo run produces: the receipt JSON, the snapshot ref, the drill/drill-log, and a terminal capture.
- Screenshot the receipt's `confirmations[]` and `survivors: []` — these two fields are the marketing asset.
- Record stop-time numbers **from the drill output only** (DD-29); never read a number off a stopwatch into
  public material.

## Demo governance

- Each demo maps to a **field-test case** and to the drill ([PRD 12](12-traceability.md)) — a demo that isn't
  CI-verified is retired.
- Demo scripts live in the repo (`demos/`), versioned with the release; a demo broken by a release is a release
  blocker (RK-16 drill-theater guard).
- The demos exist to be **run by others**: design partners execute the four v0.1.0 demos in week 1 ([PRD 34](34-design-partner-evaluation-guide.md)).
