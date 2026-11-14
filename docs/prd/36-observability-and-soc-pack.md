# PRD 36 — Observability & SOC Pack

**BLUF:** A stop the SOC can't see didn't formally happen ([PRD 07](07-success-metrics.md)). agenthalt ships its
own observability: a **metrics registry** (Prometheus-style, cardinality-disciplined), **SLOs with an error
budget policy** (what happens when the stop stops meeting its numbers), and — the piece nobody else ships — a
**SOC content pack**: ready-to-import alert rules and dashboards for the `halt.*` event stream, so the
operator's SIEM alarms on halts, incomplete halts, spoofed triggers, and chain tampering on day one. The
product's honesty extends to its telemetry: metrics report survivors and incomplete stops as loudly as
successes.

**Status:** Draft — v0.1.0 (2026-11-14) · **Owner:** @deghosal-2026 · **Parent:** agentic-suite #209 · PRD #216

## Why an observability pack is product, not ops decoration

- R6's acceptance test is *"SOC dashboards can alarm on halts"* — that requires shipped content, not a schema.
- The 09:01 readout is a per-halt artifact; **fleet-level 09:01** (halt rates, incomplete trends, residue
  patterns) is what a security lead reviews weekly — that's metrics + dashboards.
- Detection and enforcement stay separate (DD-07), but **the stop must feed detection**: halt events are the
  highest-signal events an agent fleet emits.

## Metrics registry (v1, shipped)

| Metric | Type | Labels (bounded) | Source |
|---|---|---|---|
| `agenthalt_halts_total` | counter | `mode`, `trigger_source`, `status` | coordinator |
| `agenthalt_stop_time_seconds` | histogram | `phase` (`choke`/`suspend`/`revoke`/`gateway`/`snapshot_start`) | per-phase timestamps → [PRD 39](39-performance-budget.md) |
| `agenthalt_drill_stop_time_seconds` | histogram | `platform`, `case` | drill runner (the C-02 source) |
| `agenthalt_incomplete_halts_total` | counter | `reason` (`lineage_gap`/`deadline`/`layer_failed`) | receipt builder |
| `agenthalt_survivors_detected_total` | counter | `source` (`drill`/`post_halt_probe`) | survivor detector |
| `agenthalt_refused_calls_total` | counter | `layer` | choke/gateway enforcement points |
| `agenthalt_triggers_received_total` | counter | `source` | trigger adapters |
| `agenthalt_triggers_rejected_total` | counter | `source`, `reason` (`bad_signature`/`replay`/`rate_limited`/`scope_ceiling`/`non_interactive`) | trigger auth |
| `agenthalt_store_up` | gauge | — | store health |
| `agenthalt_paused_runs` | gauge | `age_bucket` (`lt1h`/`lt24h`/`ge24h`) | pause registry (RK-15 watch) |
| `agenthalt_unrevocable_grants` | gauge | — | readout aggregation |
| `agenthalt_journal_chain_verified` | gauge | — | chain verifier (0 on tamper = critical alarm) |

**Cardinality discipline:** labels are enumerated sets (no run ids, no agent names in metrics — those live in
events/journal); a label set that would exceed 100 series is a config error at load. High-cardinality
investigation belongs to the event stream and the journal, never to the metrics path.

## SLOs and the error budget

| SLO | Target | Measured by | Window |
|---|---|---|---|
| **Stop time** | p95 ≤ 1 s (drill, reference hardware) | `agenthalt_drill_stop_time_seconds` | per release + weekly CI |
| **Containment** | zero survivors per drill run | survivor detector | per run |
| **Halt availability** | store reachable 99.9% while armed | `agenthalt_store_up` | 30 d rolling |
| **Proof integrity** | 100% of halts produce verifiable receipts | `prove` golden + journal chain | per release |

**Error budget policy (what honesty demands):** when the weekly drill breaches the stop-time SLO or produces
any survivor, the *next release is frozen* to feature work until the catalogue is green again (DD-32's
consequence, made operational). The breach itself publishes in the release notes — the same no-false-success
rule as receipts ([PRD 07](07-success-metrics.md) anti-metrics).

## The SOC content pack (shipped, importable)

**Alert rules** (Sigma-style, plus mappings for Splunk/Datadog/Elastic in the pack):

| Rule | Condition on the agentwatch stream | Severity |
|---|---|---|
| `Halt Raised — Automatic` | `halt.raised` with `trigger.source=dead_man` | High — a dead-man switch fired; investigate the trigger |
| `Halt Incomplete` | `halt.completed` with `status=incomplete` | **Critical** — a survivor exists; page the responder |
| `Halt Failed` | `halt.completed` with `status=failed` | Critical — blocking never established; manual fallback |
| `Spoofed Trigger Attempt` | `trigger.rejected` rate spike per source | High — likely key compromise or DoS probing (RK-5) |
| `Chain Verification Failure` | journal chain head mismatch (gauge 0) | Critical — tamper; preserve segments, escalate |
| `Store Unreachable` | `agenthalt_store_up=0` sustained > 30 s | High — fail-closed engaged; fleet is deny-mode |
| `Pause Limbo` | `agenthalt_paused_runs{age_bucket="ge24h"} > 0` | Medium — TTL policy not firing (RK-15) |

**Dashboards:** *Fleet Halts* (rate by mode/trigger/status, stop-time percentiles, refused-call volume) ·
*Incomplete Triage* (survivors by reason, affected agents from events — the per-halt drill-down is the receipt)
· *Drill History* (per-platform measured numbers over releases — the honesty ledger in graph form).

## Event → SIEM field mapping (shipped as part of the pack)

| agentwatch field | ECS/OCSF-friendly mapping |
|---|---|
| `halt_id`, `event_id` | event uids (join keys) |
| `trigger.source`, `trigger.principal` | `user.name` / `source.domain` per event taxonomy |
| `target.agent`, `scope` | resource ids |
| `mode`, `status`, `reason_code` | normalized severity/disposition fields |
| receipt ref (`halt.completed`) | evidence chain pointer |

## Log format

- `haltd` emits structured JSON logs (one line per pipeline stage: raise/resolve/plan/execute/confirm/receipt)
  with `halt_id` correlation — the log is the debuggable version of the journal, never a replacement for it.
- No secrets in logs at any level ([PRD 06](06-security-baseline.md)); the same redaction pipeline guards both
  artifacts.

## Compatibility & non-goals

- Exports: Prometheus text + OTel metrics; events via agentwatch (OTLP) — no bespoke agent, no required
  vendor. Dashboards ship as JSON imports for Grafana, plus a text-only `agenthalt status` for the
  no-SIEM case (P4 Sam sees the same truth in his terminal).
- **Non-goal:** agenthalt is not a detection product — the pack *feeds* the SOC; it never classifies behavior
  ([PRD 14](14-non-goals.md)).
- **Non-goal:** long-term event storage — retention and the lake are agentwatch's job; the metrics above are
  aggregates with bounded cardinality by design.
