# PRD 10 — Feature Parity

**BLUF:** agenthalt absorbs the **halt-trigger class** of the shipped predecessor **`ai-loopguard`** (#58, MIT,
391 tests, 95.9% coverage) and the enforcement intent of **`BehaviorGuard`** (#192, unbuilt). This document
disposes of **every** absorbed capability — **delivered**, **delegated** (to another ecosystem tool or back to
`ai-loopguard` itself), or **waived** (with reason) — so no capability is silently dropped. The pattern inverts:
where `ai-loopguard` **detected failure and escalated to a stronger model** (in-loop, availability-oriented,
fail-open), agenthalt **stops the whole graph** (out-of-band, safety-oriented, fail-closed). The two compose —
`ai-loopguard` may raise an agenthalt dead-man trigger — and one deliberate semantic inversion is documented
below rather than hidden.

**Status:** Draft — v0.1.0 (2026-11-14) · **Owner:** @deghosal-2026 · **Parent:** agentic-suite #209 · PRD #216

## Source of the absorbed capabilities

- **`ai-loopguard`** — a framework-agnostic circuit breaker + escalation layer for LLM agent loops (shipped
  2026-07-11, MIT, `pip install loopguard`). It proved the trigger model: stuck-pattern detection (repeated
  identical errors, test-failure loops, schema-validation failures, hallucination cycles, custom callbacks),
  threshold semantics (N retries), cost-per-completed-task accounting, escalation logging with an OTel hook, and
  framework adapters (LangGraph, CrewAI). 18 modules, 391 tests, 95.90% coverage, ruff + mypy clean.
- **`BehaviorGuard`** (#192) — an unbuilt behavioral-enforcement idea; only its intent is absorbed (nothing to
  port).

## Capability disposition

| # | Absorbed capability | What it did | Disposition | Where |
|---|---|---|---|---|
| P1 | **Stuck-loop failure detection** — repeated_error, test_failure, schema_invalid, hallucination_cycle, custom callbacks | Detect the death spiral before the invoice arrives | **Delivered, re-pointed** — the full trigger vocabulary becomes **dead-man switch** conditions (R16): where loopguard escalated, agenthalt can stop. Detection stays with loopguard/agentpolicy; agenthalt owns the stop | R16, [PRD 16](16-trigger-catalogue.md) |
| P2 | **Circuit-breaker threshold semantics** (N retries, per-type, custom callbacks) | When to act | **Delivered** — threshold + trigger conditions carry over to the dead-man config; `reason_code` per trigger type carries over verbatim | R16 |
| P3 | **Escalation to a stronger model** (escalation_model, "break the cycle" packaging) | Swap the workhorse mid-loop | **Delegated → `ai-loopguard` itself** — model escalation is an in-loop availability concern, not a stop; agenthalt is the stop primitive. The two compose: loopguard's `on_escalate` may raise an agenthalt trigger | `ai-loopguard` (remains the escalation library) |
| P4 | **Context packaging for escalation** (compress + sanitize + redact the failed loop) | Feed the rescuer model | **Waived for agenthalt** — agenthalt packages **evidence for responders** (the snapshot), not prompts for a model. The escalation packaging stays with loopguard (P3) | R3 (the analog: evidence, not prompts) |
| P5 | **EscalationLogger** (JSONL + OTel event hook, `register_hook()`) | Record what happened | **Delivered, extended** — the halt journal (hash-chained, R12) + agentwatch event emission (R6); the OTel-hook idea is superseded by first-class agentwatch events | R6, R12 |
| P6 | **CostTracker** — cost per *completed task* (retries + escalations + original), escalation rate as the SLO | The real blended cost | **Delegated → agentpolicy blast-radius budgets** (the spend dimension) **+ agentwatch analytics**; agenthalt consumes the `budget_exhausted` trigger and stops | R16; agentpolicy PRD 18 |
| P7 | **GuardState** (thread-safe step recording, per-task reset) | Per-session loop state | **Delivered** — session/run scoping in the halt store (`session`, `run`, `agent` scopes) | R8, [PRD 15](15-data-model.md) |
| P8 | **GuardConfig** (Pydantic; triggers, max_retries, escalation_model) | Configuration | **Delivered** — trigger + mode config model; schema-validated, env-overridable | [PRD 16](16-trigger-catalogue.md) |
| P9 | **Interrupt callback** (custom UI prompts for HITL escalation) | Human-in-the-loop on escalate | **Delegated → agentpolicy `ask` + agentinbox** — the ecosystem's ask-gate owns human gates; agenthalt's own halt-authorization (RBAC/dual-control, R18) uses it at v0.2.0 | R18; agentpolicy R18 |
| P10 | **Fail-open paths** (no model configured, escalation failure → continue) | Availability over safety, in-loop | **Deliberately inverted — fail-closed** — a stop primitive that fails open is not a stop primitive. The inversion is the product's core semantic difference from its predecessor (documented in [PRD 13](13-non-functional-requirements.md), CUJ-16) | R8 |
| P11 | **LangGraph callback handler** | Framework-native monitoring | **Delegated → the ecosystem adapter registry** — runtime adapters where frameworks expose a stop surface, by v0.3.0; containment is already framework-agnostic via the process/credential layers | [PRD 19](19-harness-compatibility.md) |
| P12 | **CrewAI step wrapper** | Framework-native monitoring | **Delegated** — same as P11 | [PRD 19](19-harness-compatibility.md) |
| P13 | **`@guard.protect` / `@guard.aprotect` decorators** | Wrap any Python function | **Waived for agenthalt** — in-process wrapping is the *opposite* of out-of-band: a decorator lives where the agent lives and dies where it dies. Deliberate architectural non-goal (the "if the model can ignore it" rule) | [PRD 14](14-non-goals.md) |
| P14 | **CLI for analyzing escalation patterns from logs** | Post-hoc insight | **Delivered, re-scoped** — `agenthalt status` / `prove` answer "did the stop work, what survived" (the readout + receipt), not escalation analytics | R10, R11 |
| P15 | **Routing vs failover separation** (intentional escalation ≠ availability failure, logged distinctly) | Honest event taxonomy | **Delivered** — the halt journal separates trigger origins (human, dead-man, drill) and modes; every halt names actor + trigger + reason | R12, [PRD 15](15-data-model.md) |
| P16 | **Session budget hard cap** (e.g. `$20/session`) | Spend ceiling | **Delegated → agentpolicy budgets** (the `rate-limit`/halt split is exactly soft vs hard exhaustion); agenthalt is the hard-exhaustion executor | R16; agentpolicy PRD 18 |
| P17 | **Framework-agnostic core + optional extras** (`loopguard[langgraph]`) | Drop-in, not a framework | **Delivered as a principle** — agenthalt's core is harness-agnostic by construction; "adapters are extras, the core owns no framework" is inherited | [PRD 19](19-harness-compatibility.md) |
| P18 | **OTel GenAI integration** (escalation events as span events) | Telemetry | **Delivered, superseded** — the agentwatch security-event schema is the ecosystem's OTel-aligned event surface; halts are first-class events | R6 |
| P19 | **Sanitization/redaction of packaged context** | Don't ship secrets to the rescuer | **Delivered, re-scoped** — the evidence snapshot redacts secrets in the trace window per the security baseline (a forensic artifact is not a secrets dump) | R3, [PRD 06](06-security-baseline.md) |
| P20 | **`reset()` per-task isolation** | Clean state per run | **Delivered** — halt scope resolution and receipt are per run; a completed halt never leaks state into the next | [PRD 15](15-data-model.md) |

## BehaviorGuard (#192) disposition

| Absorbed intent | Disposition | Where |
|---|---|---|
| Behavioral enforcement (act on misbehavior, not just detect) | **Delivered** — as dead-man switches on observable conditions (budget, tamper, kernel kill triggers) and the composed stop; the "act" is now out-of-band and graph-wide | R16, PRD 02 |
| Nothing shipped to port | **Waived** (unbuilt predecessor) | — |

## Parity guarantees

- **No capability silently dropped** — every row above is delivered, delegated (with the owning tool named), or
  waived (with reason).
- **No competing registry** — the stop primitive lives in exactly one tool (agenthalt); escalation lives in
  exactly one (`ai-loopguard`); human gates in one (agentpolicy/agentinbox); budgets in one (agentpolicy).
- **Composition, not supersession** — `ai-loopguard` remains the in-loop escalation library; agenthalt does not
  absorb its job, only its trigger class, and the two are designed to compose (`on_escalate` → dead-man trigger).
- **One documented inversion** — fail-open → fail-closed is a *semantic* change, stated here and in
  [PRD 13](13-non-functional-requirements.md) rather than smuggled in: availability concerns move to loopguard,
  safety concerns move to agenthalt.
