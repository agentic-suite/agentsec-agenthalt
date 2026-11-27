# The halt store (`agenthalt.store.v1`)

The halt store is the **single source of stop truth** (R8, ADR-0001): every runtime and gateway consults it
before an action executes. Implemented in [`src/agenthalt/store.py`](../../src/agenthalt/store.py); design in
[M1 design §3, §6](../design/m1-halt-store-choke.md).

## File

`<home>/store/state.json` (`0600`, directory `0700`). It holds only **active** halts; history is in the
[journal](journal-format.md).

```json
{
  "schema": "agenthalt.store.v1",
  "generation": 4,
  "journal_seq": 4,
  "journal_head": "sha256:…",
  "halts": [
    { "halt_id": "hlt_01KQ…", "scope": "agent:release-bot", "mode": "kill", "status": "finished",
      "actor": "maya", "reason": "prod mutation", "set_at": "2026-11-27T02:31:05.123Z", "ttl_s": null }
  ]
}
```

| Field | Meaning |
|---|---|
| `generation` | +1 on every change; the journal carries the same number |
| `journal_seq`, `journal_head` | the journal entry that produced this generation |
| `halts[].scope` | `all`, `tenant:<id>`, `agent:<id>`, `subtree:<run>`, `run:<id>`, `session:<id>`, `tool:<name>`, `writes-disabled` |
| `halts[].mode` | `pause` < `quarantine` < `kill` |
| `halts[].status` | lifecycle: `pending`, `blocking`, `executing`, `finished` (lifted halts leave the file) |
| `halts[].reason` | redacted before it is written |

## How it changes

Every mutation is **journal-first** and serialised by `store/.lock`:

1. append the journal entry (`raise`, `execute`, `complete`, `lift`) whose payload carries the full halt and the
   next generation;
2. write `state.json.<pid>.tmp`, `fsync`, rename over `state.json`, `fsync` the directory.

Readers therefore see the old file or the new one, never a partial write, and the store can always be
**rebuilt** from the journal. Lifecycle changes are compare-and-set (`Store.transition`): a stale writer cannot
resurrect a lifted halt or skip a state.

A **missing** store is *unavailable*, not empty: the choke cannot tell whether a halt is armed, so it fails
closed. `agenthalt status` creates the store on first use; `agenthalt doctor` warns until it exists.

## Health and the integrity signal (input contract for M8 `tamper_store`)

`Store.health()` returns `status` (`ok` · `unavailable` · `recovering`), `signal`, `armed` and `detail`.
**"Armed" is computed from the journal**, so deleting or editing the store cannot hide a halt.

| Situation | `status` | `signal` |
|---|---|---|
| store matches the journal | `ok` | — |
| store missing/unreadable, nothing armed (planned restart) | `unavailable` | — |
| store missing/unreadable, a halt armed | `unavailable` | `unreachable` |
| store truncated/corrupt, a halt armed | `unavailable` | `truncated` |
| store one or more generations behind, matching an earlier journal state (crash between journal and store) | `recovering` | — |
| store matches no journal state (edited outside agenthalt), journal broken, or journal not replayable | `unavailable` | `head_mismatch` |

The signal values are frozen: `unreachable`, `truncated`, `head_mismatch` (`INTEGRITY_SIGNALS`). In M1 they are
reported by `agenthalt status` (exit 1) and `agenthalt doctor` (`store` check fails). M8's `tamper_store` trigger
consumes them to raise a quarantine halt (ADR-0010); M1 does not raise a halt on its own.

`agenthalt status` repairs the `recovering` case automatically (rebuild from the journal) and journals a
`store_recovered` finding.

## Trust model in M1 (DD-44)

The agent usually runs as the same OS user as agenthalt, so it *could* open the file. M1 makes that detectable,
not impossible: every change is committed to the hash-chained journal, so an out-of-band edit shows up as
`head_mismatch`. Running agents under a separate OS user through enrollment (M2, ADR-0009) removes the access.
