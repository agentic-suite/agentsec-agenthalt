# PRD 11 — Decisions

**BLUF:** Accepted decisions for v0.1.0: **Apache-2.0**, Python core with a daemon + CLI, the **halt store as
the single source of stop truth** read by a **dual choke** (runtime + gateway), **fail-closed everywhere**
(an unreachable store denies high-impact actions), **confirmations-not-requests** as the receipt's building
block, the **agentwatch security-event schema** as the machine-readable halt surface, **hash-chained evidence**
written **before** termination, **no ML in the stop path**, **no new protocol**, and the hard architectural
rule that **agenthalt composes layers and owns none**.

**Status:** Draft — v0.1.0 (2026-11-14) · **Owner:** @deghosal-2026 · **Parent:** agentic-suite #209 · PRD #216

## Design & architecture

| # | Decision | Rationale |
|---|---|---|
| **DD-01** | **agenthalt owns no layer** — it composes agentkeys/agentgate/agentseatbelt/agentkernel and executes the stop through their documented actions | A composition tool that grew its own layer would be two products (PRD 02); layers keep their own controls — agenthalt asks, never bypasses |
| **DD-02** | **The halt store is the single source of stop truth**, read by the **dual choke** (runtime + gateway) before an action executes | One check the model can talk past is a suggestion (Clype bar, [PRD 01](01-why.md)); the store sits outside the model's control plane |
| **DD-03** | **Fail-closed everywhere** — store unreachable, adapter failure, lineage gap ⇒ deny new high-impact actions with a distinct `reason_code` | The safe direction is always *stopped* (CUJ-16); the inverse of the predecessor's fail-open availability stance ([PRD 10](10-feature-parity.md) P10) |
| **DD-04** | **Confirmations, not requests** — the receipt is built only from enforcement-point confirmations; `incomplete` is a first-class status | The category fudges with requests; proof-of-stop is the differentiator (R10) |
| **DD-05** | **Block-new-first ordering** — the choke write is synchronous; suspend/revoke/snapshot fan out in parallel within a deadline | Closes the race between the halt write and the layer cuts (PRD 02); keeps the ≤1 s budget honest (RK-4) |
| **DD-06** | **Hooks are optional and never load-bearing** | The Plugin4Shell case: a hostile harness with hooks removed is still contained (R5) |
| **DD-07** | **No ML / no detection in the stop path** — triggers are deterministic events from authenticated sources | Determinism is a product requirement; detection is somebody else's job (agentwatch, agentpolicy, the SIEM) |
| **DD-08** | **Harness-agnostic by construction** — containment at the process/credential/sandbox layers | The ecosystem's non-negotiable; works for any harness the ecosystem can see, including zero-hook-surface ones |
| **DD-09** | **The halt signal is an agentwatch event — no new protocol** | Composition of existing layers only; the halt event is the entire standard surface (ecosystem PRD #216 non-requirement) |
| **DD-10** | **Snapshot before termination** — the evidence is written before any process is destroyed | The stop must not destroy the scene it is preserving (RK-6); order is architectural, not an optimization |
| **DD-11** | **Irreversibility is stated, never fudged** — a mandatory compensation list; recovery is rescope-and-restart | The category's biggest lie is rollback theater; honesty is the feature (R13) |

## Scope

| # | Decision | Rationale |
|---|---|---|
| **DD-12** | **v0.1.0 = Wave 0**: composed stop + lineage + evidence + proof + readout + journal + triggers + pause/resume + drill | Matches the release-roadmap meta-MVP; "stop it" is Wave 0's headline |
| **DD-13** | **All three rungs ship at v0.1.0 as explicit commands; graduated semantics ship v0.2.0** | `kill`, `pause`/`resume` (R7) and a basic `quarantine` (network cut + issuance freeze) are operator-driven at v0.1.0, with a manual `escalate`. Escalate-on-act and auto-escalation defaults (R15) wait until each rung is proven end-to-end ([PRD 18](18-stop-modes.md)) |
| **DD-14** | **External dead-man switches are v0.2.0** (budget, kernel, the absorbed `ai-loopguard` class); self-tamper triggers ship at v0.1.0 (DD-36) | The trigger vocabulary is absorbed at v0.1.0 as design; live automatic halts from external producers need agentpolicy budgets in production first. Tamper on agenthalt's own surfaces needs no external producer |
| **DD-15** | **No console/UI beyond CLI in v1** | The stop is a command; review lives in receipts, events, and git |
| **DD-16** | **Fleet `all` halts require dual control at v0.2.0; v0.1.0 documents the blast radius loudly** | The switch must not be a DoS lever (RK-5); v0.1.0 is single-operator by scope (local-first), the authorization layer lands with agentinbox. **v0.1.0 interim control:** `all` can be raised only from the local CLI by the OS principal that owns the store, with a typed confirmation; every remote trigger's `max_scope` is capped at `agent` ([PRD 16](16-trigger-catalogue.md)) |
| **DD-17** | **macOS + Linux at v0.1.0; Windows documented not-supported with a dated plan** | The ecosystem's platforms; cross-platform process semantics are the top technical risk (RK-9) |
| **DD-18** | **agentgate disconnect degrades honestly until agentgate v1.0 (Wave 1)** | The adapter reports `unsupported`; the receipt names the missing cut — never a silent skip (PRD 09) |

## Technical

| # | Decision | Rationale |
|---|---|---|
| **DD-19** | **Python core** (library + `haltd` daemon + CLI + MCP server), shared coordinator engine | Ecosystem parity (agentwatch/agentpolicy/agentkeys are Python); one engine, several surfaces |
| **DD-20** | **`pip install agentsec-agenthalt`**, CLI `agenthalt`, package `agenthalt` | Ecosystem naming convention |
| **DD-21** | **Local artifacts under `.agenthalt/`** (journal, receipts, snapshots, drill results) | Local-first; sibling to the ecosystem stores |
| **DD-22** | **≤1 s alert → full stop** is the measured CI budget; the synchronous portion is the choke write | The #216 success criterion; everything slower runs parallel/deadline-bounded and reports honestly (RK-4) |
| **DD-23** | **Per-OS executor adapters** (process group / cgroup suspend semantics isolated per platform) | Cross-platform containment is adapter work, not cleverness (RK-9) |
| **DD-24** | **Lineage edges are append-only** and hash-chained with the journal | Edge deletion/poisoning must be detectable (PRD 06); no edge, no containment |
| **DD-25** | **Triggers authenticate** (HMAC/mTLS/interactive-session per path) with replay protection | The switch is a weapon; entry security is not optional (PRD 06, RK-5) |
| **DD-26** | **Hash-chained journal + anchored rotation**; receipt entries signed by enforcement points | Tamper-evidence for the record; forgery-proofing for the proof (R12, RK-11/12) |
| **DD-27** | **Idempotent halts** — re-raise returns the existing receipt | Duplicate alerts must not interleave states (PRD 06) |
| **DD-28** | **Apache-2.0 license** | Ecosystem standard; matches repo LICENSE |

## Governance

| # | Decision | Rationale |
|---|---|---|
| **DD-29** | **Measured numbers only** — published stop times are CI drill measurements on stated hardware | "Do not publish a latency number you have not measured" (Clype); the honesty moat |
| **DD-30** | **Every release ships**: notes + compatibility table + security audit + standards/regulatory matrix + drill numbers | Org governance floor (PRD 09) |
| **DD-31** | **Flag, never silently change** — stop semantics, mode defaults, trigger behavior changes are versioned with migration notes | A responder's muscle memory is a dependency; no quiet edits |
| **DD-32** | **The drill is release-blocking** — a survivor anywhere fails the build; the self-halt pack runs every release | A switch nobody pulled is a label on a box (R14, PRD 06) |
| **DD-33** | **agenthalt is the ecosystem's single composed-stop entry point** — layers expose actions, not parallel kill policies | Ecosystem divergence is the structural risk (RK-21); one breaker box |
| **DD-34** | **Claims vocabulary enforced in CI** — "composes", "verified in the drill", and "aligned to" are allowed; "H.R. 9917 compliant", "stops anything", "undoes" are forbidden | Regulatory overreach and rollback theater are banned claims (PRD 20 §G, RK-18/19) |
| **DD-35** | **Signed releases + provenance** (Sigstore/SLSA) | Supply-chain trust; a security control's own supply chain must be clean |

## Added in the PRD consistency review (2026-11-27)

| # | Decision | Rationale |
|---|---|---|
| **DD-36** | **Self-tamper triggers ship at v0.1.0.** Store suppression, hook/config hash mismatch, and lineage-edge deletion raise a halt (`tamper_store` / `tamper_hooks` / `tamper_lineage`) | PRD 06, 27, 30 and drill case `edge-forgery` depend on "suppression is itself a trigger". These triggers start inside agenthalt's own trust boundary, so they need neither agentpolicy nor R18 ([PRD 16](16-trigger-catalogue.md)) |
| **DD-37** | **Pause max-TTL defaults to 24 h**, expiring to `kill` with `reason_code=pause_expired`; configurable per scope | Closes the pause-TTL tension for v0.1.0 (RK-15); revisited with design-partner data |
| **DD-38** | **Enrollment via `agenthalt run` / `agenthalt attach`** | "No edge, no containment" needs a root. A launcher that owns the process group/cgroup from spawn is the only hook-free way to get one ([PRD 02](02-architecture.md) §Mechanisms) |
| **DD-39** | **Receipt status precedence: `failed` > `incomplete` > `partial-layer` > `complete`** | One halt can have a survivor *and* a missing layer; the worst true status wins, and exit codes follow it ([PRD 26](26-receipt-schema-and-examples.md), [PRD 37](37-cli-and-output-ux-spec.md)) |
| **DD-40** | **Self-attested confirmations are labelled** (`attestation: self`) | agenthalt's built-in OS executor cannot be its own independent witness; the verifier reports self-attested cuts distinctly ([PRD 26](26-receipt-schema-and-examples.md)) |
