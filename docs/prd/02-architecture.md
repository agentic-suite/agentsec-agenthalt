# PRD 02 — Architecture

**BLUF:** agenthalt is an **out-of-band composed-stop control plane** — a daemon (`haltd`) that turns one halt
request into a coordinated stop across every ecosystem layer the target touches, then writes a tamper-evident
evidence snapshot and returns a **proof-of-stop** receipt. It owns **no enforcement layer**: process-tree
containment is agentseatbelt/agentkernel, credential revocation is agentkeys, gateway disconnection is agentgate,
recording is agentwatch, and budget/tamper triggers are agentpolicy. agenthalt's own surface is the **halt
store** (the authoritative kill state, read by a dual choke), the **lineage registry** (so containment is
provable), and the **receipt** (so the stop can be verified). The halt signal is published as an agentwatch
event — that is the entire standard surface.

**Status:** Draft — v0.1.0 (2026-11-14) · **Owner:** @deghosal-2026 · **Parent:** agentic-suite #209 · PRD #216

## Where agenthalt sits

agenthalt is the ecosystem's **hand that throws the breakers** and is deliberately thin: it composes, it never
becomes a layer. It is the emergency edge of the same control plane agentpolicy and agentgate live on.

```
   triggers (who/what raises a halt)          agenthalt (control plane)              layers it composes
 ┌────────────────────────────────┐   ┌───────────────────────────────────┐   ┌────────────────────────────┐
 │ CLI  `agenthalt halt …`        │   │  halt store  (authoritative kill) │   │ agentkeys    (revoke creds) │
 │ alert webhook / SIEM           │──►│  lineage registry (parent→child)  │──►│ agentgate    (disconnect)   │
 │ PagerDuty button / Slack action│   │  executor adapters (per layer)    │   │ agentseatbelt(macOS freeze) │
 │ keyboard panic key             │   │  evidence collector (hash chain)  │   │ agentkernel  (eBPF kill)    │
 │ dead-man switch:               │◄──│  receipt builder + verifier       │   │ harness hooks (if any)      │
 │   agentpolicy budget exhausted │   │  drill runner · trigger adapters  │   └────────────────────────────┘
 │   tamper detected · kernel kill│   └────────────┬───────────────┬──────┘
 └────────────────────────────────┘                │ reads         │ emits
                                                   ▼               ▼
                                 runtime + gateway (dual choke)   agentwatch (halt event + evidence snapshot)
```

- **Triggers** raise a halt with a scope and a reason; they never execute it themselves.
- **The halt store** is the single source of stop truth; the **runtime** and the **gateway** both read it before
  an action executes (the **dual choke**).
- **Executor adapters** do the cutting; agenthalt tracks **confirmations**, not requests.
- **Evidence** is an agentwatch record + a hash-chained snapshot; **asks** for a halt from a human route through
  agentinbox (P2).

## Components (v0.1.0)

1. **Halt coordinator (`haltd`)** — receives halt requests, resolves the target to a **subtree** via the lineage
   registry, writes the halt state, fans out to executor adapters, waits for confirmations within a deadline,
   and builds the receipt. Idempotent: re-raising the same halt is a no-op that returns the existing receipt.
2. **Halt store** — the authoritative kill state. Scopes: `session`, `agent`, `run`, `subtree`, `tenant`,
   `global`, and the soft scopes `tool:<name>` and `writes-disabled`. Fail-closed: unreachable store → the dual
   choke denies high-impact actions. Any cache in front of it has a short TTL (seconds), never minutes.
3. **Lineage registry** — records a **parent→child run ID** edge on every spawn (via the runtime adapter or a
   hook where one exists). Subtree resolution walks these edges; **no edge, no containment**.
4. **Executor adapters** — one per layer: `process-tree` (process group / cgroup suspend then kill),
   `credentials` (agentkeys revoke, incl. already-issued grants), `gateway` (agentgate session termination),
   `sandbox` (agentseatbelt/agentkernel freeze + egress block), `hooks` (harness Stop/PreToolUse where
   available). Each reports `confirmed` / `requested` / `unsupported` per target.
5. **Evidence collector** — on halt, snapshots the scene: the agentwatch trace window, the process tree
   (lineage), and open network connections; writes them as a **hash-chained, timestamped** artifact with an
   agentwatch reference. Never destroys the pod's own record by deleting it first.
6. **Receipt builder + verifier** — produces the **proof-of-stop** artifact (lineage edges, per-descendant stop
   confirmations, revoke confirmations, refused-call log) and an **offline verifier** so a third party can check
   it without installing agenthalt.
7. **Trigger adapters** — CLI, alert webhook, PagerDuty button, Slack action, keyboard **panic key**, and the
   **dead-man switches** (agentpolicy budget exhaustion, tamper detection, agentkernel kill triggers).
8. **Drill runner** — one command to rehearse the full stop flow against a live deployment, measuring the SLO;
   the same runner is the **CI chaos drill**.
9. **Halt journal** — append-only, tamper-evident log of every halt: actor, scope, reason, timestamp, affected
   run IDs, mode, and revoke status.
10. **Delivery surfaces** — Python library (`halt(...)`), CLI (`agenthalt halt/pause/resume/kill/status/prove/
    drill`), MCP server (`halt`/`status`), and an HTTP endpoint + webhook receiver.

## The halt pipeline

| Stage | What happens | Owned by |
|---|---|---|
| **Raise** | A trigger submits `{target, mode, reason, actor}`; the halt is authorized (RBAC, P2). | agenthalt |
| **Resolve** | Target → subtree: walk the lineage registry to enumerate descendants and their grants. | agenthalt (lineage) |
| **Record** | Write the kill state to the halt store at the resolved scope, **before** any layer acts. | agenthalt |
| **Fan out** | Executor adapters cut: block new actions (runtime + gateway), suspend/kill the process tree, revoke credentials, freeze the sandbox. | agentgate/agentkeys/agentseatbelt/agentkernel |
| **Confirm** | Each adapter reports per-target `confirmed`/`requested`/`unsupported`; agenthalt retries within the deadline and **never claims success on a request**. | agenthalt |
| **Snapshot** | Collect the trace window, process tree, open connections; hash-chain and timestamp. | agentwatch + agenthalt |
| **Emit** | Publish the halt + trigger as a **first-class agentwatch event**. | agentwatch schema |
| **Receipt** | Build proof-of-stop + the **09:01 readout** (survivors, live grants, queued work, downstream agents). | agenthalt |

Order matters: **block new actions for the whole subtree first, then propagate cancellation and revoke grants.**
Do not wait for cooperative draining before enforcing the block.

## The halt contract

One logical operation, several bindings (library / CLI / MCP / HTTP):

- **Input:** `{ target (session|agent|run|subtree|all), mode (pause|quarantine|kill), reason, actor, deadline? }`.
- **Output:** `{ halt_id, scope, mode, layers_attempted[], confirmations[{layer,target,status}], survivors[],
  evidence_ref, receipt_ref, readout }`.
- **Modes:** `pause` (freeze, resumable) · `quarantine` (freeze + cut network) · `kill` (terminate + revoke).
  v0.1.0 ships `kill`; `pause`/`quarantine` are [PRD 05](05-features.md) P1 (R15).

## Dual choke and fail-closed by construction

- **Dual choke:** the halt state is read in the **runtime** (before the agent acts) *and* in the **tool gateway**
  (before the call leaves). One check the model can talk past is a suggestion.
- **Fail closed:** halt store unreachable → high-impact actions are **denied**, never allowed. Adapter failure →
  agenthalt escalates to a stronger mode (pause → quarantine → kill) and reports the partial state honestly.
- **No false success:** if any descendant is unconfirmed, the receipt says so and the readout lists it. A halt
  that cannot prove containment reports `incomplete`, never `done`.

## Standards

- **agentwatch security-event schema** — the halt and its trigger are first-class events any SIEM can alarm on.
- **Hash-chained, timestamped evidence format** — usable in incident response and legal contexts.
- **No new protocol** — composition of existing layers only.
- **Aligned with the regulatory capability set** — the AI Kill Switch Act's "stop inference / terminate access /
  suspend / shut down" and the NCSC's "pull the plug" map onto agenthalt's layers; the EU AI Act Art. 14 stop
  button maps onto the panic-key and CLI triggers.

## Extensibility

- **Executor adapters** and **trigger adapters** register via a documented schema + entry points, validated at
  load (`unknown adapter → ConfigError`). A new layer is one adapter + one test.
- **The halt signal** is the only cross-tool interface; no bespoke DSL, no proprietary format.
