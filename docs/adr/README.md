# agenthalt — Architecture Decision Records

ADRs record the **load-bearing decisions** and their rationale. Status: `proposed` → `accepted` → (rarely)
`superseded`. Superseding an ADR requires a new ADR that names it — decisions are never silently reversed.

| # | Decision | Status |
|---|---|---|
| [0001](0001-out-of-band-halt-store.md) | The halt state lives outside the model's control plane (out-of-band by construction) | accepted |
| [0002](0002-dual-choke-enforcement.md) | Dual-choke enforcement: the runtime and the gateway both read the halt state | accepted |
| [0003](0003-confirmations-not-requests.md) | Receipt semantics: confirmations, never requests; `incomplete` is a first-class status | accepted |
| [0004](0004-fail-closed-over-fail-open.md) | Fail-closed over fail-open — the deliberate inversion of `ai-loopguard` | accepted |
| [0005](0005-hooks-never-load-bearing.md) | Harness hooks are optional and never load-bearing | accepted |
| [0006](0006-snapshot-before-termination.md) | Snapshot-before-termination: evidence is written before the scene is destroyed | accepted |
| [0007](0007-agentwatch-event-no-new-protocol.md) | The halt signal is an agentwatch event; no new protocol | accepted |
| [0008](0008-lineage-process-observation-priority.md) | Lineage edge priority: process observation wins over hooks and runtimes | accepted |
| [0009](0009-enrollment-supervisor.md) | Enrollment: agents enter the lineage through a supervisor (`agenthalt run` / `attach`) | accepted |
| [0010](0010-self-tamper-triggers-v010.md) | Self-tamper triggers ship at v0.1.0; external dead-man switches stay v0.2.0 | accepted |
| [0011](0011-status-precedence-and-attestation.md) | Receipt status precedence and labelled self-attestation | accepted |
| [0012](0012-built-in-egress-fallback.md) | Minimal built-in egress fallback for `quarantine` | accepted |

Each ADR maps to decision records (DD-xx) in [PRD 11](../prd/11-decisions.md); ADRs carry the *why* in depth,
the PRD carries the requirement-side summary. The twelve decisions above are the load-bearing set for v0.1.0 —
the properties the release gate, the drill catalogue ([PRD 35](../prd/35-drill-pack-catalogue.md)), and the
threat model ([PRD 30](../prd/30-threat-model.md)) all assume.
