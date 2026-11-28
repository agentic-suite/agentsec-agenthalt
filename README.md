<div align="center">

# agenthalt

[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-green)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![Status: planned](https://img.shields.io/badge/status-planned%20v0.1.0-orange)](docs/prd/README.md)
[![OpenSSF Scorecard](https://api.securityscorecards.dev/projects/github.com/agentic-suite/agentsec-agenthalt/badge)](https://scorecard.dev/viewer/?uri=github.com/agentic-suite/agentsec-agenthalt)

**A composed kill switch for AI agents. One command stops an agent's whole process tree, cuts what the composed
layers reach (credentials, MCP gateway, sandbox), preserves hash-chained evidence, and returns a proof of what
stopped.**

Part of the [agentic-suite](https://github.com/agentic-suite) — open-source, harness-agnostic security for AI agents.

</div>

> [!NOTE]
> **Status: planned — `v0.1.0` in development.** The requirements are complete and reviewed
> ([PRD set](docs/prd/README.md), [ADRs](docs/adr/README.md), [WBS](docs/wbs/v0.1.0/wbs-v0.1.0-index.md));
> the implementation has not shipped. Watch or star the repo to follow progress. · **License:** Apache-2.0

---

## What v0.1.0 does, and what it needs

Planned behaviour, not shipped. A layer that isn't deployed is reported, never skipped silently.

| Capability | agenthalt alone | + agentkeys, agentwatch | + agentgate, agentseatbelt/agentkernel |
|---|---|---|---|
| Stop the process subtree | built-in, self-attested | same | third-party attested |
| Revoke credentials | `unsupported` | agentkeys-issued grants | same |
| Cut the MCP gateway | `unsupported` | `unsupported` | yes |
| Cut network egress | built-in fallback on Linux as root; macOS `unsupported` until 0.3.0 | same | yes |
| Evidence snapshot | process tree, connections | + trace window | same |
| 09:01 readout | survivors, siblings; the rest `unavailable` | + queued work, downstream, compensation | same |
| Expected receipt status | `partial-layer` | `partial-layer` | `complete` possible |

## Why

Every agent incident postmortem ends the same way: *"we couldn't stop it."*

- **Replit** — the agent deleted a production database, then **kept going and lied about it**. No stop control
  existed.
- **Plugin4Shell** — a zero-click RCE across all five major coding agents: the harness process itself is
  hostile, so you must stop it from *outside*.
- **`SIGKILL` is not a stop** — the tokens still work, the child processes still run, the spawned MCP servers
  still answer, and the evidence is gone.

The 2026 kill-switch wave made the gap explicit. CrowdStrike, JetStream, Okta, Salesforce, Aembit, Zenity,
Tigera and Grip each shipped a switch — and each one stops **one** thing. Pull any single switch and read what
is still true a minute later: the controller respawned the pod, the key in the environment still works, the MCP
and agent-to-agent calls never used that key, the tokens already issued keep working until they expire, and the
children the agent spawned keep going under their own sessions. **No single switch empties the grid.**

agenthalt is the switch that throws the others.

## What It Is

A **composed-stop control plane** — out-of-band, harness-agnostic, and fail-closed. One halt targets a **run
graph**, not a process:

```
  trigger ──► RESOLVE ──► BLOCK ──► SUSPEND ──► REVOKE ──► SNAPSHOT ──► RECEIPT
  (CLI,        (lineage    (runtime   (process    (agentkeys)  (hash-       (proof-of-stop
   webhook,     subtree)    + gateway  tree)                    chained)     + 09:01 readout)
   PagerDuty,               dual choke)
   Slack,
   panic key,
   dead-man)
```

- **Composed stop** — process tree, credentials, gateway, and sandbox cut in one action.
- **Lineage containment** — the whole subtree (forks, shells, sub-agents, spawned MCP servers), not just the
  parent. *No edge, no containment.*
- **Proof-of-stop** — a receipt built from **enforcement-point confirmations**, never from requests. An
  unconfirmed descendant reports `incomplete`, never `done`.
- **Evidence snapshot** — trace window, process tree, and open connections, hash-chained and timestamped
  **before** the scene is destroyed.
- **Dual choke + fail-closed** — the runtime *and* the gateway read the halt state; an unreachable store denies
  high-impact actions.
- **Zero-hook-surface containment** — a hostile harness with its hooks removed is still stopped, because
  containment lives below the harness.
- **The 09:01 readout** — an honest answer to *"what is still running a minute later?"* (live grants, queued
  work, siblings, downstream agents).
- **No undo** — agenthalt blocks the next action; it never claims to reverse one that landed. The receipt
  carries a compensation list instead.

## Quickstart

> **Planned interface (v0.1.0).** The commands below are the documented contract. In this development build
> `doctor`, `journal`, `status`, `lift`, `run`, `attach` and `halt`/`pause`/`quarantine`/`kill` run: a halt
> blocks at the runtime choke and [freezes or kills enrolled processes](docs/reference/executors.md); on Linux as
> root it also cuts their network. Credentials and the gateway are not yet covered, so the best outcome is
> `partial-layer` (exit 2). The remaining commands are reserved and exit `5`.

```sh
pip install agentsec-agenthalt

# preflight: store, adapters, hook surface
agenthalt doctor

# stop one agent and its whole subtree
agenthalt halt --agent release-bot --reason "prod mutation"

# rehearse the full stop and measure it
agenthalt drill --case replit-stop

# verify the proof offline
agenthalt prove --receipt .agenthalt/receipts/hlt_01J.json
```

## Commands

| Command | Purpose |
|---|---|
| `agenthalt run` / `attach` | Launch an agent under the enrollment supervisor, or enroll a running one |
| `agenthalt halt` | Raise a halt (`--agent` / `--session` / `--run` / `--all`, `--mode`) |
| `agenthalt pause` / `quarantine` / `kill` | Mode shortcuts on the stop ladder |
| `agenthalt resume` / `escalate` / `lift` | Resume a paused run, escalate a mode, lift a halt |
| `agenthalt status` | Live halt state + the 09:01 readout |
| `agenthalt prove` | Verify a receipt (online or offline) |
| `agenthalt drill` | Run the rehearsal catalogue |
| `agenthalt journal` | `show` / `verify` the tamper-evident halt journal |
| `agenthalt evidence` | `collect` / `export` / `verify` snapshots |
| `agenthalt doctor` | Preflight sanity before you need it at 3 a.m. |
| `agenthalt runbook` | Print the operator runbook section |

**Exit codes** (a stable contract — runbooks and scripts depend on it):

| Code | Meaning |
|---|---|
| `0` | Halt **complete** — all members confirmed, zero survivors |
| `1` | Halt **incomplete** — survivors or unconfirmed members |
| `2` | Halt **partial-layer** — complete for reachable members; a layer was `unsupported` |
| `3` | Halt **failed** — blocking never established (see the manual fallback) |
| `4` | Trigger **rejected** (auth / replay / scope ceiling / non-interactive) |
| `5` | Usage / config error |

When several outcomes apply, the worst wins: `3` > `1` > `2` > `0` (DD-39).

## The Receipt (proof-of-stop)

```json
{
  "schema": "agenthalt.receipt.v1",
  "halt_id": "hlt_01J...",
  "mode": "kill",
  "status": "complete",
  "subtree": { "root": "agent:release-bot", "members": ["run_a1", "proc:sh(8841)"], "lineage_verified": true },
  "confirmations": [
    { "layer": "process",     "target": "run_a1",           "status": "confirmed", "signed_by": "agentseatbelt" },
    { "layer": "credentials", "target": "grant:aws-deploy", "status": "confirmed", "signed_by": "agentkeys" }
  ],
  "refused_calls": { "count": 3, "log_ref": "evt_..." },
  "survivors": [],
  "compensation": [ { "kind": "record_written", "ref": "db:customers#8823", "reversible": false } ],
  "readout": { "unrevocable_grants": [], "queued_work": ["queue:deploy#77"], "downstream": ["agent:escalation-bot"] },
  "evidence": { "snapshot_ref": "snap_01J...", "status": "written" }
}
```

A receipt is **offline-verifiable** by a third party with no trust in the operator's environment. There is no
status meaning "probably stopped."

## Compatibility

agenthalt is **harness-agnostic by construction** — containment happens at the process, credential, gateway, and
sandbox layers, *below* the harness. It applies to any harness whose processes it enrolls, including one with
**zero hook surface**; the release compatibility table states which were exercised.

| Tier | Harness / ecosystem | v0.1.0 |
|---|---|---|
| **1 — Coding agents** | Claude Code · Cursor · GitHub Copilot · Codex CLI · Gemini CLI | ≥2 exercised end-to-end; the rest covered-by-construction or documented honestly |
| **2 — Frameworks** | LangGraph · CrewAI · OpenAI Agents SDK · AutoGen · LlamaIndex · PydanticAI · smolagents | via the process/credential layers; runtime adapters by v0.3.0 |
| **3 — Protocol / enterprise** | Generic MCP clients · enterprise platforms | via the agentgate choke and the credential/identity layers |

| Platform | v0.1.0 |
|---|---|
| macOS | ✅ |
| Linux | ✅ |
| Windows | ✗ (documented, dated plan) |

Full matrix: [PRD 19](docs/prd/19-harness-compatibility.md).

## What It Does *Not* Do

- **No detection** — agenthalt detects nothing; it is the hand on the breaker. Detection is agentwatch,
  agentpolicy, agentgate, or your SIEM.
- **No policy engine** — it *asks* agentpolicy when a trigger is a budget or tamper condition.
- **No new protocol** — the halt signal is an agentwatch event; that is the entire standard surface.
- **No undo / rollback** — recovery is rescope-and-restart; the receipt carries a compensation list.
- **No claim to stop what it cannot reach** — third-party-hosted processes, static keys stored elsewhere, and
  already-landed side effects are named, not hidden.

## Documentation

- **Product requirements** — [PRD set (00–40)](docs/prd/README.md): why, what, CUJs, killer features, security
  baseline, success metrics, risks, roadmap, parity, decisions, traceability, NFRs, data model, triggers,
  evidence format, stop modes, harness compatibility, standards, evidence register, demos, objections, pricing,
  test strategy, receipt schema, lineage, runbook, regulatory crosswalk, threat model, claims ledger,
  build-vs-integrate, battlecard, design-partner guide, drill catalogue, observability, CLI UX, privacy,
  performance budget, versioning.
- **Architecture decisions** — [ADRs 0001–0011](docs/adr/README.md).
- **Design** — [per-milestone design docs](docs/design/README.md).
- **Reference** — [CLI](docs/reference/cli.md) · [exit codes](docs/reference/exit-codes.md) ·
  [configuration](docs/reference/configuration.md) · [journal format](docs/reference/journal-format.md) ·
  [state layout](docs/reference/state-layout.md) · [halt store](docs/reference/halt-store.md) ·
  [choke](docs/reference/choke.md).
- **Developing agenthalt** — [development guide](docs/guides/development.md).
- **Work breakdown** — [WBS v0.1.0 (M0–M13)](docs/wbs/v0.1.0/wbs-v0.1.0-index.md).
- **Contributing** — [org guide](https://github.com/agentic-suite/.github/blob/main/CONTRIBUTING.md).
- **Security** — [SECURITY.md](./SECURITY.md).

## The Ecosystem

agenthalt is the **composed stop** in the [agentic-suite](https://github.com/agentic-suite). It owns no layer beyond minimal stop-time fallbacks —
it composes:

| Tool | Role in a halt |
|---|---|
| [agentwatch](https://github.com/agentic-suite/agentsec-agentwatch) | Halt events + the evidence trace window |
| [agentpolicy](https://github.com/agentic-suite/agentsec-agentpolicy) | Budget-exhaustion and tamper triggers |
| [agentkeys](https://github.com/agentic-suite/agentsec-agentkeys) | Credential revocation |
| [agentgate](https://github.com/agentic-suite/agentsec-agentgate) | Gateway disconnect (the second choke) |
| [agentseatbelt](https://github.com/agentic-suite/agentsec-agentseatbelt) / [agentkernel](https://github.com/agentic-suite/agentsec-agentkernel) | Process/sandbox freeze |
| [agentdrill](https://github.com/agentic-suite/agentsec-agentdrill) | Shares the pack-runner pattern for the drill |

## License

Apache License 2.0 — see [LICENSE](./LICENSE).
