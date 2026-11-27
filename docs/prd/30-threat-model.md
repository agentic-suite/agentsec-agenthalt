# PRD 30 — Threat Model

**BLUF:** agenthalt is the emergency control, so its own compromise is a fleet-scale event: a stolen trigger
halts a healthy fleet (**DoS via the switch**), a suppressed store lets a rogue agent survive its stop, a forged
receipt proves a containment that never happened. This is the formal model behind [PRD 06](06-security-baseline.md):
system context and trust boundaries, five threat actors (a compromised agent, a compromised harness, a malicious
or careless operator, an external attacker, a compromised ecosystem component), a STRIDE matrix over the six
assets, the top attack paths ranked, mitigations mapped to tests, and the residual risks we accept out loud.

**Status:** Draft — v0.1.0 (2026-11-14) · **Owner:** @deghosal-2026 · **Parent:** agentic-suite #209 · PRD #216

## System context & trust boundaries

```
┌─ trust boundary 1: the internet / vendor estate ─────────────────────────────┐
│  PagerDuty  Slack  SIEM webhooks          SaaS-hosted agents (unreachable proc)│
└───────┬──────────────────────────────────────────────────────── ▲ ───────────┘
        │ signed triggers                                       │ layer report: unsupported
┌───────▼──── trust boundary 2: the operator's host / fleet ─────────────────────┐
│  agenthalt: haltd · halt store · lineage registry · journal · receipt builder  │
│     │ composed action surfaces                                                │
│  agentkeys (revoke)   agentgate (disconnect)   agentseatbelt/agentkernel       │
┌─────┴──────────────────────────── trust boundary 3: the agent's world ────────┐
│  harness ⇄ agent ⇄ children/shells/spawned MCP servers ⇄ model + tools        │
│  (assumed hostile under compromise — the R5 premise)                          │
└───────────────────────────────────────────────────────────────────────────────┘
```

**Boundary rules:** everything inside boundary 3 is untrusted for *control* purposes (it may be observed, never
obeyed); triggers cross boundary 1 only with signatures; the store and journal never accept writes from
boundary 3; the receipt assembles only from boundary-2 enforcement-point reports.

## Assets (from [PRD 06](06-security-baseline.md))

halt state · lineage registry · trigger paths · receipt/proof · evidence snapshot · halt journal ·
authorization state.

## Threat actors

| Actor | Capability | Goal |
|---|---|---|
| **A1 compromised agent** (incl. via Plugin4Shell) | code exec in boundary 3; can edit its own hooks/prompts; can spawn | Survive the stop; conceal damage; keep credentials warm |
| **A2 compromised harness** | controls the surface A1 lives in; can remove hooks, lie to observers | Make containment depend on the harness (it must not) |
| **A3 malicious/careless operator** | legitimate trigger access; broad scopes | Halt the wrong fleet; erase an inconvenient journal |
| **A4 external attacker** | network reach to trigger endpoints; key theft | DoS via the switch; forge halts/receipts; steal evidence |
| **A5 compromised ecosystem component** | a peer tool's identity (agentpolicy/agentkeys events) | Inject dead-man triggers; poison lineage |

## STRIDE matrix

| Asset | Spoofing | Tampering | Repudiation | Info disclosure | DoS | Elevation |
|---|---|---|---|---|---|---|
| Halt state | forged halt (A4/A5) → **auth + scope ceilings** | suppression/deletion (A1/A2) → **out-of-band store + fail-closed + suppression-as-trigger** | actorless halt → **journaled actor+channel** | scope enumeration → **auth'd status reads** | store flooding → **quota + idempotency** | trigger widening → **max_scope structural** |
| Lineage | forged edges (A5) → **adapter-authenticated writes** | edge deletion (A1) → **append-only chain + attempt-as-trigger** | — | subtree map to attacker → **read auth** | enumeration flood → **deadline + honest incomplete** | poisoned blast scope → **scope proofs in receipt** |
| Triggers | spoofed webhook/PagerDuty (A4) → **HMAC/mTLS + replay window** | key theft (A4) → **rotation + rate limits** | "nobody sent it" → **trigger record pre-resolution** | principal discovery → **per-source auth** | trigger flood (RK-5) → **per-principal limits + dual control on `all`** | panic-key squat (A1) → **interactive-session binding** |
| Receipt | forged confirmations (A4/A1) → **enforcement-point signatures** | field edits → **receipt_hash + chain** | "it stopped, trust me" → **offline verifier output** | readout leak of topology → **receipt read auth** | — | fabricated `complete` → **schema invariant: survivors⇒incomplete** |
| Evidence | fake snapshot → **chain + manifest** | post-halt edit → **chain + off-host export** | — | secrets in trace window → **redaction-before-persistence + canary test** | snapshot deletion → **write-before-terminate + export** | — |
| Journal | — | edit/erase (A3) → **hash chain + anchored rotation** | deny a halt → **chain proves history** | — | truncation → **missing-segment = loud finding** | — |
| Authorization | forged approver (A4) → **principal binding** | self-approval (A3) → **dual-control quorum** | unattributed fleet halt → **dual-control records** | — | — | RBAC bypass → **scope ceilings enforced at store, not UI** |

## Top attack paths (ranked)

1. **Suppress-the-stop** (A1/A2 → halt state): highest impact — the product's core promise. Broken by
   construction (out-of-band + fail-closed); the attempted suppression becomes a trigger. *Residual:* a
   kernel-level compromise below all composed layers — out of scope, named in the readout (`uncovered_routes`).
2. **DoS-via-the-switch** (A4 → triggers, A3 → `all`): most likely path. Auth + rate limits + dual control;
   *residual:* a stolen legit principal can still halt its scoped fleet until rotation — journaled, reversible
   (`lift`).
3. **Survivor-by-ignorance** (A1 spawns via an unobserved surface): most common in practice (RK-2). Orphan
   watchlist + scope-inheritance choke + drill survivor detection; *residual:* fully invisible spawn surfaces
   — the receipt refuses to claim completeness (`lineage_verified: false`).
4. **Receipt forgery** (A4/A1): lowest likelihood, worst credibility impact. Enforcement-point signatures +
   offline verification; *residual:* a fully compromised boundary-2 enforcement point can sign a lie — the
   self-halt pack's "colluding layer" case documents detection (cross-layer contradiction: a `confirmed` stop
   with post-halt refused-call activity).
5. **Evidence exfiltration** (A4 → snapshot): the snapshot is a map of the incident, redacted by default and
   access-controlled; *residual:* retention window trade-off (configurable).
6. **Remote listener abuse** (A4 → `haltd` webhook/PagerDuty/Slack endpoints): a network-facing control plane.
   Localhost bind by default; remote listeners opt-in, authenticated, rate-limited, capped at `max_scope: agent`;
   a listener crash never affects local halts or the choke. *Residual:* a stolen HMAC key can halt agents in its
   scope until rotation (journaled, `lift`-able) (RK-24).

## Mitigation → test mapping (every mitigation is a shipped test)

| Mitigation | Test (from [PRD 25](25-test-strategy.md) / [PRD 06](06-security-baseline.md)) |
|---|---|
| Fail-closed store | `test_failclosed_store` (fuzzed matrix) |
| Suppression-as-trigger | self-halt pack case: kill the store mid-drill ⇒ tamper halt fires |
| Hooks never load-bearing | hostile-harness drill leg (Demo 2) |
| Trigger auth + replay + rates | `test_trigger_replay`, spoof-source pack cases |
| Dual control on fleet scope | `test_authz_dualcontrol` (v0.2.0) |
| Edge chain + forged-edge refusal | `test_edges_append_only`, `test_forged_edge_rejected` ([PRD 27](27-lineage-model.md)) |
| Receipt signatures + verifier | `test_receipt_verify` + `prove` golden cases ([PRD 26](26-receipt-schema-and-examples.md)) |
| Redaction (canary secret) | `test_snapshot_canary` |
| Journal chain | `test_journal_tamper` (seeded edit detected) |
| Colluding-layer detection | self-halt pack: `confirmed` stop + live refused calls ⇒ contradiction finding |

## Residual risks (accepted, out loud)

- **Below-the-layers compromise** (rootkits, kernel implants): out of agenthalt's reach; the readout names the
  uncovered routes; agentkernel's eBPF layer is the ecosystem's partial answer where deployed.
- **Same-OS-user store access (until M2):** in v0.1.0's first milestones the agent usually runs as the same OS
  user as agenthalt and could open the `0600` store file. Every store change is committed to the hash-chained
  journal, so an out-of-band edit raises the `head_mismatch` integrity signal; running agents under a separate OS
  user via enrollment (M2, ADR-0009) removes the access itself (DD-44).
- **A colluding boundary-2 component** can sign one lie until cross-layer contradiction catches it; the
  self-halt pack documents the detection window honestly.
- **Physical-console access** defeats everything local; the panic key is *for* the person at the console.
- **The stop cannot un-send** — R13, not a vulnerability, but the threat model says it plainly because the
  attacker's favorite post-halt narrative is "the damage is done anyway."

## Review cadence

The self-halt pack is the living form of this model; every new surface (a new trigger, a new mode, a new
adapter) adds a case or the PR doesn't merge (RK-22). This document re-reviews at each release alongside the
coverage matrix regeneration.
