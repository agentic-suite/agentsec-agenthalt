# PRD 24 — Pricing & Packaging Thesis

**BLUF:** agenthalt is **OSS-first and always will be**: the composed stop, the receipt, the evidence format,
and the drill are **free forever, Apache-2.0, no feature gates** — a kill switch that only paying customers can
pull is a security defect dressed as a business model. The commercial surface (if/when one exists) is
**around** the stop, never **inside** it: fleet coordination, hosted control planes, integrations, support,
and attestation at org scale. The ecosystem's anti-paywall rules are restated here as product law.

**Status:** Draft — v0.1.0 (2026-11-14) · **Owner:** @deghosal-2026 · **Parent:** agentic-suite #209 · PRD #216

## The principle (product law)

From the ecosystem's shared anti-requirements: **no paywalled enforcement, no proprietary formats, no ML in
enforcement paths.** For agenthalt this means concretely:

| Capability | Gating |
|---|---|
| `halt` / `pause` / `resume` / `kill` — all modes, all scopes | **Never paywalled** |
| The halt store + dual choke + fail-closed behavior | **Never paywalled** — safety cannot be a tier |
| Receipt generation + offline verification (`prove`) | **Never paywalled** — proof you can't audit is not proof |
| The evidence format (hash-chained, documented) | **Open forever** — append-only schema, no format churn to force upgrades |
| The drill (`agenthalt drill`) + self-halt pack | **Never paywalled** — an untested switch is a liability we won't sell |
| All five launch triggers + dead-man switches | **Never paywalled** |

A paid tier that withheld any row of this table would make every fleet running the free tier *less*
stoppable — the exact opposite of the product. Not negotiable (same rule as agentpolicy).

## Packaging by persona

| Persona | Package | Why |
|---|---|---|
| **P4 Sam** (solo) | `pip install agentsec-agenthalt` — CLI + panic key + local store; full capability, zero account | Distribution engine; his halt works the same day without a team |
| **P1 Maya** (platform lead) | OSS + ecosystem meta-installer (Wave 0): agenthalt wired behind the installed layers, monitor-first | Bottom-up adoption; she demos Demo 1 in her first 30 minutes ([PRD 22](22-demo-scenarios.md)) |
| **P2 Ravi** (SecOps) | OSS + the trigger integrations (webhook/PagerDuty/Slack) + SIEM alarm on `halt.*` events | He blocks tools he can't audit — the receipt is what unblocks adoption |
| **P3 Dana** (GRC) | OSS evidence + (later, enterprise) **attestation-as-a-service**: R24 external drill attestation, org-scale evidence retention, compliance mappings at fleet level | Evidence *generation* is free; evidence *custody and attestation at scale* is the enterprise convenience |
| **P5 Alex** (embedder) | Apache-2.0 library/MCP/HTTP surfaces; no CLA friction beyond DCO; adapter schema is public | His product gets "security-review-ready in a day" without adopting our stack |

## The possible commercial surface (v2.x thesis, not a commitment)

Only **around** the stop — coordination and assurance, never the stop itself:

1. **Fleet coordination plane** — distributed halt stores, cross-tenant authorization, fleet dual-control
   (R18's enterprise form), org-wide runbooks. (The R31-style sync problem in agentpolicy's terms.)
2. **Attestation & evidence custody** — R24 external attestation, long-horizon evidence retention, auditor
   portals on top of the open format (the agentcomply pattern: open evidence, mapped controls at scale).
3. **Support & indemnified deployment** — hardened manifests, CIS-style benchmarks, SLAs: the standard OSS
   security-vendor ladder ([PRD 20](20-standards-and-claims.md) §E).
4. **Never:** a faster stop, a deeper containment, a "pro" choke, or receipt fields the free tier hides.

## Why this maximizes (not minimizes) commercial value

- **The trust asymmetry:** a kill switch's buyer is buying *proof and honesty*. Paywalling the proof
  (receipts/verification) destroys the product's core claim; open proof and paid *custody* of proof is how the
  trust-products (Sigstore, OPA, Falco ecosystems) monetize without breaking themselves.
- **The wedge is the standard:** the open receipt format + the drill are the category-defining surface; if they
  win, the coordination plane around them is the natural enterprise product — the same shape as every CNCF
  success story.
- **Bottom-up compounding:** Sam's panic key and Maya's demo both run on the identical artifact the enterprise
  tier orchestrates. No "community edition" fork ever exists to outgrow.

## Non-goals (pricing-shaped)

- No per-halt, per-seat-metered **stopping**. (Metering *coordinator SaaS*, fine; metering halts, never.)
- No "evidence export" fee — evidence export is a right, not a tier (R21 offline bundles are free).
- No proprietary format migrations — the schemas are append-only and documented forever
  ([PRD 26](26-receipt-schema-and-examples.md)).
- No CLA/DCO asymmetry that would let the project relicense away from Apache-2.0 (org governance floor).

## Open questions

- **Attestation economics** — is R24 attestation a service (we run the pack against partner deployments) or a
  self-serve artifact partners sign? (Design-partner input; [PRD 34](34-design-partner-evaluation-guide.md).)
- **Meta-installer positioning** — does Wave 0's one-install ship agenthalt armed-but-silent by default
  (monitor-only), or drill-first? Hypothesis: monitor-only + a first-run drill nudge (matches the ecosystem's
  default posture).
