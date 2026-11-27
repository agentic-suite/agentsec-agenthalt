# PRD 20 — Standards, Claims & Interop

**BLUF:** agenthalt is built **on** the ecosystem's open surfaces (the agentwatch security-event schema, the
hash-chained evidence format) and **aligns to** the regulatory capability sets that made kill switches a 2026
mandate (H.R. 9917, UK NCSC agentic-AI guidance, EU AI Act Art. 14, California EO N-9-26) and the AI-security
frameworks (OWASP ASI/LLM, MITRE ATLAS, NIST AI RMF, ISO/IEC 42001). This document is the **claim surface**: what
agenthalt implements, what it aligns to, what it is certified against — and a **claims vocabulary** that forbids
over-claiming (no "compliance," no "undo," no unmeasured numbers). The coverage matrix is regenerated per
release.

**Status:** Draft — v0.1.0 (2026-11-14) · **Owner:** @deghosal-2026 · **Parent:** agentic-suite #209 · PRD #216

## A. Control-plane & event standards (agenthalt implements these)

| Standard | Status | What agenthalt implements |
|---|---|---|
| **agentwatch security-event schema v1** | Ecosystem standard | The halt + trigger event surface (R6) — halt as a first-class event any SIEM can alarm on; the **entire** cross-tool standard surface (no new protocol, DD-09) |
| **agenthalt receipt format v1** (`agenthalt.receipt.v1`) | This PRD | The open proof-of-stop artifact ([PRD 17](17-evidence-and-proof-format.md)) — offline-verifiable, enforcement-point-signed |
| **agenthalt evidence format v1** (`agenthalt.evidence.v1`) | This PRD | The documented, hash-chained, timestamped forensic snapshot (R3) — the ecosystem's shared chain pattern |
| **OTel GenAI semantic conventions** | Active | Evidence and events ride the ecosystem's OTel-aligned telemetry (via agentwatch) |
| **OCSF** | Mapping via agentwatch | SIEM interop for the halt event stream |

## B. Regulatory capability sets (agenthalt aligns to — alignment is documented, compliance is not claimed)

| Framework | Status | agenthalt alignment |
|---|---|---|
| **AI Kill Switch Act (H.R. 9917)** | Introduced 2026-07-23; in committee | The capability set maps: stop inference (choke), terminate/suspend access (pause/kill), shut down (kill), graduated corrections (the [PRD 18](18-stop-modes.md) ladder); the bill's *incident definition* (shutdown sabotage, concealment from a shutdown mechanism) is the [PRD 06](06-security-baseline.md) threat model |
| **UK NCSC — Managing the cyber risk of agentic AI** | Interim advice, 2026-08-20 | "Always able to pull the plug… may mean more than stopping the processes" = the composed stop (R1); the two named cuts (network around agents, agent↔model path) = sandbox + choke layers |
| **EU AI Act Art. 14** | In force | Human oversight via "a 'stop' button or similar procedure" — the panic key/CLI trigger by an authorized person, journaled with actor; Art. 12 logging = journal + snapshot |
| **California EO N-9-26** | Signed 2026-09-18; recommendations due 2026-11-16 | Watchlist item; the drill + receipt are the evidence a frontier kill-switch requirement would ask for |
| **ISO/IEC 42001** (AI management) | Published | The halt journal + drill results as oversight-control evidence (via agentcomply's mapping) |

## C. AI security frameworks (coverage published per release)

| Framework | Status | agenthalt alignment |
|---|---|---|
| **OWASP Top 10 for Agentic Applications 2026 (ASI)** | Published | **ASI10 (Rogue Agents)** — the stop is the terminal control for runaway autonomy; **ASI02** (Tool Misuse) — the choke blocks further misuse; **ASI05** (Unexpected Code Execution) — sandbox freeze; **ASI09** (Trust) — journaled actor + authorization (R18) |
| **OWASP Top 10 for LLM Applications 2025** | Published | **LLM06** (Excessive Agency) — the graduated stop is the named mitigation family; **LLM02** — redaction in the evidence snapshot |
| **MITRE ATLAS** | Active | Halt-relevant techniques (destructive execution, privilege abuse) are *stopped*, not detected; tags on the drill matrix, not detection claims |
| **NIST AI RMF 1.0 + GenAI Profile** | Published | **Manage** (incident response: the receipt + readout), **Measure** (drill metrics); mapping in the coverage matrix |

## D. Product security & supply chain (agenthalt's *own* posture)

| Standard | Use |
|---|---|
| **NIST SSDF (SP 800-218)** | Secure development for the control plane itself |
| **OWASP ASVS L2** | Target for the daemon/HTTP surfaces |
| **OpenSSF Scorecard / Best Practices badge** | Signed releases, pinned deps — the repo already carries the Scorecard badge |
| **SLSA + Sigstore** | Build provenance + signing on releases **and on the enforcement-point verification keys** the offline verifier consumes ([PRD 17](17-evidence-and-proof-format.md)) |
| **SPDX/CycloneDX SBOM** | Per release |
| **CVE / coordinated disclosure + `security.txt`** | With SLAs and the **manual-fallback runbook** (PRD 06) — a kill-switch vulnerability is disclosed with the operator's path around it |

## E. The certification ladder (ordered by cost/timeline)

| Rung | Target | When | Evidence |
|---|---|---|---|
| **OpenSSF Best Practices badge** | Passing → Silver | v0.1.0 | Badge |
| **SLSA build provenance + Sigstore signing** | L2→L3 | v0.1.0 | Attestations per release |
| **CVE program + `security.txt` + disclosure SLAs** | Live | v0.1.0 | Public URL + fallback runbook |
| **Published OWASP ASI/LLM + regulatory-alignment matrix** | Published | v0.1.0 | Regenerated from pack tags per release |
| **Measured drill numbers** (p50/p95/p99, stated hardware) | Published | v0.1.0 | The CI drill artifact (DD-29) |
| **SOC 2 Type I → Type II** | Audited | v1.x | Audit letter (start the evidence pipeline now — the journal is the evidence) |
| **ISO/IEC 27001 / 42001** | Certified | later | Certificate |

## F. Claims vocabulary (the honesty rule)

> **Canonical source:** the claims ledger ([PRD 31](31-claims-ledger.md)) is the single machine-checked registry.
> This table summarizes it for the standards context; where they differ, PRD 31 wins and this table is corrected.

agenthalt may claim only what it can prove. The following are **forbidden** or **restricted**:

| Claim | Status |
|---|---|
| "Stops any agent, anywhere" | **Forbidden** — it stops what the composed layers reach; the readout states the rest |
| "Undoes / rolls back the agent's actions" | **Forbidden** — there is no undo; compensation lists exist because reversal is impossible |
| "H.R. 9917 compliant / NCSC compliant / Art. 14 compliant" | **Forbidden** — those bind model providers and deployers, not tools; agenthalt **aligns to** the capability sets, documented (RK-18) |
| "Guarantees zero surviving descendants" | **Forbidden** — the receipt says *verified in the drill* (no post-halt call observed), never *guaranteed* |
| "Sub-second stop" | **Allowed only** with the CI drill measurement + hardware published |
| "Composes agentkeys/agentgate/agentseatbelt/agentkernel" | **Allowed** with the compatibility table naming per-layer version + exercised status |
| "Works on zero-hook-surface harnesses" | **Allowed only** with the hostile-harness fixture passing in CI (R5) |
| "Court-usable evidence" | **Allowed** as "documented, hash-chained, timestamped, offline-verifiable format" — the *court* decides admissibility, not the README |

A machine-readable **claims linter** checks published docs/marketing against this vocabulary in CI (the
agentdrill `claims-ledger` pattern; DD-34).

## G. Coverage matrix (published per release, generated from the drill + pack tags)

| Control / drill case | OWASP ASI | OWASP LLM | NIST AI RMF | Regulatory alignment |
|---|---|---|---|---|
| Composed stop (R1) | ASI10, ASI02 | LLM06 | MANAGE (IR) | NCSC "pull the plug"; H.R. 9917 shut-down |
| Lineage containment (R2) | ASI10, ASI03 | LLM06 | MANAGE (IR) | — |
| Evidence snapshot (R3) | — | LLM02 (redaction) | MEASURE | EU AI Act Art. 12 (logging) |
| Trigger set (R4) | ASI09 | — | MANAGE | Art. 14 (human interrupt) |
| Zero-hook-surface containment (R5) | ASI05 | — | MANAGE | H.R. 9917 incident definition (sabotage-proof) |
| Halt events (R6) | — | — | MEASURE | Art. 12 |
| Graduated modes (R15) | ASI10 | LLM06 | MANAGE | H.R. 9917 graduated framework |
| Dead-man switches (R16) | ASI10, ASI02 | LLM06 | MANAGE | — |
| Halt authorization (R18) | ASI09, ASI03 | — | MANAGE | Art. 14 (authorized person) |

> The full per-control mapping regenerates from CI and ships with every release artifact ([PRD 09](09-roadmap.md)).
