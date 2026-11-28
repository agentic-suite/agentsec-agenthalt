# PRD 09 — Roadmap

**BLUF:** **v0.1.0** ships the composed stop — halt store + dual choke + lineage registry + executor adapters,
evidence snapshot, proof-of-stop receipt, the 09:01 readout, the halt journal, the full trigger set, pause/
resume, and the CI chaos drill at **≤ 1 s**. **v0.2.0** adds graduated-mode escalation (escalate-on-act across `pause → quarantine → kill`),
the dead-man switches (the absorbed `ai-loopguard` trigger class), drills-in-a-box for partners, halt
authorization (RBAC + dual control + break-glass), third-party-agent coverage, the blast map, offline evidence
bundles, and halt-from-anywhere (agentinbox). **v0.3.0+** adds fleet halt policies and external attestation —
no deferred proof.

**Status:** Draft — v0.1.0 (2026-11-14) · **Owner:** @deghosal-2026 · **Parent:** agentic-suite #209 · PRD #216

## Versions

| Version | Theme | Scope |
|---|---|---|
| **v0.1.0** (Wave 0) | **The composed stop** | R1–R14: `halt <agent\|session\|all>` across every available layer (process tree, agentkeys revoke, agentgate disconnect, sandbox freeze); lineage containment (zero surviving descendants, verified); hash-chained evidence snapshot; triggers (CLI, alert webhook, PagerDuty, Slack, keyboard panic key); zero-hook-surface containment (the hostile-harness fixture); halt + trigger as agentwatch events; pause/resume (24 h test) + basic quarantine; self-tamper triggers (DD-36); built-in egress fallback (DD-45); enrollment (`agenthalt run` / `attach`, DD-38); halt store + dual choke + fail-closed; lineage registry; proof-of-stop receipt; the 09:01 readout; tamper-evident halt journal; irreversibility honesty (compensation list); CI chaos drill ≤ 1 s. ≥2 Tier-1 harnesses exercised via the composed layers. Absorbs the `ai-loopguard` vocabulary into the dead-man switch design ([PRD 10](10-feature-parity.md)) |
| **v0.2.0** | **Graduated stops, dead-man switches, authorization + partner drills** | R15 graduated stops; R16 dead-man switches (budget exhaustion, tamper detection, kernel kill triggers — the `ai-loopguard` trigger class live); R17 drills-in-a-box (partner runbooks); R18 halt authorization (RBAC, dual control, break-glass + auto-revert); R19 third-party/SaaS agent coverage; R20 blast map; R21 offline evidence bundles; R22 halt-from-anywhere (Slack + agentinbox mobile). **Also:** third-party credential and cluster adapters (GitHub, AWS, Kubernetes, Okta), ordered by design-partner input; see candidates below |
| **v0.3.0** | **Fleet policies + attestation** | The **macOS network cut** (pf), moved from v0.1.0 (DD-51); R23 fleet halt policies ("auto-quarantine any agent matching X"); R24 external halt attestation (a third party runs the drill pack and publishes); full Tier-1×5 coverage via the layers; ≥3 Tier-2 runtime adapters where frameworks expose a surface |
| **later** | **Fleet coherence + enterprise** | Distributed halt stores; cross-tenant halt federation; enterprise-platform coverage via standards (v2.x, design-partner driven) |

## Candidates from the 2026-11-27 review (not requirements yet)

None of these changes the v0.1.0 scope or release gate. Each gets an R-number, a CUJ and a drill case only when
it is picked up. Vendor APIs named here are unverified.

| Candidate | Target | Note |
|---|---|---|
| Third-party adapters: GitHub tokens, AWS role sessions, Kubernetes controllers and pods, Okta, model-provider keys | v0.2.0 | Today credential cuts reach agentkeys-issued grants only; the first user's stack decides the order |
| Env-held secret readout (names only, redacted) | v0.2.0, or v0.1.0 only if built there | Tells a standalone user what to rotate |
| Standalone readout sources (subtree sockets, recent file writes) | v0.2.0 | Without agentwatch these readout fields stay `unavailable` |
| Baseline drill: show what survives a team's current switch (`kill -9`, key revoke, pod delete) | v0.2.0 | Revisit after the field test |
| Earlier budget dead-man | v0.2.0, as DD-14 already plans | Revisit only if runaway spend is the first user's main pain |
| Competitor refresh: date the "Nobody" verdicts, add vendors' announced roadmaps, re-verify the E5 source, correct H.R. 9917 status to "introduced" | Before any external pitch | PRD 03, 20, 29, 33 |

**Considered, not scheduled:** freeze labels on PRDs 24, 33, 36, 38 and 40; deferring the PagerDuty trigger
(cut at M7 if the schedule slips); one receipt schema-id bump before 1.0; running the claims linter over
`docs/prd/`.

## Compatibility targets by version

| Version | Tier-1 coding agents | Tier-2 frameworks |
|---|---|---|
| **v0.1.0** | ≥2 exercised end-to-end in the field test (via the composed layers); the rest documented as covered-by-construction or not supported — honestly | library + MCP-server surface; containment via process/credential layers |
| v0.2.0 | all 5 covered by construction; ≥3 exercised | runtime adapters for the frameworks that expose a stop surface |
| v0.3.0 | all 5, with a published per-harness containment matrix | ≥3 named adapters |

> agenthalt is harness-agnostic **by construction** — containment happens below the harness. "Compatible"
> means the composed layer set is **exercised end-to-end in the field test** for that harness; the release
> compatibility table states honest coverage, including explicit "not supported" rows ([PRD 19](19-harness-compatibility.md)).

## Migration & deprecation

- **Predecessor:** `ai-loopguard` (#58, shipped, MIT) is complete and remains useful as an in-loop escalation
  library; agenthalt **absorbs its halt-trigger class** and supersedes nothing — the two compose (loopguard may
  *raise* an agenthalt dead-man trigger). Full disposition: [PRD 10](10-feature-parity.md).
- **`BehaviorGuard` (#192):** unbuilt; its enforcement intent is absorbed into the dead-man trigger surface.
- **No silent behavior change:** a change to stop semantics, mode defaults, or trigger behavior is a versioned,
  reviewed change with a migration note — never a quiet edit. A receipt from v0.1.0 must verify forever
  (the evidence format is append-only).

## Release cadence

Each version ships with: release notes, a **compatibility table** (harness × layer × version), a **security
audit** (org governance floor), the **published standards/regulatory coverage matrix** ([PRD 20](20-standards-and-claims.md)),
and the **measured drill numbers** (p50/p95/p99 stop time on the stated hardware — measured, never assumed).
Articles accompany each release per the ecosystem content plan.

## Ecosystem dependency

agenthalt needs **layers to compose**: agentkeys (revocation, Wave 0), agentgate (gateway disconnect —
agentgate v1.0 ships Wave 1, so v0.1.0 degrades honestly: the adapter reports `unsupported` and the receipt
names the missing cut), agentseatbelt/agentkernel (freeze; kernel containment Wave 2), agentwatch (events +
evidence, Wave 0), agentpolicy (budget/tamper triggers, Wave 0), agentinbox (ask-gate for halt authorization,
v0.2.0). It ships last within Wave 0's five tools — composition only.

The Wave-0 meta-installer (monitor-only by default) wires agenthalt in as the stop surface; `agenthalt drill` is
the meta-MVP's closing demo — **"stop it"** is Wave 0's headline, and this is the tool that says it.
