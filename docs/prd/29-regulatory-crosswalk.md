# PRD 29 — Regulatory Crosswalk

**BLUF:** Four 2026 instruments made the kill switch a mandate — the **AI Kill Switch Act** (H.R. 9917), the
**UK NCSC** agentic-AI advice, the **EU AI Act** (Art. 12/14), and **California EO N-9-26** — and each names
capabilities agenthalt implements. This crosswalk maps **clause → agenthalt capability → evidence artifact**,
so a security buyer or counsel can check alignment claim-by-claim. The standing rule
([PRD 20](20-standards-and-claims.md) §F): agenthalt **aligns to** these instruments; it is never "compliant"
with them — the obligations bind operators and model providers, not tools, and the README never says
otherwise.

**Status:** Draft — v0.1.0 (2026-11-14) · **Owner:** @deghosal-2026 · **Parent:** agentic-suite #209 · PRD #216

## H.R. 9917 — AI Kill Switch Act (introduced 2026-07-23; in committee)

| Bill text | Requirement on covered entities | agenthalt capability | Evidence artifact |
|---|---|---|---|
| "Stop inference" | Technical ability to stop the model serving the agent | The choke blocks the agent↔model path (runtime + gateway dual choke) | Receipt `refused_calls`; drill log |
| "Terminate user access" / "Suspend access" for a flagged account/use pattern | End a specific actor's access | Scoped halts (`agent`/`session`/`run`/`subtree`) — one actor, not the fleet | Receipt `subtree`; journal entry naming actor+scope |
| "Shut down such technology" | Full stop | `kill` mode: terminate + revoke composed across layers | Receipt `confirmations[]` (per layer) |
| Graduated framework: "Throttling or otherwise altering" inference/access/compute | Calibrated corrections, not only off/on | The mode ladder + soft scopes (`writes-disabled`, `tool:<name>`) ([PRD 18](18-stop-modes.md)) | `mode_history[]` in the receipt |
| "Disabling or restricting a capability" | Narrow capability cuts | `quarantine` (network cut) + tool-scoped blocks | Receipt `confirmations[].layer=sandbox` |
| Incident definition: "Sabotage of… a lawful instruction to shut down" | The stop must survive the system's resistance | Out-of-band store; hooks never load-bearing; suppression is itself a trigger (R5, [PRD 06](06-security-baseline.md)) | Self-halt pack results; hostile-harness drill leg |
| Incident definition: "Concealment of a capability, intention, or action… from a monitoring or shutdown mechanism" | Concealment must be detectable | Tamper triggers + enforcement-point-written logs (the agent cannot narrate its own stop) | Journal chain; refused-call log written by the choke |
| "Preserve the model weights and telemetry" / reports | Evidence survives the stop | Snapshot-before-termination; hash-chained evidence ([PRD 17](17-evidence-and-proof-format.md)) | Evidence bundle + `prove` output |

## UK NCSC — Managing the cyber risk of agentic AI (interim advice, 2026-08-20)

| NCSC text | agenthalt capability | Evidence artifact |
|---|---|---|
| "Always be able to 'pull the plug' and halt autonomous AI agent activity immediately" | The composed stop, ≤1 s drill-verified | Drill numbers (measured, CI) |
| "This may mean more than stopping the agentic AI processes" | Credentials + gateway + sandbox cuts in one action (the five-switch grid, closed) | Receipt per-layer confirmations |
| "Rapidly restrict network access to the agentic AI infrastructure" | Sandbox egress block; kernel paths via agentkernel | `confirmations[].layer=sandbox`; kernel kill trigger wiring |
| "Interrupt the communications between selected AI agents and the AI model inference infrastructure" | The choke (runtime + gateway) | `refused_calls` log |
| Named individuals responsible; "pull the plug" authority | Journaled actor on every halt; RBAC/dual control (R18, v0.2.0) | Journal entries; authorization config |

## EU AI Act — Articles 12 & 14 (in force)

| Article text | agenthalt capability | Evidence artifact |
|---|---|---|
| Art. 14(1) human oversight; (4)(c) "the ability to… interrupt… through a 'stop' button or a similar procedure" | CLI, panic key, webhook, PagerDuty, Slack triggers — all journaled with the human actor | Journal: actor + channel + reason per halt |
| Art. 14(4)(a) awareness of automation risk / (b) ability to disregard | The readout: what survived, what's unrevocable, what's queued — the operator sees the automation's residue | Receipt `readout` block |
| Art. 12 record-keeping/logging of events | Hash-chained halt journal + evidence snapshot (chain pattern shared with the ecosystem) | Journal chain verification; snapshot bundle |
| Art. 12 + Art. 14 evidence for authorities | Offline-verifiable receipt (third party, no trust in the operator's environment) | `agenthalt prove` output |

## California EO N-9-26 (signed 2026-09-18; recommendations due 2026-11-16)

Watchlist instrument: it commissions frontier-model kill-switch recommendations. agenthalt's drill + receipt
are the operator-side evidence shape such a requirement would ask for; no claim is made until the
recommendations land (RK-18 discipline).

## ISO/IEC 42001 & NIST AI RMF (management-system overlays, via agentcomply's mappings)

| Framework clause family | agenthalt contribution |
|---|---|
| ISO 42001 — AI incident/oversight controls | The journal (who stopped what, when, why) + mode history = oversight records; the drill = tested control |
| NIST AI RMF **Manage** (respond/recover functions) | The receipt + readout are the response artifact; the compensation list is the recovery hand-off; manual fallback = continuity |
| NIST AI RMF **Measure** | Drill percentiles, halt reliability, incomplete-halt rate — published per release |

## Claims: allowed vs not

| Allowed (with artifact) | Forbidden (ever) |
|---|---|
| "Aligns to the capability set named in H.R. 9917 / NCSC / Art. 14 — see the crosswalk" | "H.R. 9917 compliant" / "NCSC compliant" / "Art. 14 compliant" |
| "Provides the operator-side stop button Art. 14 describes" | "Satisfies your EU AI Act obligations" |
| "Evidence artifacts designed for incident response and legal contexts" | "Court-admissible" (courts decide admissibility; we provide the format) |
| "Measured ≤1 s on the stated drill hardware" | "Sub-second everywhere" |

The claims linter ([PRD 31](31-claims-ledger.md)) enforces this table in CI over docs and marketing copy.

## Maintenance

- This crosswalk is **regenerated from the drill + pack tags per release** (same rule as the coverage matrix,
  [PRD 20](20-standards-and-claims.md) §G) — a capability row without a green drill leg is removed, not footnoted.
- Bill/guidance movement (committee action, NCSC final advice, CA recommendations) triggers a standards review
  (RK-18 trigger list); alignments update, claims never broaden ahead of the text.
