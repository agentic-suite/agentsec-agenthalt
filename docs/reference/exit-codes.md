# Exit codes

Exit codes are a **Tier-0** contract ([PRD 40](../prd/40-support-versioning-and-deprecation.md)): they never
change once shipped, because runbooks and scripts branch on them. Implemented in
[`src/agenthalt/exit_codes.py`](../../src/agenthalt/exit_codes.py).

| Code | Name | Meaning | What to do |
|---|---|---|---|
| `0` | `COMPLETE` | halt complete — every member confirmed, zero survivors | nothing; keep the receipt |
| `1` | `INCOMPLETE` | survivors or unconfirmed members | read the readout; re-halt survivors by id ([PRD 28 §2](../prd/28-failure-mode-runbook.md)) |
| `2` | `PARTIAL_LAYER` | complete for reachable members; ≥1 layer `unsupported` | cut the missing layer by hand ([PRD 28 §3](../prd/28-failure-mode-runbook.md)) |
| `3` | `FAILED` | blocking never established | manual fallback now ([PRD 28 §7](../prd/28-failure-mode-runbook.md)) |
| `4` | `TRIGGER_REJECTED` | auth, replay, scope ceiling, non-interactive panic key, unconfirmed fleet halt | check the trigger; it was journaled where a journal exists |
| `5` | `USAGE` | usage or configuration error — **nothing executed** | fix the command or the config key named in the error |

## Precedence (DD-39)

One halt can be several things at once — the common Wave-0 case is a survivor on a stack without agentgate.
The receipt's headline status is the worst true one, and the exit code follows it:

```
failed (3)  >  incomplete (1)  >  partial-layer (2)  >  complete (0)
```

So a halt with a survivor *and* a missing gateway exits **1**, never 2; the `unsupported` layer is still listed in
the receipt. `ReceiptStatus.worst()` and `exit_code_for()` are the single place this is decided
([ADR-0011](../adr/0011-status-precedence-and-attestation.md)).

## Other commands

| Command | `0` | non-zero |
|---|---|---|
| `doctor` | no check failed (warnings allowed) | `5` — at least one check failed |
| `journal verify` / `journal show` | chain intact | `1` — the chain is broken (an incomplete record, not a usage error) |
| `prove` (M6) | `VERIFIED (complete)` | `1` verified but not clean · `2` `TAMPERED` |
| reserved commands in this build | — | `5` — "not available in this build" |

`agenthalt run` is a launcher: it returns the **agent's** exit status, not a halt outcome (DD-47). A refusal
before launch is `5`.
