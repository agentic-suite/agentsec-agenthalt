# PRD 08 — Risks

**BLUF:** agenthalt's credibility *is* the product, so its top risks are the ones that make a stop fail or lie:
**fail-open** (a path that keeps the agent running), **lineage gaps** (an untracked descendant survives), **false
success** (a receipt that claims what a request asked for), **trigger abuse** (the switch turned against the
fleet), and **evidence loss** (the snapshot destroyed by the stop or the attacker). Second tier: latency on the
≤1 s budget, harness/kernel churn, cross-platform process semantics, and scope creep into enforcement. Each has
a trigger and a mitigation.

**Status:** Draft — v0.1.0 (2026-11-14) · **Owner:** @deghosal-2026 · **Parent:** agentic-suite #209 · PRD #216

## Risk register

| # | Risk | Likelihood | Impact | Trigger | Mitigation |
|---|---|---|---|---|---|
| **RK-1** | **Fail-open** — some path keeps the agent acting after a halt | Medium | Critical | A new code path returns "not halted" on error | Fail-closed contract is a CI test over a fuzzed failure matrix; every failure has a distinct `reason_code`; the dual choke defaults to deny (R8, CUJ-16) |
| **RK-2** | **Lineage gap** — a descendant is never enumerated (edge missing at spawn) | High | High | A harness/framework spawns children agenthalt's adapter never sees | **No edge, no containment**: an untracked-descendant finding is a loud drill failure; adapters registered per spawn surface; the readout names unknown-descendant risk (R9, R10) |
| **RK-3** | **False success** — the receipt claims stops that never confirmed | Medium | Critical | An adapter reports `requested` and the receipt rounds it up | Receipt is built from confirmations only; `incomplete` is a first-class status; receipt-forgery is a self-halt pack case (R10, PRD 06) |
| **RK-4** | **≤1 s budget blown** — the composed stop is slower than the sum of its parts | Medium | High | Layer fan-out serializes slow adapters (e.g. a slow revoke API) | Block-new at the choke is synchronous and fast; heavy cuts (revoke, snapshot) run in parallel within a deadline; the drill measures and publishes; partial confirmation is honest `incomplete` (R1, R14) |
| **RK-5** | **Trigger abuse / DoS via the switch** — a hostile party (or a spoofed alert) halts the healthy fleet | Medium | High | A forged webhook or a flapping SIEM rule | Trigger authentication + replay protection; per-principal rate limits; fleet scope is local-CLI-only with a typed confirmation at v0.1.0 (DD-16), dual control at v0.2.0 (R18); every halt journaled with actor (PRD 06) |
| **RK-6** | **Evidence destroyed** — the stop deletes the scene before the snapshot (or the attacker does after) | Medium | High | Pod deletion orders process kill before collect | **Snapshot-before-termination** is an architectural rule (F10/F11 order); snapshot exported off-host; chain verification detects post-halt edits (R3) |
| **RK-7** | **Unrevocable credentials survive** — static keys copied out of agentkeys' reach | High | Medium | The agent holds a long-lived static key | The receipt names unrevocable grants + residual windows (never claims full revoke); short-lived issuance (agentkeys R9) is the durable fix; the readout surfaces them (CUJ-5, CUJ-23) |
| **RK-8** | **Gateway bypass** — a direct provider connection never crosses agentgate | Medium | High | The harness routes around the proxy | Dual choke + sandbox egress block; the readout names uncovered routes; agentkernel closes kernel-level egress where deployed (R11, PRD 02) |
| **RK-9** | **Cross-platform process semantics** — process groups/cgroups differ across macOS/Linux/Windows | High | Medium | A suspend works in CI (macOS) but not on Linux or vice versa | Platform-specific executor adapters with per-OS drill legs; documented matrix; agentkernel owns Linux eBPF containment (PRD 05 §Compatibility) |
| **RK-10** | **Shutdown sabotage / concealment** — the agent attacks the stop (the H.R. 9917 incident definition) | Medium | High | Hooks removed, store suppressed, halt message eaten | The stop lives outside the model's control plane; hooks are never load-bearing (R5); store suppression is itself a self-tamper trigger (DD-36, PRD 06) |
| **RK-11** | **Journal tamper** — an operator edits the halt history after a bad halt | Low | High | An incident review finds an inconvenient halt record | Hash chain + rotation anchors + verification command (R12); a missing segment is a loud finding |
| **RK-12** | **Receipt forgery** — a fake proof-of-stop for a still-running agent | Low | Critical | An attacker fabricates confirmations | Receipt entries signed by the enforcement points; offline verifier re-derives the chain (R10, R21) |
| **RK-13** | **Scope creep into enforcement** — a PR adds "just one" layer capability (a mini-gateway, a mini-broker) | Medium | Medium | An adapter grows its own enforcement logic | Architecture rule: agenthalt composes and owns no layer (PRD 02); non-goals (PRD 14); adapter schema forbids inline enforcement |
| **RK-14** | **Halt-store availability** — the store is a single point of failure *and* a halt target | Medium | High | The store crashes or is partitioned at halt time | Local-first with fail-closed semantics; store-down → choke denies high-impact actions (never allow); manual-fallback runbook ships with the tool (PRD 06) |
| **RK-15** | **Pause-limbo** — paused sessions pile up forever, "resumable" becomes a liability | Medium | Medium | Nobody resumes; credentials stay warm; state rots | Pause has a **max TTL** (default 24 h) auto-expiring to a logged kill; the status command lists paused runs (R7, PRD 18) |
| **RK-16** | **Drill theater** — the drill tests the demo path, not the real fleet | Medium | High | The drill fixture drifts from real harness topologies | The drill runs per-platform and against the field-test matrix; partners run their own (R17); a survivor anywhere fails the build |
| **RK-17** | **Harness/OS churn** — spawn surfaces and process APIs move under us | Medium | Medium | A harness update changes its subprocess model | Layer adapters are narrow and each has a watchlist leg; harness-compat table regenerated per release (PRD 19) |
| **RK-18** | **Regulatory overreach** — marketing claims legal compliance ("H.R. 9917 compliant") | Medium | Medium | A claims drift into regulation territory | Claims vocabulary (PRD 20 §G): alignment is documented, compliance is claimed only with counsel; the claims linter runs in CI |
| **RK-19** | **Irreversibility misunderstanding** — a user believes the halt "fixed" what already landed | Medium | Medium | A receipt omits the compensation list | The compensation list is mandatory (R13); the CLI prints it on every kill; docs state recovery is rescope-and-restart |
| **RK-20** | **Escalation to kill by default** — operators reach for `kill` when `pause` would do, destroying evidence | Medium | Medium | Muscle memory + incident stress | `pause` is the documented first move for the uncertain case; `kill` requires an explicit reason; mode history is journaled (PRD 18) |
| **RK-21** | **Ecosystem divergence** — a layer grows its own halt path (agentgate "disconnect" becomes a parallel kill) | Medium | High | A tool ships a bespoke stop | agenthalt is the single composed-stop entry point; layers expose actions, not policies, to it (DD-01, RK-16 in agentpolicy terms) |
| **RK-22** | **Self-halt pack rots** — stops tracking the real attack surface | Medium | High | A new feature (triggers, modes) ships without a self-halt case | Every new surface feature adds/updates a self-halt case; pack coverage reported with the release (PRD 06) |
| **RK-23** | **macOS lineage escape** — a child calls `setsid` / double-forks out of the process group | High | High | A harness or agent daemonizes helpers | Supervisor ancestry polling + session/uid scoping; an escape is a `lineage_gap` finding, never silent; agentseatbelt (Endpoint Security) closes it where deployed ([PRD 27](27-lineage-model.md)) |
| **RK-24** | **Remote listener exposure** — the webhook/PagerDuty/Slack endpoints make `haltd` network-facing | Medium | High | A listener is bound beyond localhost or its key leaks | Localhost by default; remote listeners opt-in, authenticated, rate-limited, `max_scope ≤ agent`; a listener failure never blocks local halts ([PRD 30](30-threat-model.md)) |
| **RK-25** | **Self-attestation** — with no agentseatbelt/agentkernel, agenthalt signs its own process cuts | High | Medium | A Wave-0 stack with only the built-in OS executor | Confirmations labelled `attestation: self`; the verifier reports them distinctly; third-party attestation arrives with the composed layers (DD-40) |

## Hard parts

1. **Cross-platform subtree containment.** Process groups (macOS/BSD), cgroups (Linux), and job objects
   (Windows) suspend differently, and spawn methods differ per harness. Solved with per-OS executor adapters +
   the drill's per-platform legs — not with cleverness.
2. **The ≤1 s budget across a fan-out.** One second for halt-state propagation + process suspend + revoke
   calls + snapshot start. Solved by sequencing: the *blocking* step (choke write) is synchronous; everything
   else runs parallel within a deadline; the receipt tells the truth about what landed in budget.
3. **Lineage completeness without hooks.** Where a harness offers no spawn hook, edges come from the process/
   runtime adapters (parent→child pid tracking), which is best-effort — the honest answer is the drill's
   survivor detection plus the readout, never a quiet assumption.
4. **Proving a negative.** "Zero survivors" can only be *tested* (no post-halt network call observed in the
   drill), not proven — the receipt's language and the docs must say *verified in the drill*, not *guaranteed*.
5. **Evidence at stop time without slowing the stop.** The snapshot must not serialize before the block; it
   starts in parallel and the receipt references it when complete (or reports it pending honestly).

## Triggers to revisit

- A fail-open path is found → RK-1 escalation to release-blocking.
- A drill leaves a survivor → RK-2/RK-16: halt the release, fix lineage or drill.
- A trigger spoof/flood in the wild or in a pentest → RK-5 auth hardening cycle.
- A platform API change (macOS/Linux) breaks a drill leg → RK-9/RK-17 watchlist update.
- A vendor/harness changes its spawn surface → RK-2 adapter update + compatibility-table refresh.
- A regulatory development (H.R. 9917 movement, EU AI Act guidance) → RK-18 standards review (PRD 20).

## Open questions

- **Lineage edge source priority** — harness hook vs. process adapter vs. runtime adapter when they disagree
  (hypothesis: process adapter wins; it is the one containment actually acts on — needs design-partner data).
- ~~Pause max-TTL default~~ — **decided: 24 h (DD-37)**; revisit with design-partner data (RK-15).
- **Fleet-halt dual-control quorum** — 2 is the default; is 2 enough for `all`? (needs design-partner input).
- **Snapshot retention** — how long, where, and who can read secrets captured in the trace window? (ties to the
  security baseline and agentwatch retention policy).
- **Windows v0.1.0?** — hypothesis: macOS + Linux ship first (the ecosystem's platforms); Windows documented as
  not supported with a dated plan.
- **In-flight cancel honesty** — which layers can actually cancel an in-flight call (gateway: yes; process: no)
  — the receipt must state it per layer, and the copy must never promise synchronous cancel.
