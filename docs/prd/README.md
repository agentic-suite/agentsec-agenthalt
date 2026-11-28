# agenthalt — Product Requirements (v0.1.0)

Requirements for **agenthalt** — a composed agent **kill switch**: one command that composes a stop across
every layer the ecosystem owns (process tree, credentials, MCP gateway, sandbox), preserves a hash-chained
**evidence snapshot**, and returns a **proof that the stop happened**. Part of the
[agentic-suite](https://github.com/agentic-suite).

> **Status: v0.1.0 proposed (draft, 2026-11-14).** This PRD set defines the **entire v0.1.0 (Wave 0)** release:
> an out-of-band composed-stop control plane that answers one question — *"stop this agent, everywhere, now,
> and show me it stopped"* — for any harness, including one with **zero hook surface**. It composes the
> ecosystem's existing layers (agentkeys revoke, agentgate disconnect, agentseatbelt/agentkernel freeze,
> agentwatch evidence, agentpolicy triggers) rather than inventing a new protocol, and it **absorbs the
> halt-trigger class of the shipped predecessor `ai-loopguard`** (#58, MIT, 391 tests) into the ecosystem's
> composition layer ([PRD 10](10-feature-parity.md)). The folder mirrors the `agentpolicy` PRD structure.

## Documents

| # | Document | Covers |
|---|---|---|
| 00 | [Press Release / FAQ](00-press-release.md) | Working-backwards PR/FAQ |
| 01 | [Why](01-why.md) | Problem, evidence, the "kill switch that isn't one" gap, absorption of `ai-loopguard`, non-goals |
| 02 | [Architecture](02-architecture.md) | Where it sits, components, the halt pipeline, the halt contract, standards |
| 03 | [Landscape](03-landscape.md) | Commercial + OSS kill-switch tooling (CrowdStrike, JetStream, Okta, Salesforce, Aembit, Zenity, Tigera, Grip; intutic, LongGuard, AgentDFIR, kerneleye…), whitespace |
| 04 | [Users and CUJs](04-users-and-cujs.md) | Personas + critical user journeys (stop, contain, pause, revoke, preserve, prove, drill, dead-man, authorize) |
| 05 | [What (Features)](05-features.md) | v0.1.0 P0 (R1–R14), P1/P2 (R15–R24), the ten killer features, feature catalog (F1–F30), non-requirements, compatibility |
| 06 | [Security Baseline](06-security-baseline.md) | Assets, controls, agenthalt's own attack surface (the adversarial sub-matrix), trigger authentication, disclosure |
| 07 | [Success Metrics](07-success-metrics.md) | Outcome metrics, the release gate, anti-metrics, instrumentation |
| 08 | [Risks](08-risks.md) | Risk register (RK-1..RK-22), hard parts, triggers to revisit, open questions |
| 09 | [Roadmap](09-roadmap.md) | Versions, compatibility by version, migration/deprecation, release cadence, ecosystem dependency |
| 10 | [Feature Parity](10-feature-parity.md) | Every absorbed `ai-loopguard` / BehaviorGuard capability → delivered / delegated / waived; the documented fail-open→fail-closed inversion |
| 11 | [Decisions](11-decisions.md) | Accepted decisions (DD-01..DD-48: design, scope, technical, governance) |
| 12 | [Traceability](12-traceability.md) | Requirements → CUJ → WBS → test → parity; reverse CUJ map; decisions → requirements |
| 13 | [Non-Functional Requirements](13-non-functional-requirements.md) | Speed (≤1 s), determinism, fail-closed safety, portability, security, auditability, cost, observability |
| 14 | [Non-Goals](14-non-goals.md) | Consolidated non-goals with owners; what agenthalt is *not* claiming |
| 15 | [Data Model & Lifecycle](15-data-model.md) | Entities (Trigger→Receipt→Snapshot→Journal), examples, lifecycle, storage layout, invariants |
| 16 | [Trigger Catalogue](16-trigger-catalogue.md) | The five launch triggers, the dead-man switches (the absorbed `ai-loopguard` class), trigger governance |
| 17 | [Evidence & Proof Format](17-evidence-and-proof-format.md) | The snapshot format, the receipt, offline verification, the no-over-claiming rules |
| 18 | [Stop Modes](18-stop-modes.md) | pause → quarantine → kill: semantics, escalation, TTLs, the regulatory ladder mapping |
| 19 | [Harness Compatibility](19-harness-compatibility.md) | Containment-below-harness, the Tier-1/2/3 + platform tables, verification & governance |
| 20 | [Standards, Claims & Interop](20-standards-and-claims.md) | Event/evidence standards, regulatory alignment (H.R. 9917, NCSC, EU AI Act), OWASP ASI coverage, the certification ladder, the claims vocabulary |
| 21 | [Evidence Register & Method](21-evidence-register-and-method.md) | Preserved research: evidence register (E1–E22), gap analysis, PRD tensions, method, falsification |
| 22 | [Demo Scenarios](22-demo-scenarios.md) | The five canonical demos (Replit stop, hostile harness, identity problem, dead-man, panic key) — scripts, receipts, failure conditions |
| 23 | [Persona Objections & Adoption](23-persona-objections-and-adoption.md) | Objection→answer per persona (P1–P5), adoption paths, churn triggers, objections we refuse to "fix" |
| 24 | [Pricing & Packaging Thesis](24-pricing-and-packaging-thesis.md) | Product law: what is never paywalled; packaging by persona; the possible commercial surface (around the stop, never inside it) |
| 25 | [Test Strategy](25-test-strategy.md) | The five-level pyramid (unit→adapter→integration→drill→self-halt), golden fixtures, failure-injection matrix, platform/harness matrices, CI gates |
| 26 | [Receipt Schema & Examples](26-receipt-schema-and-examples.md) | Normative `agenthalt.receipt.v1` schema, status vocabulary, four worked receipts, append-only compatibility rules |
| 27 | [Lineage Model](27-lineage-model.md) | What counts as a descendant, edge sources & priority, conflict/orphan handling, the post-halt spawn rule, guarantees vs best-effort |
| 28 | [Failure-Mode Runbook](28-failure-mode-runbook.md) | The operator's survival doc: symptom→action per failure, manual per-layer fallbacks, escalation tree, post-incident checklist |
| 29 | [Regulatory Crosswalk](29-regulatory-crosswalk.md) | Clause→capability→artifact mappings for H.R. 9917, NCSC, EU AI Act Art. 12/14, CA EO, ISO 42001, NIST AI RMF; allowed vs forbidden claims |
| 30 | [Threat Model](30-threat-model.md) | Trust boundaries, five threat actors, STRIDE matrix, ranked attack paths, mitigation→test mapping, residual risks |
| 31 | [Claims Ledger](31-claims-ledger.md) | **Canonical** machine-checkable claim registry (C-01..C-12), forbidden list (F-01..F-08), linter rules, miss-handling SLA |
| 32 | [Build vs Integrate](32-build-vs-integrate.md) | The six owned components, the integrated surfaces per layer, what we never build, boundary-blur guardrails |
| 33 | [Competitive Battlecard](33-competitive-battlecard.md) | Per-competitor cards (CrowdStrike, Okta, Zenity, Tigera, Aembit/Grip, Salesforce/JetStream, OSS breakers) with their own words, wins/losses, closes-by |
| 34 | [Design-Partner Evaluation Guide](34-design-partner-evaluation-guide.md) | The one-week eval kit: day-by-day plan, ten questions, evidence to demand, miss reporting, blocker-vs-feature classification |
| 35 | [Drill Pack Catalogue & Format](35-drill-pack-catalogue.md) | Pack format, verdict vocabulary, the 12 named launch cases each mapped to R/CUJ/claims, partner-authored case flow |
| 36 | [Observability & SOC Pack](36-observability-and-soc-pack.md) | Metrics registry, SLOs + error budget policy, the shipped SIEM alert rules and dashboards, event→SIEM field mapping |
| 37 | [CLI & Output UX Spec](37-cli-and-output-ux-spec.md) | Command surface, the stable exit-code contract, output modes, kill-requires-reason / fleet-confirmation patterns, accessibility rules |
| 38 | [Evidence Privacy & Data-Handling Policy](38-evidence-privacy-and-data-handling.md) | Data inventory, redaction pipeline + canary, access control, retention vs chain, export notices, DSAR tooling, GDPR mapping |
| 39 | [Performance Budget](39-performance-budget.md) | The 1000 ms decomposition: phase budgets, what the clock measures, reference hardware, measurement discipline, breach policy |
| 40 | [Support, Versioning & Deprecation Policy](40-support-versioning-and-deprecation.md) | Dated platform matrix, stability tiers (Tier-0 immutable receipts/exit codes), semver rules, deprecation process, upgrade path, support windows |

## Reviewers start here

1. **Scope:** does [PRD 05](05-features.md) define the right v0.1.0 (composed stop, lineage containment,
   evidence, proof-of-stop, the 09:01 readout, zero-hook-surface containment, ≤1 s CI drill)?
2. **Journeys:** is [PRD 04](04-users-and-cujs.md) CUJ-1..CUJ-25 the right set?
3. **Composition:** is agenthalt the **hand that throws the breakers** in [PRD 02](02-architecture.md) correctly
   drawn — it composes agentkeys/agentgate/agentseatbelt/agentkernel/agentwatch and owns no layer itself?
4. **Honesty:** does the set keep the two hard promises the category fudges — **no new protocol** and **no
   undo** — and does it say plainly what a stop cannot reach ([PRD 14](14-non-goals.md),
   [PRD 17](17-evidence-and-proof-format.md))?
5. **Wedge:** is the composed-stop + proof-of-stop + evidence + lineage + drills set the right differentiator
   against single-layer commercial switches ([PRD 03](03-landscape.md))? Are the whitespace rows (#18–#20, #25)
   real?
6. **Parity:** every `ai-loopguard` halt-trigger capability is delivered / delegated / waived in
   [PRD 10](10-feature-parity.md), with the one semantic inversion documented.
7. **Grounding:** are the open tensions in [PRD 21](21-evidence-register-and-method.md) the right ones to leave
   open, and are the falsifiers honest?
8. **Operability:** does the runbook ([PRD 28](28-failure-mode-runbook.md)) hold up without us on the call —
   and does the eval guide ([PRD 34](34-design-partner-evaluation-guide.md)) let a partner genuinely fail us?
9. **Honesty machinery:** do the threat model ([PRD 30](30-threat-model.md)), claims ledger
   ([PRD 31](31-claims-ledger.md)), and crosswalk ([PRD 29](29-regulatory-crosswalk.md)) close every over-claim
   the category tempts us into?
10. **Operational contracts:** does the 1000 ms decomposition ([PRD 39](39-performance-budget.md)) match what
    the drill measures, do the exit codes ([PRD 37](37-cli-and-output-ux-spec.md)) mean what runbooks will
    assume, and does the drill catalogue ([PRD 35](35-drill-pack-catalogue.md)) actually gate the release gate
    ([PRD 07](07-success-metrics.md))?
11. **Longevity:** are the Tier-0 immutability promises ([PRD 40](40-support-versioning-and-deprecation.md)) and
    the redaction/retention defaults ([PRD 38](38-evidence-privacy-and-data-handling.md)) ones we can keep for
    years — receipts verify forever, or the product's core claim fails?

## Sources

- Ecosystem PRD 07 (agenthalt, #216) — requirements R1–R12, harness-compatibility mandate, non-goals, standards,
  success metrics.
- Ecosystem master note #209 and the release roadmap — Wave 0 meta-MVP, dependency graph (`agenthalt ◄──
  agentkeys + enforcers + watch`), "0 = stop it".
- Predecessor **`ai-loopguard`** (#58, shipped, MIT): its failure-detection + escalation/halt-trigger class,
  absorbed into the composition layer ([PRD 10](10-feature-parity.md)).
- The 2026 kill-switch wave, read as engineering requirements: **H.R. 9917** (AI Kill Switch Act), **UK NCSC**
  interim agentic-AI advice, **EU AI Act** Art. 14, **California EO N-9-26**; and the vendor/practitioner
  corpus — CrowdStrike Falcon Guardian, JetStream, Okta Agent Gateway, Salesforce Agent Fabric, Aembit, Zenity,
  Tigera Lynx, Grip, Clype — cited inline in [PRD 01](01-why.md), [PRD 03](03-landscape.md), and
  [PRD 21](21-evidence-register-and-method.md).
- The `agentpolicy` PRD set (#211) — the house PRD style, the shared personas, and the composition targets
  (agentpolicy's budgets/tamper triggers fire agenthalt's dead-man switches).
