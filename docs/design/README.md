# agenthalt — Design docs (v0.1.0)

Design docs are written **first** in every milestone, as its `.D0` work item
([WBS index](../wbs/v0.1.0/wbs-v0.1.0-index.md)), and reviewed before any code. This index lists each
milestone's design doc, what it must decide, and the inputs it is bound by. Requirements live in the
[PRD](../prd/README.md); load-bearing decisions live in the [ADRs](../adr/README.md). A design doc may refine
them but never contradict them. A contradiction is resolved by amending the PRD or adding an ADR, not inside
the design doc.

| M | Design doc (to be written at `.D0`) | Must decide | Bound by | Status |
|---|---|---|---|---|
| M0 | `m0-foundation.md` | CLI surface incl. `run`/`attach`, config precedence, exit-code contract (incl. DD-39 precedence), journal chain format, `doctor` checks (macOS Accessibility for the panic key, Linux cgroup v2 delegation for enrollment, hook surface) | PRD 13, 37, 40 · ADR-0009, 0011 | not started |
| M1 | `m1-halt-store-choke.md` | Store scopes/TTL/persistence, choke-read path and cache TTL, fail-closed reason codes, the store integrity signal (`unreachable`/`truncated`/`head_mismatch` while armed) that feeds `tamper_store` | PRD 02, 39 · ADR-0001, 0002, 0004, 0010 | not started |
| M2 | `m2-lineage-enrollment.md` | Edge model + segments, ingestion priority, **enrollment supervisor** (process group / cgroup ownership), macOS escape handling, orphan + post-halt spawn rules, edge-deletion findings | PRD 27 · ADR-0008, 0009, 0010 | not started |
| M3 | `m3-process-executor.md` | Executor contract, per-OS suspend/kill, block-new-first sequencing, deadline handling, how the zero-hook "runtime choke" is realised (suspend + egress) | PRD 02 §Mechanisms, 32 · ADR-0002, 0005 | not started |
| M4 | `m4-composed-executors.md` | agentkeys/agentgate/agentkernel adapters, degradation matrix, **signing model** incl. the separate OS-executor key and `attestation: self` | PRD 26, 32 · ADR-0003, 0011 | not started |
| M5 | `m5-evidence.md` | Snapshot components, chain math, redaction pipeline + canary, snapshot-before-termination order, retention/encryption | PRD 17, 38 · ADR-0006 | not started |
| M6 | `m6-receipt-readout.md` | Receipt schema v1 fields (incl. `survivor_probe`, `attestation`, `readout.coverage`), status precedence, readout/compensation data sources, `prove` semantics (incl. reporting self-attested cuts) | PRD 26, 37 · ADR-0003, 0011 | not started |
| M7 | `m7-triggers-events.md` | Auth per trigger, replay windows, `max_scope` ceilings (remote ≤ `agent`, `all` local-CLI-only — DD-16), listener bind defaults, halt-event schema binding | PRD 16, 20, 30 · ADR-0007 | not started |
| M8 | `m8-hostile-harness.md` | Hook-as-accelerant, the three self-tamper triggers, hostile-harness fixture, **survivor-probe method per platform** | PRD 06, 16 · ADR-0005, 0010 | not started |
| M9 | `m9-modes.md` | Ladder semantics (three rungs, manual `escalate`), pause/resume state, TTL 24 h (DD-37), basic quarantine, 24 h test cadence | PRD 18 · ADR-0001 | not started |
| M10 | `m10-drill.md` | Pack format, runner measurement, the 12 cases' goldens (incl. `PASS (degraded)` without agentgate), CI artifact | PRD 35, 39 | not started |
| M11 | `m11-hardening.md` | Perf gate, metrics/SLOs, self-halt pack scope, claims linter, privacy enforcement | PRD 13, 31, 36, 38 | not started |
| M12 | field-test plan (`12.D0`) | The platform × harness × trigger × layer matrix | PRD 19, 22, 34 | not started |
| M13 | release plan (`13.D0`) | Gate checklist, artifacts, PyPI/attestation steps | PRD 07, 40 | not started |

## Open decisions each design must close

Taken from the [PRD 21 open decisions register](../prd/21-evidence-register-and-method.md): enrollment
mechanism #11 (M0/M2), lineage edge priority #1 (M2, revisited M12), retention + encryption #5 (M5), remote
anchoring #9 (M5), self-attestation key custody #13 (M4), verification-key publication #10 (M4/M13),
survivor-probe method #12 (M8), reference hardware #14 (M11), agentgate co-shipping #7 (M12 partner eval). When a design
closes one, record it as a DD entry in [PRD 11](../prd/11-decisions.md) and update the register.
