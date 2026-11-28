# PRD 35 — Drill Pack Catalogue & Format

**BLUF:** A **drill pack** is a versioned, case-anchored rehearsal set — the same "no pack without a proof"
discipline as agentpolicy's rule packs, applied to the **stop** instead of the decision. agenthalt ships
**twelve named launch cases**, each mapped to the killer feature, CUJ, risk, and claims-ledger entry it proves;
each with a deterministic verdict and a golden expectation. The drill is release-blocking (DD-32), the pack is
CI-executed, and partners author their own cases through the same one-PR flow. **Nobody else ships the drill
(coverage row #25) — the catalogue is the moat.**

**Status:** Draft — v0.1.0 (2026-11-14) · **Owner:** @deghosal-2026 · **Parent:** agentic-suite #209 · PRD #216

## Pack format

```
drills/<name>/
  metadata.yaml     # name, version, description, min_agenthalt, license,
                   #   claims[] (C-ids this case proves), tags, platforms[]
  cases.yaml       # the case: setup, trigger, halt expectation, verdict rules
  goldens/         # expected receipt fragments (status, confirmations, survivors)
  README.md        # one page: what it proves, how to run, how to tune
```

- `cases.yaml` is **declarative**: fixture (spawn topology, hooks on/off, credential fixtures), trigger
  (source + auth mode), expected halt behavior (mode, deadline, per-layer expectations), and verdict rules —
  no imperative scripts in the pack; the runner interprets.
- Packs are **semver'd and reviewed like code**; a pack change is a reviewed change to what "supported" means
  ([PRD 19](19-harness-compatibility.md) — the drill is the compatibility verifier).
- `agenthalt drill --case <name> --platform <os>` runs one case; the release job runs the full catalogue and
  emits a machine-readable artifact (per-case verdict + measured timings + hardware note) that the claims
  ledger (C-02, C-03) reads directly ([PRD 31](31-claims-ledger.md)).

## Verdict vocabulary (exhaustive)

| Verdict | Meaning | Release effect |
|---|---|---|
| `PASS` | Expectation met exactly (golden match, ≤1 s where the case budgets it, zero survivors) | green |
| `PASS (degraded)` | Expectation was *honest degradation* (e.g. `partial-layer` with agentgate absent) and the golden specified it | green — degradation is only passable when the golden *predicts* it |
| `FAIL` | Any divergence: a survivor, an unpredicted `unsupported`, a golden mismatch, a hang past deadline | **release-blocker** |
| `NOT-RUN` | Platform/harness not present on the runner | recorded in the compatibility table — **never silently omitted** |

## The launch catalogue (12 named cases)

| # | Case | What it proves | Maps to | Golden asserts |
|---|---|---|---|---|
| 1 | **`replit-stop`** | The composed stop, end-to-end, on the clock (Demo 1) | K1/R1/R2, CUJ-1, C-02/C-03 | status `complete` with agentgate, `partial-layer` → `PASS (degraded)` without it (DD-18); every reachable confirmation present; survivors `[]`; stop ≤ 1 s p95 |
| 2 | **`hostile-harness`** | Containment with every hook removed (Demo 2, the Plugin4Shell case) | K6/R5, CUJ-13, C-05 | status `complete` with agentgate, `partial-layer` → `PASS (degraded)` without it (DD-18); hook surface reported absent; zero dependence on hooks |
| 3 | **`credential-residue`** | Revocation confirmed for brokered grants; static keys surfaced honestly (Demo 3) | CUJ-5, R20 | `confirmed` for grant A; `unrevocable_grants` lists grant B with window |
| 4 | **`panic-key`** | The local red button; non-interactive invocation refused | CUJ-12, RK-5 | halt from interactive session; non-interactive attempt journaled + rejected |
| 5 | **`spawn-race`** | A child spawned mid-halt is choke-blocked by scope inheritance | [PRD 27](27-lineage-model.md) post-halt spawn rule | post-halt child never acts; blocked-by-scope event logged |
| 6 | **`store-down`** | Fail-closed: store unreachable ⇒ high-impact actions denied | R8, CUJ-16, RK-1/RK-14 | choke denies with `halt_store_unavailable`; drill leg proves manual fallback works |
| 7 | **`trigger-spoof`** | Unsigned/stale/replayed triggers rejected; `all`-scope from any remote trigger refused by `max_scope` (DD-16) | R4, RK-5 | all spoof attempts rejected + journaled; no halt raised |
| 8 | **`edge-forgery`** | Unauthenticated lineage writes refused; deleted edges detected | R9, [PRD 27](27-lineage-model.md), PRD 06 | forged edge refused; deletion attempt ⇒ `tamper_lineage` trigger fires (DD-36) |
| 9 | **`receipt-tamper`** | Edited receipt/confirmation fails `prove`; forged `complete` impossible | R10/R12, RK-12 | `TAMPERED` verdict; survivors⇒`incomplete` invariant holds |
| 10 | **`evidence-canary`** | Redaction-before-persistence: a planted canary secret never lands in snapshot or receipt | R3, [PRD 06](06-security-baseline.md), C-07 | canary absent from bundle; placeholder + count present |
| 11 | **`pause-ttl`** | Pause/resume integrity after 24 h; expiry auto-escalates to kill | R7, RK-15 | resume with full context; `pause_expired` escalation journaled |
| 12 | **`manual-fallback`** | The fleet is stoppable when agenthalt itself is dead | [PRD 28](28-failure-mode-runbook.md) §7 | each layer's manual command succeeds; runbook leg verified |
| 13 | **`fleet-drill`** *(v0.2.0)* | Dead-man trigger chain + dual-control `all` halt | R16/R18, CUJ-19/21 | budget-exhaustion fires with `reason_code`; single approval does not release a fleet halt |

> The catalogue ships 12 cases at v0.1.0; `fleet-drill` lands with the v0.2.0 triggers/authorization work.
> Every new surface feature adds or updates a case or the PR doesn't merge (RK-22, the anti-rot rule).

## Case→test binding (the catalogue is the integration suite's index)

Each case composes the unit/contract/integration tests named in [PRD 25](25-test-strategy.md) and
[PRD 27](27-lineage-model.md) into one end-to-end verdict — `replit-stop` runs L3+L4 with `test_m1_compose`
fixtures; `store-down` wraps `test_failclosed_store`; `edge-forgery` wraps `test_forged_edge_rejected`;
`evidence-canary` wraps `test_snapshot_canary`. The drill is the *only* place a green unit suite is allowed to
be contradicted — and when it is, the drill wins (release-blocker, RK-16 anti-theater rule).

## Partner-authored cases (the v0.2.0 surface, R17)

- A partner's case is one `metadata.yaml` + `cases.yaml` + golden fragments + a one-page README — **one PR**
  (the ecosystem's pack pattern, [PRD 32](32-build-vs-integrate.md)).
- Partner cases run against *their* stack topology (spawn shapes, real grant fixtures) and produce the same
  verdict artifact — the operational-adoption metric ([PRD 07](07-success-metrics.md) drill-adoption row).
- `agenthalt drill --case <partner-case> --private` runs locally without publishing; a partner may share only
  the verdict artifact (numbers + verdict, no environment detail) — the attestation pathway to R24.

## Governance

- **Reviewed like code**; signed on release; deprecation carries a migration note (DD-31).
- **No case without a claim**: every case's `claims[]` must reference a C-id in the claims ledger — a case that
  proves nothing we claim is cut; a claim without a case is demoted to forbidden ([PRD 31](31-claims-ledger.md)
  rule 5).
- **Numbers from the runner only**: the pack's measured timings are the single source for C-02; hand-typed
  numbers fail the claims lint.
