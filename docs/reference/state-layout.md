# The `.agenthalt/` state directory

agenthalt keeps all local state under one directory (DD-21). It is local-first: nothing here is sent anywhere.
The location is `.agenthalt` in the working directory by default; change it with `--home`, `AGENTHALT_HOME`
or `home` in `agenthalt.toml` ([configuration](configuration.md)).

```
.agenthalt/                 0700  owner-only
  journal/                  0700  the halt journal (M0)
    seg-000001.jsonl        0600  append-only, hash-chained segments
    seg-000002.jsonl        0600  each new segment opens with a rotation anchor
    .lock                   0600  advisory write lock (concurrent writers never fork the chain)
  store/                          the live halt state (M1)
  lineage/                        append-only lineage edge segments (M2)
  halts/<halt_id>/                halt, subtree, stop plan, executions, confirmations (M3-M6)
  receipts/<halt_id>.json         proof-of-stop receipts, offline-verifiable (M6)
  evidence/<halt_id>/             redacted evidence snapshots (M5)
  drills/                         measured drill results (M10)
  logs/                           structured logs, when log output goes to a file
```

Only `journal/` exists in this build; the other directories are created by the milestone that owns them.

## Rules

- **Permissions.** Directories are created `0700` and files `0600`. `agenthalt doctor` fails if the state
  directory is readable by anyone else.
- **Identifiers in paths** must match `^[a-zA-Z0-9_-]+$`; anything else is refused before a path is built.
- **Never edit the journal.** A broken chain is incident evidence. `agenthalt journal verify` tells you where
  it broke; the failure-mode runbook ([PRD 28](../prd/28-failure-mode-runbook.md)) tells you what to do.
- **Not for version control.** `.agenthalt/` is in `.gitignore`; it holds incident records, not source.

See also: [journal format](journal-format.md), [CLI reference](cli.md).
