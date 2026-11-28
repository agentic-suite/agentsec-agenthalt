# PRD 34 — Design-Partner Evaluation Guide

**BLUF:** The field eval is a **one-week kit**: install, run the four v0.1.0 demos, run the drill against *their*
stack, inspect the receipts, and answer ten questions with artifacts in hand. This guide tells a design partner
exactly what to test, what evidence to demand, how to report a miss, and — critically — what counts as a
**blocker** (product failed its core claim) versus a **feature request** (product worked, wanted more). Partners
who cannot fail us aren't validating us; this guide is built so they can.

**Status:** Draft — v0.1.0 (2026-11-14) · **Owner:** @deghosal-2026 · **Parent:** agentic-suite #209 · PRD #216

## Who this is for

A platform/security engineer (P1/P2) with a live agent workload on macOS or Linux, one Tier-1 harness (Claude
Code / Codex CLI preferred at v0.1.0), and 4–6 hours across a week. No ecosystem pre-install required — the
eval runs standalone; composed layers light up where they exist.

## Week 1, day by day

| Day | Activity | Artifact produced |
|---|---|---|
| 1 | Install; `agenthalt doctor`; run **Demo 1** (Replit stop) on the demo agent | receipt JSON #1; drill log |
| 2 | Run **Demo 2** (hooks removed) and **Demo 5** (panic key) | receipts #2, #5; doctor output showing hook surface absent |
| 3 | Point the **alert webhook** at their SIEM test rule (or PagerDuty sandbox); fire it from a script | receipt #trigger; journal entry with actor+channel |
| 4 | Run `agenthalt drill` **against a non-prod copy of their stack**; record the number | drill output (p50/p95/p99) on *their* hardware |
| 5 | **Demo 3** (credentials + the honest readout); verify one receipt offline on another machine (`prove`) | `VERIFIED (…)` output; readout with their real grant inventory |
| 6 | The ten questions (below) + the miss report | eval report |

## The ten questions (answered with artifacts, not opinions)

1. Did the halt stop **every** process in the subtree — and does the receipt *prove* it, or just assert it?
2. Was stop time ≤1 s on your hardware? What did the drill actually print?
3. What did the **readout** say was still true at 09:01 — and did anything surprise you?
4. Which of your credentials were `confirmed` revoked vs `unrevocable` — was the residual window honest?
5. With the hooks removed (Demo 2): did containment hold? Where did it *come from*?
6. Could you verify a receipt **offline, on another machine, without us**? Paste the verifier output.
7. What did the evidence snapshot capture — and was the canary secret absent from it?
8. What happens when the store is unreachable (kill it mid-drill)? Did the fleet keep running unguarded?
9. Could a forged trigger halt your fleet? (Try: unsigned webhook, replayed webhook, non-interactive panic key.)
10. What would you put in your runbook on day 2 of an incident — and does [PRD 28](28-failure-mode-runbook.md)'s
    manual fallback actually work on your stack?

## Environment questionnaire (before day 1)

- OS + kernel versions (macOS/Linux; Windows = not supported at v0.1.0 — stated, not discovered)
- Harness(es) + versions (Tier-1 matrix, [PRD 19](19-harness-compatibility.md))
- Spawn topology: does their agent spawn shells/sub-agents/stdio MCP servers? (The lineage tests live here)
- Ecosystem components present: agentwatch / agentkeys / agentpolicy / agentgate (each changes which
  confirmations will say `unsupported` — expected, not a failure)
- SIEM/alerting: webhook target + signing method available?
- Credential inventory: broker-issued vs static (predicts the `unrevocable_grants` honesty test)

## Evidence the partner should demand (the eval's teeth)

| Demand | The claim it tests |
|---|---|
| `receipt.confirmations[]` with signatures, not summaries | C-04 (proof-of-stop) |
| A drill number printed by CI-style output, not read off a slide | C-02 (measured, not assumed) |
| `survivors: []` **plus** the survivor-detector leg actually running | C-03 (verified-in-drill, not guaranteed) |
| The redaction canary absent from the exported bundle | C-07 / PRD 06 |
| A `partial-layer` receipt naming what wasn't covered | DD-18 honesty (no padding) |
| The self-halt pack's published results, misses included | [PRD 06](06-security-baseline.md) disclosure posture |

## Scoring: success criteria for the eval itself

**Eval PASS** = all four v0.1.0 demos ran without author help · drill ≤1 s p95 on their hardware · ≥1 receipt verified
offline · store-down test failed closed · zero unexplained triggers in the journal.

**Eval FINDINGS** (expected, non-blocking): unsupported layers honestly reported · lineage orphans surfaced ·
UX friction notes · platform-specific drill legs pending (Windows, some harnesses).

## Reporting a miss

- **Format:** the receipt/journal/drill artifacts + the exact command sequence + the observed-vs-expected delta.
- **Channel:** private issue (security-relevant misses → the disclosure path, [PRD 06](06-security-baseline.md)).
- **SLA:** a confirmed C-claim miss is Sev-1 — the claim is pulled from public material same-day
  ([PRD 31](31-claims-ledger.md)); a containment miss blocks the release ([PRD 07](07-success-metrics.md)).

## Blocker vs feature request (the classification rule)

| Category | Definition | Examples |
|---|---|---|
| **Blocker** | A core claim failed *with artifacts*: a survivor acted post-halt; a receipt lied (`complete` with live descendants); fail-open path found; evidence destroyed by the stop | "Receipt said complete; the MCP child kept calling out for 40 s" |
| **Defect** | The stop worked; a mechanism misbehaved honestly (wrong readout field, degraded evidence wrongly labeled) | "Readout missed the queued job until re-run" |
| **Feature request** | The stop worked as claimed; the partner wants more scope | "Quarantine without freezing the parent" · "Webhook for Slack-free envs" · "Windows" |
| **Out of scope (documented)** | Asked-for things the PRD explicitly refuses | Undo/rollback · detection/judgment triggers · stopping vendor-hosted processes ([PRD 14](14-non-goals.md)) |

The partner's job is to find blockers — an eval that finds none was not run with the knobs turned.

## What the partner gets back

- Their drill numbers and receipts become (anonymized, with consent) field-test evidence for the release.
- Their blocker/defect classifications feed the release gate directly ([PRD 12](12-traceability.md) WBS).
- Partners keep the eval kit; the v0.2.0 ask is one line: **run `agenthalt drill` once a week** — the
  operational-adoption metric ([PRD 07](07-success-metrics.md) drill adoption row).
