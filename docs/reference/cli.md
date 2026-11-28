# CLI reference

The full command surface is reserved from M0 so scripts and runbooks see the final names from day one
([PRD 37](../prd/37-cli-and-output-ux-spec.md), [M0 design §2](../design/m0-foundation.md)). This page states
what each command does **in this build**; the `Lands in` column is when its behaviour arrives.

## Global options

| Option | Meaning |
|---|---|
| `--config PATH` | config file (default `./agenthalt.toml` if present) — see [configuration](configuration.md) |
| `--home DIR` | state directory (default `.agenthalt`) — see [state layout](state-layout.md) |
| `--log-level LEVEL` | `debug`, `info`, `warning`, `error` |
| `--log-format FMT` | `json` (default) or `text`; logs go to stderr and are always redacted |
| `--version`, `-h/--help` | version and help; `--help` ends with the exit-code table |

Global options go **before** the command: `agenthalt --home /var/lib/agenthalt doctor`.

## Commands

| Command | Arguments | In this build | Lands in |
|---|---|---|---|
| `doctor` | `--json`, `--verbose`, `--migrate` | **runs** — preflight checks and a verdict | M0 |
| `journal show` | `--halt ID`, `--json` | **runs** — prints journal entries | M0 |
| `journal verify` | — | **runs** — verifies the hash chain | M0 |
| `run` | `--name NAME`, `--user USER` (needs sudo) `-- <cmd> [args…]` | **runs** — [enrolls](lineage.md) and supervises the command; returns the agent's own exit status; a refusal is exit 5 and nothing executes | M2 |
| `attach` | `--pid PID` (required), `--name NAME` | **runs** — enrolls your own running process best-effort; prints `lineage_verified` | M2 |
| `halt` | one of `--agent/--session/--run/--all`; `--mode {pause,quarantine,kill}` (default `pause`); `--reason`; `--deadline-ms`; `--yes`; `--json` | **runs** — blocks at the [choke](choke.md), then [cuts the enrolled processes](executors.md); exit 2 (`partial-layer`) at best in this build, 1 if anything is unconfirmed, 3 if the block failed | M1, M3 (credentials M4) |
| `pause` / `quarantine` / `kill` | as `halt`, mode fixed | as `halt` | M1, M3 |
| `resume` | `--halt ID` | exits 5 | M9 |
| `escalate` | `--halt ID --to MODE` | exits 5 | M9 |
| `lift` | `--halt ID --reason TEXT` (required, non-blank) | **runs** — removes the halt (journaled), then [releases what it cut](executors.md#lift); exit 1 if something could not be released; unknown id ⇒ 5 | M1, M3 |
| `status` | `--halt ID`, `--json` (`--watch` M6) | **runs** — active halts, store health and integrity signal; recovers an interrupted write; lists enrolled runs, orphans, gaps and lineage tamper findings; exit 1 if the store is unhealthy or the lineage was tampered with | M1 (readout M6) |
| `prove` | `--receipt FILE` (required), `--evidence BUNDLE` | exits 5 | M6 |
| `drill` | `--case NAME`, `--platform {macos,linux}`, `--all`, `--json` | exits 5 | M10 |
| `evidence collect/export/verify` | `--halt ID` (required), `--out` | exits 5 | M5 |
| `runbook` | `--section N` | exits 5 | M11 |

## Rules the halt family enforces now

- **Exactly one target.** `--agent`, `--session`, `--run` or `--all`.
- **Kill requires a reason.** `--reason` is mandatory for `kill` (including `halt --mode kill`) and for `--all`
  (RK-20: muscle memory must not destroy evidence wordlessly).
- **Fleet confirmation.** `--all` asks you to type `halt all`, unless `--yes`. In a non-interactive context
  without `--yes`, the command is **rejected with exit 4** — it never proceeds implicitly.
- **Safe identifiers.** Target and halt ids must match `^[a-zA-Z0-9_-]+$` (1–128 chars).
- **`run` needs a command** after `--`; `attach` refuses a missing pid or another user's process.
- **Scopes:** `--agent X` ⇒ `agent:X`, `--session X` ⇒ `session:X`, `--run X` ⇒ `subtree:X` (the run and its
  subtree), `--all` ⇒ `all`.
- **Idempotent:** re-raising an active `(scope, mode)` keeps the existing halt id, journals a `duplicate_raise`
  finding and cuts again.

Usage errors always exit **5**, never argparse's default 2 (2 means `partial-layer`). See
[exit codes](exit-codes.md).
