# M0 design — Foundation, CLI & halt journal

**Status:** reviewed 2026-11-27 (decisions confirmed by the owner) · **WBS:** [M0](../wbs/v0.1.0/wbs-v0.1.0-part1-foundation-store.md) (#399) · **Bound by:**
[PRD 13](../prd/13-non-functional-requirements.md), [PRD 15](../prd/15-data-model.md),
[PRD 37](../prd/37-cli-and-output-ux-spec.md), [PRD 40](../prd/40-support-versioning-and-deprecation.md) ·
[ADR-0009](../adr/0009-enrollment-supervisor.md), [ADR-0011](../adr/0011-status-precedence-and-attestation.md)

M0 ships the parts every later milestone builds on: packaging, the CLI surface and its exit-code contract,
the configuration loader, the append-only halt journal, `doctor`, and structured logging. It stops nothing yet.
This document fixes the decisions M0 must make; anything it leaves to a later milestone is named as such.

## 1. Packaging and module layout

- Distribution `agentsec-agenthalt`, import package `agenthalt`, console script `agenthalt` (DD-20).
- `src/` layout, setuptools, **stdlib-only runtime**. The one exception is `tomli` on Python 3.10, which has no
  `tomllib` (`tomli; python_version < "3.11"`). Python **3.10+** (PRD 13), tested on 3.10–3.13.
- Dev extras: `pytest`, `pytest-cov`, `ruff`, `mypy`. Make targets: `setup`, `lint`, `typecheck`, `test`, `cov`,
  `gate` (the standing milestone gate), `clean`.

| Module | Responsibility |
|---|---|
| `agenthalt/__init__.py` | `__version__` |
| `agenthalt/exit_codes.py` | `ExitCode`, `ReceiptStatus`, the DD-39 precedence |
| `agenthalt/ids.py` | identifier validation (`^[a-zA-Z0-9_-]+$`) and ULID-style ids |
| `agenthalt/layout.py` | the `.agenthalt/` state-directory layout |
| `agenthalt/config.py` | config schema, precedence, fail-closed loading |
| `agenthalt/journal.py` | the hash-chained halt journal |
| `agenthalt/redact.py` | secret redaction (shared by logs now, evidence in M5) |
| `agenthalt/logs.py` | structured JSON logging with `halt_id` correlation |
| `agenthalt/doctor.py` | preflight checks and the verdict |
| `agenthalt/cli.py` | the command surface |

## 2. Command surface (Tier 1)

Every command in [PRD 37](../prd/37-cli-and-output-ux-spec.md) is **reserved in M0** so `--help` and scripts
see the final surface from day one. Commands whose behaviour lands later are honest about it:

| Command | M0 behaviour | Lands in |
|---|---|---|
| `doctor` | implemented | M0 |
| `journal show` / `journal verify` | implemented (library + CLI) | M0 (M7 adds trigger records) |
| `halt`, `pause`, `quarantine`, `kill` | argument validation (exactly one target, kill-requires-reason, fleet confirmation); then exit 5 "not available in this build" with the manual-fallback pointer. Nothing is journaled, because nothing was attempted | M1–M9 |
| `resume`, `escalate`, `lift` | argument validation; exit 5 "not available in this build" | M1, M9 |
| `run`, `attach` | argument validation (`run` requires a command after `--`; `attach --pid` must be a live pid of the invoking user); exit 5 "not available in this build" | M2 (2.7) |
| `status`, `prove`, `drill`, `evidence`, `runbook` | exit 5 "not available in this build" | M1, M6, M10, M5, M11 |

**Unavailable commands exit 5** ("nothing executed"). For the halt family the message also names the manual
fallback (`docs/prd/28-failure-mode-runbook.md` §7), because the person typing `kill` needs a way to stop the
agent today, not a usage hint.

Global flags (precedence §4): `--config PATH`, `--home DIR`, `--log-level`, `--log-format {json,text}`,
`--json` (machine output where a command supports it), `--version`, `-h/--help`.

Halt-family flags: `--agent | --session | --run | --all` (exactly one), `--mode {pause,quarantine,kill}`
(`halt` only; the shortcuts fix it), `--reason TEXT` (**required** for `kill` and `--all`, RK-20),
`--deadline-ms N`, `--yes` (skips the typed `halt all` confirmation; required for `--all` when not on a tty).

`run`: `--name NAME`, then `-- <cmd> [args…]`. `attach`: `--pid PID`, `--name NAME`.

## 3. Exit codes and precedence (Tier 0)

| Code | Name | Meaning |
|---|---|---|
| 0 | `COMPLETE` | halt complete — all members confirmed, zero survivors |
| 1 | `INCOMPLETE` | survivors or unconfirmed members |
| 2 | `PARTIAL_LAYER` | complete for reachable members; ≥1 layer `unsupported` |
| 3 | `FAILED` | blocking never established |
| 4 | `TRIGGER_REJECTED` | auth / replay / scope ceiling / non-interactive / fleet halt without confirmation |
| 5 | `USAGE` | usage or config error; nothing executed |

`ReceiptStatus` is `complete | partial-layer | incomplete | failed`, with precedence
**`failed` > `incomplete` > `partial-layer` > `complete`** (DD-39). `ReceiptStatus.worst(*statuses)` returns the
headline status; `exit_code_for(status)` maps it, so exit codes follow the same order `3` > `1` > `2` > `0`.
Precedence is decided once, in `exit_codes.py`, and every caller uses it.

`doctor` uses 0 (no failing check) or 5 (a check failed — the environment is misconfigured). Warnings exit 0.

## 4. Configuration model

**Format: TOML** (`agenthalt.toml`). TOML is in the stdlib from 3.11 (`tomllib`) and keeps the runtime
dependency-free. PRD 16's YAML-looking trigger examples describe the same keys; the on-disk format is TOML
(DD-41).

**Precedence:** flags > `AGENTHALT_*` env > config file > defaults. Config file location: `--config`, else
`AGENTHALT_CONFIG`, else `./agenthalt.toml` if present, else no file (defaults only).

| Key | Env | Flag | Default | Validation |
|---|---|---|---|---|
| `home` | `AGENTHALT_HOME` | `--home` | `.agenthalt` | path; created `0700` on first write |
| `log.level` | `AGENTHALT_LOG_LEVEL` | `--log-level` | `info` | `debug/info/warning/error` |
| `log.format` | `AGENTHALT_LOG_FORMAT` | `--log-format` | `json` | `json/text` |
| `halt.deadline_ms` | `AGENTHALT_DEADLINE_MS` | `--deadline-ms` | `1000` | int, 1–60000 |
| `choke.cache_ttl_s` | `AGENTHALT_CACHE_TTL_S` | — | `2` | int, 0–59 (*seconds, never minutes*, PRD 13) |
| `pause.max_ttl_s` | `AGENTHALT_PAUSE_MAX_TTL_S` | — | `86400` | int, 60–604800 (DD-37 default 24 h) |
| `journal.segment_max_entries` | — | — | `10000` | int ≥ 2 |

Reserved sections, accepted but empty until their milestone: `[store]` (M1), `[[triggers]]` (M7),
`[adapters]` (M3/M4). Any key inside them in M0 is rejected with "lands in M<n>".

**Fail-closed loading (DD-03, DD-42):**

- A malformed file, a wrong type, an out-of-range value, or an **unknown key** refuses to load. The error names
  the exact key and its source (file / env / flag) and the CLI exits 5 before doing anything else.
- Unknown keys are rejected rather than ignored because a silently ignored key — a trigger, a scope ceiling —
  is a fail-open path. This refines PRD 40's Tier-2 "forward-compatible readers": compatibility is additive
  within a major, and an older reader fails loudly on a newer file.
- Unrecognised `AGENTHALT_*` environment variables are **not** load errors (secret references such as
  `AGENTHALT_HMAC_KEY` share the prefix); `doctor` warns about any that look like a misspelt config key.

The loaded `Config` is a frozen dataclass that records each value's source, so `doctor` can print where every
setting came from.

## 5. State layout (`.agenthalt/`, DD-21)

```
.agenthalt/            (0700)
  journal/
    seg-000001.jsonl   append-only segments (0600)
    seg-000002.jsonl
    .lock              advisory write lock
  logs/                structured logs, when log output is a file
  store/ lineage/ halts/ receipts/ evidence/ drills/   created by later milestones
```

Identifiers used in paths must match `^[a-zA-Z0-9_-]+$` (PRD 15); anything else is a `ValueError` before any
path is built.

## 6. Halt journal format (Tier 0)

One JSON object per line, UTF-8. Fields:

| Field | Type | Notes |
|---|---|---|
| `schema` | `"agenthalt.journal.v1"` | frozen; evolution is additive |
| `seq` | int | starts at 1, +1 per entry, global across segments |
| `timestamp` | RFC 3339 UTC, ms precision | wall clock, human-readable only |
| `action` | enum | `raise`, `execute`, `complete`, `lift`, `resume`, `escalate`, `trigger_rejected`, `finding`, `anchor` (additive set) |
| `halt_id` | str or null | null for non-halt entries (e.g. `finding`) |
| `actor` | str | OS user or authenticated principal |
| `scope` | str or null | e.g. `agent:release-bot`, `all` |
| `mode` | str or null | `pause` / `quarantine` / `kill` |
| `reason` | str or null | free text, **redacted** before writing |
| `payload` | object | action-specific, redacted; may carry `payload_ref` |
| `prev_hash` | `"sha256:<hex>"` | genesis = `sha256:` + 64 zeros |
| `entry_hash` | `"sha256:<hex>"` | over the canonical form of every other field |

**Canonical form:** `json.dumps(entry_without_entry_hash, sort_keys=True, separators=(",", ":"),
ensure_ascii=False)` encoded UTF-8. `entry_hash = "sha256:" + sha256(canonical).hexdigest()`.

**Rotation:** when a segment reaches `journal.segment_max_entries`, the next entry opens
`seg-<n+1>.jsonl` with an **`anchor`** entry whose payload is `{ "prior_segment": "seg-<n>.jsonl",
"prior_head": <last entry_hash of seg-n>, "prior_entries": <count>, "prior_file_sha256": <hash of the file> }`.
The anchor's `prev_hash` is the prior head, so the chain is continuous across files.

**Concurrency:** writers take an exclusive `fcntl.flock` on `journal/.lock`, re-read the head, append one line,
`fsync`, release. Two concurrent `agenthalt` processes therefore never fork the chain.

**Append-time check (refined in review, 0.CR):** under the lock, `append()` checks only the tail — no
segment-number gap, the last segment's first and last lines parse, the last entry's hash recomputes — in
constant time. The full-chain walk is `journal verify` / `doctor`. Re-walking the history on every append
would grow without bound and break PRD 39's ≤ 50 ms trigger + journal budget.

**Verification (`journal verify`):** walk every segment in order and check, per entry: JSON parses, `schema`
known, `seq` contiguous, `prev_hash` equals the previous `entry_hash`, `entry_hash` recomputes. For every anchor,
`prior_head`, `prior_entries` and `prior_file_sha256` match the prior segment. Report the first failure with
segment, line and field; exit 0 when the chain is intact, 1 when it is not (a broken chain is an incomplete
record, not a usage error).

**What the local chain does and does not prove:** it detects any in-place edit, reorder, deleted line, deleted
middle segment or edited prior segment. It cannot by itself detect truncation of the *newest* entries or a
wholesale rebuild, because nothing outside the journal remembers the head. Remote anchoring (open decision #9,
M5) closes that gap. Until then `journal verify` prints the head hash so operators can record it elsewhere.

## 7. `doctor`

Each check returns `pass`, `warn`, `fail` or `n/a` with a one-line fix. The verdict is the worst result:
`fail` ⇒ exit 5.

| Check | Fails when | Fix shown |
|---|---|---|
| `python` | interpreter < 3.10 | install Python ≥ 3.10 |
| `platform` | not macOS or Linux (Windows: **fail**, DD-17) | use macOS/Linux; Windows plan in PRD 40 |
| `config` | config does not load (shows key + source) | the exact key to fix |
| `env` | **warn** on `AGENTHALT_*` names close to a config key | the probable intended name |
| `home` | state dir not creatable/writable, or wider than `0700` | `chmod 700 <home>` |
| `journal` | chain fails to verify | `agenthalt journal verify` + runbook pointer |
| `store`, `adapters` | `n/a` in M0 ("lands in M1 / M3–M4") | — |
| `panic_key` (macOS) | **warn** when the Accessibility permission is not granted | System Settings → Privacy & Security → Accessibility |
| `cgroup` (Linux) | **warn** when cgroup v2 is absent or the user's cgroup is not delegated (enrollment, M2, needs it) | enable cgroup v2 / `systemd-run --user --scope` delegation |
| `hooks` | never fails; reports whether agenthalt hooks are present for detected harnesses (ADR-0005) | — |

Platform checks are `warn`, not `fail`, in M0 because nothing in M0 depends on them; M2 (enrollment) and M7
(panic key) promote them to `fail` for the features that need them. The egress-fallback privilege check (DD-45,
ADR-0012) is not part of the M0 build; M3 adds it. `doctor --migrate` is a stub that reports
"no migrations in this version". `doctor --json` emits the checks as a list.

## 8. Structured logging and redaction

- Logs are JSON lines on stderr by default (`log.format = json`), one per event, with `ts`, `level`, `event`,
  `halt_id` (when bound) and fields. `text` format is for humans.
- `halt_id` correlation uses a context variable set by `bind_halt(halt_id)`; every log line inside that context
  carries it.
- **No secrets at any level** (PRD 06): a redaction filter runs on every record's message and fields before
  formatting. It replaces known secret shapes with typed placeholders `secret:<kind>[redacted]`: AWS access
  keys, `Bearer` tokens, `sk-…`/`ghp_…`-style API keys, PEM private-key blocks, JWTs, and `key=value` pairs whose
  key names a secret (`password`, `token`, `secret`, `api_key`, …). The journal uses the same redactor for
  `reason` and `payload`.

## 9. CI and quality gate

- `ci.yml`: matrix Python 3.10–3.13 on ubuntu-latest and macos-latest; `ruff check` + `ruff format --check`,
  `mypy --strict`, `pytest` with coverage `--cov-fail-under=95`; an install smoke job (`pip install .`,
  `agenthalt --version`, `agenthalt --help`, `agenthalt doctor`).
- `dco.yml` already enforces `Signed-off-by`. Actions are pinned to commit SHAs (Scorecard).

## 10. Test plan (0.T)

| Test file | Covers |
|---|---|
| `tests/test_exit_codes.py` | codes are stable; precedence over every combination of {survivor, unsupported layer, blocking failed} |
| `tests/test_cli_surface.py` | `--help` lists every command incl. `run`/`attach` flags; reserved commands exit as §2; kill-requires-reason; fleet confirmation; `run` with no command ⇒ 5; `attach` foreign/missing pid ⇒ 5 |
| `tests/test_config.py` | precedence flag > env > file > default; every invalid shape exits 5 naming key + source; unknown keys rejected; reserved sections |
| `tests/test_journal.py` | append/verify; a seeded edit, reorder, deleted line, deleted segment and edited prior segment are each detected; rotation keeps the chain; concurrent writers don't fork; redaction of `reason` |
| `tests/test_doctor.py` | verdict aggregation; each platform check's pass/fail/n-a paths with the fix text; `--json` |
| `tests/test_logs.py` | JSON lines parse; `halt_id` correlation; a planted canary secret never appears in output |

## Decisions recorded by this design

- **DD-41** — the config file format is TOML (`agenthalt.toml`).
- **DD-42** — unknown config keys are rejected (fail-closed); unknown `AGENTHALT_*` env names only warn.
- M0 halt commands validate their arguments and exit `5` ("not available in this build") with the manual-fallback
  pointer until a containment layer exists; nothing is journaled (§2).
