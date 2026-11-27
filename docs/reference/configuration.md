# Configuration

agenthalt reads **TOML** (`agenthalt.toml`, DD-41). Precedence is **flags > `AGENTHALT_*` environment > config
file > defaults**. Implemented in [`src/agenthalt/config.py`](../../src/agenthalt/config.py); design in
[M0 design §4](../design/m0-foundation.md).

## Finding the file

1. `--config PATH`
2. else `AGENTHALT_CONFIG`
3. else `./agenthalt.toml`, if it exists
4. else no file — defaults only

An explicitly named file that does not exist is an error.

## Keys

| Key | Env | Flag | Default | Allowed |
|---|---|---|---|---|
| `home` | `AGENTHALT_HOME` | `--home` | `.agenthalt` | non-empty path; relative paths resolve from the working directory |
| `log.level` | `AGENTHALT_LOG_LEVEL` | `--log-level` | `info` | `debug`, `info`, `warning`, `error` |
| `log.format` | `AGENTHALT_LOG_FORMAT` | `--log-format` | `json` | `json`, `text` |
| `halt.deadline_ms` | `AGENTHALT_DEADLINE_MS` | `--deadline-ms` (halt commands) | `1000` | 1–60000 |
| `choke.cache_ttl_s` | `AGENTHALT_CACHE_TTL_S` | — | `2` | 0–59 — *seconds, never minutes* |
| `pause.max_ttl_s` | `AGENTHALT_PAUSE_MAX_TTL_S` | — | `86400` | 60–604800 (24 h default, DD-37) |
| `journal.segment_max_entries` | `AGENTHALT_JOURNAL_SEGMENT_MAX_ENTRIES` | — | `10000` | ≥ 2 |

```toml
home = "/var/lib/agenthalt"

[log]
level = "info"
format = "json"

[halt]
deadline_ms = 1000

[pause]
max_ttl_s = 86400
```

Reserved sections — accepted only empty until their milestone: `[store]` (M1), `[adapters]` (M3),
`triggers = []` (M7).

## Fail-closed loading (DD-42)

A config that does not load stops everything: the CLI exits **5** before running the command, and the error names
the key and where it came from:

```
agenthalt: config error: config key 'halt.deadline_ms' (file:/srv/agenthalt.toml): must be 1..60000, got 0
```

- Malformed TOML, a wrong type, an out-of-range value, or an **unknown key** are all errors. An unknown key is
  never ignored: a silently skipped trigger or scope ceiling is a fail-open path.
- Unrecognised `AGENTHALT_*` **environment** names are *not* errors (secret references such as
  `AGENTHALT_HMAC_KEY` share the prefix). `agenthalt doctor` warns when one looks like a misspelt config key.
- `agenthalt doctor` is the one command that still runs with a broken config — it reports the error as a failing
  check. `agenthalt doctor --verbose` prints every effective value and its source.
