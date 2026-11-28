# PRD 37 — CLI & Output UX Spec

**BLUF:** The CLI is the product's face at 3 a.m.: the operator is stressed, the terminal is the interface, and
the next keystroke matters. This spec fixes the command surface, **exit codes** (a stable, documented contract —
scripts and runbooks depend on them), output modes (human/`--json`/quiet), the **kill-requires-reason** and
**fleet-requires-confirmation** patterns, the receipt one-liner, and the accessibility rules (no color-only
signals, ever). The design rule throughout: *the tool states what happened, what is still true, and what to do
next — and it never fakes a success.*

**Status:** Draft — v0.1.0 (2026-11-14) · **Owner:** @deghosal-2026 · **Parent:** agentic-suite #209 · PRD #216

## Command surface (v0.1.0)

| Command | Purpose | Key flags |
|---|---|---|
| `agenthalt run` | Launch an agent under the enrollment supervisor (owns its process group/cgroup; records the lineage root — DD-38); returns the agent's exit status (DD-47) | `--name`, `--user` (DD-46), `-- <cmd>` |
| `agenthalt attach` | Enroll an already-running agent, best-effort (`lineage_verified: false` until a full walk succeeds) | `--pid`, `--name` |
| `agenthalt halt` | Raise a halt (mode via flag or shortcut) | `--agent\|--session\|--run\|--all`, `--mode`, `--reason` (required for `kill`/`--all`), `--deadline-ms`, `--json`, `--yes` |
| `agenthalt pause` / `quarantine` / `kill` | Mode shortcuts for the ladder ([PRD 18](18-stop-modes.md)) | same as `halt` |
| `agenthalt resume` | Resume a paused run | `--halt <id>` (prints the readout as a warning) |
| `agenthalt escalate` | One command up the ladder | `--halt <id> --to pause\|quarantine\|kill` |
| `agenthalt lift` | Lift a halt (journaled) | `--halt <id> --reason` (required) |
| `agenthalt status` | Live state + the 09:01 readout | `--halt <id>`, `--watch`, `--json` |
| `agenthalt prove` | Verify a receipt (online/offline) | `--receipt <f>`, `--evidence <bundle>` |
| `agenthalt drill` | Run the rehearsal | `--case <name>`, `--platform <os>`, `--all`, `--json` |
| `agenthalt journal` | `show\|verify` the halt journal | `--halt <id>`, `--segment` |
| `agenthalt evidence` | `collect\|export\|verify` snapshots | `--halt <id>`, `--out` |
| `agenthalt doctor` | Preflight sanity (run before you need it), incl. platform checks: macOS Accessibility (panic key), Linux cgroup v2 delegation (enrollment), egress-fallback privileges (DD-45), hook surface present/absent | `--migrate`, `--verbose` |
| `agenthalt runbook` | Print the operator runbook section | `--section <n>` ([PRD 28](28-failure-mode-runbook.md)) |

Naming: subcommands are verbs, flags are long-form only in docs (`-h/--help` excepted); config precedence is
**flags > env (`AGENTHALT_*`) > config file > defaults** — documented once, honored everywhere.

## Exit codes (the stable contract)

Scripts, runbooks, and CI legs branch on these; they are **Tier-0 immutable** once shipped ([PRD 40](40-support-versioning-and-deprecation.md)):

| Code | Meaning | Notes |
|---|---|---|
| `0` | Halt **complete** — all members confirmed, zero survivors | The only green |
| `1` | Halt **incomplete** — survivors or unconfirmed members (receipt says which) | The responder's next step is in the readout |
| `2` | Halt **partial-layer** — complete for reachable members; ≥1 layer `unsupported` | Expected on Wave-0 stacks (DD-18) |
| `3` | Halt **failed** — blocking never established | Pointer: `runbook --section 7` manual fallback |
| `4` | Trigger **rejected** (auth/replay/scope-ceiling/non-interactive) | Journaled; never silently dropped |
| `5` | Usage/config error | Nothing executed |

When several outcomes apply, the exit code follows the receipt's status precedence (DD-39): `3` > `1` > `2` > `0`.

`prove` extends the contract: `0` = `VERIFIED (complete)`, `1` = `VERIFIED (incomplete/partial/failed)` (the
receipt is honest but not clean), `2` = `TAMPERED`. A runbook that says "&& echo fleet stopped" is only correct
because exit 0 *means* it.

## Output modes

- **Human (default):** the **receipt one-liner**, then the readout, then survivors (red, listed), then next
  steps. Example:

  ```
  ✔ halt complete in 0.61s — release-bot subtree (4 members) killed, 2 grants revoked (confirmed)
    evidence: snap_01J written · refused 3 calls post-flip · compensation: 1 landed side effect
    readout: 1 static key unrevocable (expires 2026-12-01) · 1 queued job · downstream: escalation-bot
    receipt: hlt_01J (verify: agenthalt prove --receipt .agenthalt/receipts/hlt_01J.json)
  ```

- **`--json`:** the full receipt ([PRD 26](26-receipt-schema-and-examples.md) schema — machine consumers get the
  same object `prove` verifies; no separate "API shape").
- **`--quiet`:** `halt_id` + status word only — for pipes and panic-key contexts.

## Interaction patterns

| Pattern | Rule |
|---|---|
| **Kill requires a reason** | `--reason` mandatory for `kill` and `--all`; the reason lands in the journal and the receipt (`trigger.reason`). Muscle memory must not destroy evidence wordlessly (RK-20) |
| **Fleet confirmation** | `--all` prompts for a typed confirmation (`halt all`) unless `--yes`; in CI mode (`--ci` or non-tty) fleet halts without `--yes` are **exit 4**, never an implicit proceed |
| **Pause-first nudge** | `halt` without `--mode` on an interactive tty asks: *uncertain? pause preserves the scene — escalate any time.* (One line, not a wizard) |
| **No prompts in CI** | non-tty ⇒ no interactive questions, ever; every branch resolves to a flag default or exit 4 |
| **Destructive verbs never alias** | `kill` is never `rm`-flavored shorthand; `--force` does not exist (idempotency makes it meaningless — DD-27) |

## Accessibility & terminal hygiene

- **Never color-only:** every status signal is word + icon + exit code (`✔ complete` / `✖ incomplete`);
  `--no-color` and `NO_COLOR` honored; the human output parses identically without styling.
- Screen-reader-friendly: table mode (`--plain`) emits one fact per line, no box-drawing.
- Long receipts wrap, never truncate — a cut-off survivor line is a false success (the anti-metric as a
  terminal rule).

## Error-message style (the three-sentence rule)

Every error states: **what happened** (exact layer/phase) · **what is true right now** (is the agent still
running?) · **what to do next** (the runbook section, the exact next command). Example:

```
✖ halt incomplete (exit 1) — process adapter confirmed 3/4 members; run_a3 unconfirmed (lineage edge missing).
  run_a3 is still blocked at the choke but NOT suspended — it may still hold warm credentials.
  next: agenthalt kill --run run_a3 --reason "survivor from hlt_01J"  ·  runbook: agenthalt runbook --section 2
```

## v0.2.0 additions (reserved, not specced yet)

Authorization flows (dual-control prompts, break-glass windows), `halt --from slack` channel context, fleet
policy listing. Reserved names, documented so scripts can be written against a stable surface — but their UX
lands with the features.

## Non-goals

- No interactive TUI/dashboard in v1 — the CLI's output **is** the dashboard ([PRD 14](14-non-goals.md), DD-15).
- No i18n at v1 (English); the output grammar is designed so translation later never changes exit codes or
  `--json` shapes.
- No shell-integration magic beyond completions (bash/zsh/fish shipped) — the panic key is the one deliberate
  exception, and it is configuration, not a daemon (CUJ-12).
