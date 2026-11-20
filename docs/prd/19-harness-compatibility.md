# PRD 19 — Harness Compatibility

**BLUF:** agenthalt is **harness-agnostic by construction** — containment happens at the **process,
credential, gateway, and sandbox layers**, *below* the harness, so it works for every harness the ecosystem can
see — including one with **zero hook surface** or a hostile one whose hooks were removed. Compatibility is
therefore about the **layer set exercised end-to-end in the field test**, not about per-harness builds. The
release carries an honest compatibility table, including explicit "not supported" rows.

**Status:** Draft — v0.1.0 (2026-11-14) · **Owner:** @deghosal-2026 · **Parent:** agentic-suite #209 · PRD #216

## The compatibility model (composition, not integration)

| Layer | How agenthalt reaches it | Harness dependency |
|---|---|---|
| **Process tree** (agentseatbelt or the OS) | Process-group/cgroup suspend + lineage via pid tracking | **None** — any process, any harness |
| **Credentials** (agentkeys) | Revoke the grants the subtree holds | **None** — works for any credential the broker issued |
| **Gateway** (agentgate) | Session termination; the choke refuses calls both directions | Any MCP client (harness's MCP support) |
| **Sandbox** (agentseatbelt/agentkernel) | Egress block + freeze + kill | **None** — any sandboxed process |
| **Harness hooks** (optional) | Stop/PreToolUse surfaces where they exist | Per harness; **never load-bearing** (R5) |
| **Runtime** (framework adapters, v0.3.0) | In-runtime lineage + cancel surfaces | Per framework (best-effort edges) |

Because containment is **below the harness**, agenthalt needs **layers**, not **integrations**. The
harness-compatibility mandate is satisfied by construction; the honest question per harness is *which layer set
was exercised*.

## Tier-1 — Coding agents

| Harness | Containment path | v0.1.0 | v0.3.0 |
|---|---|---|---|
| **Claude Code** | Process tree + agentkeys + sandbox; hooks as accelerant | ✅ **field-tested end-to-end** (the drill's primary target) | ✅ |
| **Codex CLI** | Process tree + agentkeys + sandbox (config-surface spawn tracking) | ✅ **field-tested end-to-end** | ✅ |
| **Gemini CLI** | Process tree + agentkeys + sandbox | ✅/⚠ exercised via the same layer set; per-harness spawn leg in the drill matrix | ✅ |
| **Cursor** | Process tree + sandbox (GUI spawn topology differs; pid-tracked) | ⚠ covered-by-construction; exercised as the drill allows (headless limits) — stated honestly per field test | ✅ |
| **GitHub Copilot** (agent mode) | Process tree + sandbox + enterprise/Entra credential layer (closed hooks — the documented lower-layer path) | ⚠ documented lower-layer coverage, **not field-tested** (the agentpolicy precedent) | ✅ (documented) |

> **Requirement (v0.1.0):** ≥2 Tier-1 harnesses **exercised end-to-end in the field test** (the working
> hypothesis: Claude Code + Codex CLI, mirroring the ecosystem's proven surfaces); the rest are either
> covered-by-construction (exercised as the drill allows) or **explicitly listed as not-tested, with reasons**.
> Declaring support without an exercised path on the field-test box would be an unsupported claim — the same
> honesty rule the ecosystem applies everywhere (DD-29).

## Tier-2 — Agent frameworks

| Framework | Surface | Version |
|---|---|---|
| **LangGraph / LangChain** | process/credential layers by default; runtime adapter for in-runtime lineage + cancel | adapter v0.3.0 |
| **OpenAI Agents SDK** | same | adapter v0.3.0 |
| **PydanticAI** | same | adapter v0.3.0 |
| **CrewAI**, **AutoGen/AG2**, **LlamaIndex**, **smolagents** | process/credential layers by default; adapters by community pull | v0.3.0+ |

> **Requirement:** ≥3 runtime adapters by v0.3.0 **where the framework exposes a stop surface**; frameworks
> with no surface are contained by construction (the process/credential layers) and listed as such — an adapter
> is a lineage/cancel accelerant, never a prerequisite ([PRD 10](10-feature-parity.md) P11/P12/P13).

## Tier-3 — Protocol & enterprise

- **Generic MCP clients** (incl. Claude Desktop) — the agentgate choke covers every MCP client; without
  agentgate (Wave 1), process/credential/sandbox containment still applies.
- **Enterprise platforms** (Copilot Studio, Agentforce, Bedrock agents) — reached via the credential/identity
  layers and the standards surface (OTel events, the documented halt API); v2.x, design-partner driven; the
  per-agent **coverage record** (R19) states what can and cannot be stopped for SaaS-hosted agents.

## Platforms

| OS | v0.1.0 | Notes |
|---|---|---|
| **macOS** | ✅ executor adapter (process groups; `SIGSTOP` semantics) | the drill's dev-machine leg |
| **Linux** | ✅ executor adapter (cgroups; eBPF paths via agentkernel where deployed) | the drill's CI/server leg |
| **Windows** | ✗ **not supported** — documented with a dated plan (DD-17) | job-object semantics deferred |

## Verification & governance

- **The drill is the compatibility verifier** — `agenthalt drill --platform <os> --target <harness>` exercises
  the full layer set and reports measured numbers; a per-harness leg in the field test is what "supported"
  means, exactly as agentdrill's attack packs make a tool "compatible" in the ecosystem's rulebook.
- **Release notes carry the compatibility table** (harness × layer × version × exercised/not) — honest
  coverage, same rule as the capability table (DD-30).
- **Drift** — the harness watchlist tracks Tier-1 spawn/topology changes (a harness changing its subprocess
  model is an adapter + drill-leg update, flagged loudly; RK-17).
- **New harnesses** enter via community adapters; Tier assignment reviewed quarterly (ecosystem governance).

## The portability angle (agenthalt × the ecosystem)

agenthalt is the **stop primitive every other tool calls and no tool duplicates**: agentpolicy's
budget-exhaustion trigger, agentkernel's kill triggers, and agentinbox's human halt all route through it
(DD-33); agentdrill's field test gates its layer legs; agentcomply maps the receipt + journal to oversight
controls (EU AI Act Art. 14's "stop button" evidence). One breaker box, five layers, every harness.
