# PRD 16 — Trigger Catalogue

**BLUF:** A **trigger** is the authenticated way a halt is raised. agenthalt ships **five launch triggers** —
CLI, alert webhook, PagerDuty button, Slack action, keyboard **panic key** — each tested in drills, each
journaled with actor + channel + reason. v0.1.0 also ships the **self-tamper triggers** that fire when the stop
itself is attacked (DD-36). v0.2.0 adds the external **dead-man switches** (the absorbed `ai-loopguard` trigger
class): budget exhaustion, policy tamper, kernel kill triggers — deterministic conditions, never judgments. Every trigger authenticates; the switch is a weapon and entry security is not optional.

**Status:** Draft — v0.1.0 (2026-11-14) · **Owner:** @deghosal-2026 · **Parent:** agentic-suite #209 · PRD #216

## Trigger format (the config surface)

```yaml
triggers:
  - name: siem-alerts
    type: webhook
    auth: { method: hmac, key_ref: "env:AGENTHALT_HMAC_KEY" }
    replay_window_s: 300
    rate_limit: { per_minute: 10 }
    default_scope: agent       # a webhook may never widen to `all` without RBAC (R18)
  - name: panic
    type: panic_key
    binding: interactive-session
    default_scope: agent
  - name: budget-exhaustion          # v0.2.0 — dead-man
    type: dead_man
    source: agentpolicy              # authenticated internal channel
    condition: budget_exhausted
    reason_code: budget_exhausted
    default_mode: pause              # escalate-on-act (PRD 18)
```

- The examples above are shown in YAML-like form for readability; on disk they are TOML `[[triggers]]` tables in
  `agenthalt.toml` (DD-41).
- Triggers are **declarative config**, validated at load (`agenthalt doctor`); an unknown trigger type is a
  config error, never a silent no-op.
- Every trigger carries a **default scope + mode** and a **max scope** it may never widen past without
  authorization (RK-5).
- Every invocation produces a **Trigger record** (actor, channel, reason, signature) journaled before the halt
  resolves — the trigger history is part of the forensic record.

## Launch triggers (v0.1.0) — each exercised in the drill

| Trigger | Fires when | Default scope/mode | Anti-abuse | Drill case |
|---|---|---|---|---|
| **CLI** (`agenthalt halt …`) | An operator types it | any authorized scope / `kill` | OS user + local socket; every invocation journaled | CUJ-1/2 |
| **Alert webhook** | A SIEM/agentwatch/agentpolicy alert POSTs a signed halt request | `agent` / `pause` (escalatable) | HMAC signature, ±5 min replay window, per-source rate limit | CUJ-11 |
| **PagerDuty button** | The on-call clicks the incident's halt action | `agent` (bound to the incident's agent) / `kill` | PagerDuty token + incident linkage | CUJ-11 |
| **Slack action** | An authorized user clicks Halt in the incident channel | `agent` / `pause` | Slack signature + principal; RBAC scope (R18 at v0.2.0; agentinbox anti-spoofing) | CUJ-11, CUJ-25 |
| **Keyboard panic key** | Sam hits the key while an agent runs | the **active local agent** (the most recently started enrolled run of the session user; `doctor` shows which) / `kill` | Interactive session only (macOS: the console user's GUI session, which needs the Accessibility permission for the global hotkey, checked by `doctor`; Linux: the active seat's session); a non-interactive invocation is rejected + journaled; no-op when no agent is active | CUJ-12 |

Acceptance per trigger (R4): it fires in the drill, authenticates, journals actor + channel + reason, and is
idempotent — a duplicate returns the existing receipt.

## Self-tamper triggers (v0.1.0) — attacks on the stop itself (DD-36)

Raised by agenthalt's own integrity checks, inside trust boundary 2 ([PRD 30](30-threat-model.md)). They need no
external producer and do not depend on R18.

| Trigger | Condition | Default mode | Reason code |
|---|---|---|---|
| **Store suppression** | The halt store becomes unreachable, is truncated, or its head stops matching the journal while a halt is armed | `quarantine` on the affected scope, executed through the process/sandbox layers (the choke is already fail-closed) | `tamper_store` |
| **Hook removal / config drift** | A registered hook or harness-config hash changes under an enrolled run | `quarantine` | `tamper_hooks` |
| **Lineage-edge deletion** | A lineage segment fails chain verification or an edge disappears | `quarantine` on the affected subtree | `tamper_lineage` |

Each is journaled with the tampered artifact's identity. A false positive is lifted with `agenthalt lift` like
any other halt.

## Dead-man switches (v0.2.0) — the absorbed `ai-loopguard` trigger class

Deterministic conditions from authenticated ecosystem sources; **conditions, not judgments** — no ML, no
"classifier says rogue." Each fires a halt with a distinct `reason_code` and an auditable event chain.

| Dead-man | Condition | Source | Default mode | Reason code | Origin |
|---|---|---|---|---|---|
| **Budget exhaustion** | A session exhausts an agentpolicy blast-radius budget (files/requests/spend/calls) | agentpolicy | `pause` → escalate on act (hard ceilings → `kill`) | `budget_exhausted` | `ai-loopguard` session budget cap (P16); agentpolicy PRD 18 |
| **Tamper — hooks** *(ships v0.1.0 — see §Self-tamper)* | The agent's hooks/harness config hash changes under it | agentwatch / file watcher | `quarantine` | `tamper_hooks` | The H.R. 9917 incident definition (shutdown sabotage); R5/R16 |
| **Tamper — policy/config** | A policy or agenthalt config hash mismatches the pinned version | agentpolicy / self | `quarantine` | `tamper_policy` | — |
| **Kernel kill trigger** | agentkernel's eBPF containment raises a kill event | agentkernel (Wave 2) | `kill` | `kernel_kill` | PRD #216 R9 |
| **Stuck loop** (v0.3.0, stretch) | Repeated-identical-error / test-failure-loop / schema-invalid patterns sustained | loopguard-style detector (explicit, configured) | `pause` | `stuck_loop` | `ai-loopguard` FailureDetector vocabulary (P1/P2) |

> The stuck-loop triggers are **deferred to v0.3.0** deliberately: they are the closest to "judgment" of the
> set, and shipping them requires the graduated modes (R15) and authorization (R18) to be proven first
> (DD-14). The vocabulary is absorbed at v0.1.0 as design so the config surface does not break later
> ([PRD 10](10-feature-parity.md) P1/P2).

## Trigger governance

- **Every trigger is reviewed like code** — the trigger config is a reviewed artifact; a new trigger path is one
  config entry + one drill case + one PR.
- **Authentication is mandatory** — an unauthenticated trigger type is a config error; the loader refuses it.
- **Scope ceilings are structural** — a trigger's `max_scope` cannot be widened by the request; `all` requires
  the dual-control path (R18, v0.2.0).
- **Journal-first** — the trigger record is written before the halt resolves; a trigger that cannot journal
  fails closed (deny high-impact actions) rather than firing unrecorded.
- **Deprecation** — a retired trigger path is deprecated with a migration note, never silently removed (DD-31).

## What a trigger is *not*

- **Not a detector** — triggers carry *events* from the detection layer (SIEM, agentpolicy, agentkernel); they
  never classify behavior themselves.
- **Not a policy** — whether a condition *should* halt is agentpolicy's question; agenthalt's trigger config
  says what a received event *does*.
- **Not prompt-adjacent** — `KILLSWITCH.md`, system-prompt pleas, and in-loop "stop if unsafe" instructions are
  not triggers; the model gets no vote ([PRD 01](01-why.md)).
- **Not silent** — an unjournaled, unauthenticated, or unrated trigger is a bug, not a shortcut.
