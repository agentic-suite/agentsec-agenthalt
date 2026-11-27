# Code-review log — agenthalt v0.1.0

Per-milestone code/design reviews. Each milestone's `.CR` work item records findings here; **all findings must
be resolved before the milestone closes** (see the [WBS index](wbs-v0.1.0-index.md) standard closure).

Format: `#<n> [<milestone> Review] <area> — <finding> → <resolution> (<commit>)`.

## Log

### M0 — Foundation, CLI & halt journal (0.CR, #410) — 2026-11-27

- **Scope:** `src/agenthalt/` (cli, config, exit_codes, ids, journal, redact, logs, doctor), `tests/`,
  `.github/workflows/`, `pyproject.toml`, `Makefile`, reference docs; reviewed against the
  [M0 design](../../design/m0-foundation.md), PRD 13/15/37/39/40, ADR-0009/0011, DD-39/41/42.
- **Findings:**
  - #1 [M0 Review] journal — `append()` re-verified the entire chain on every write, so append cost grew with
    history and would eventually break PRD 39's ≤ 50 ms trigger + journal budget → constant-time tail check under
    the lock (gap, first/last line parse, last hash recomputes); full walk stays in `journal verify`/`doctor`;
    timing test with 5,000 prior entries + 5 refusal tests added; design §6 and journal reference updated.
  - #2 [M0 Review] cli — argparse's default usage-error exit code 2 collides with Tier-0 `partial-layer` →
    parser overrides `error()` to exit 5; locked in by `test_unknown_command_is_usage_not_partial_layer`.
  - #3 [M0 Review] redact — the `key=value` rule re-redacted an existing placeholder
    (`secret:secret:secret[redacted]`), losing the secret kind → lookaheads skip placeholders; covered by
    `test_reason_and_payload_are_redacted`.
  - #4 [M0 Review] doctor — env-typo detection matched on the shared `AGENTHALT_` prefix, flagging
    `AGENTHALT_HMAC_KEY` as a typo of `AGENTHALT_HOME` → compare only the suffix; `test_unrelated_env_name_passes`.
  - #5 [M0 Review] workflows — `dco.yml`/`scorecard.yml` pinned actions by tag → every action pinned to a commit
    SHA with a version comment; enforced by `test_every_action_is_pinned_to_a_commit_sha`.
  - #6 [M0 Review] tests — tamper paths (forged mid-segment anchor, demoted anchor, extra field, empty segment,
    non-object line) and failure paths (unreadable config/journal, non-writable home) were untested → tests added;
    coverage 99.9%, every module ≥ 95%.
  - #7 [M0 Review] config — `import os` inside `load_config` → module-level import.
- **Accepted, not changed (stated limits):** redaction covers known secret shapes and secret-named keys, not
  arbitrary high-entropy strings (the M5 evidence pipeline extends it); `attach` as root can name any pid (the
  same-user check is OS permission-based); the local chain cannot detect truncation of the newest entries
  (remote anchoring, open decision #9, M5).
- **Gates:** suite 184 passed · coverage 99.91% (≥ 95%) · `ruff` zero · `ruff format` clean · `mypy --strict` clean
  (Python 3.12, macOS). CI matrix 3.10–3.13 × ubuntu/macos runs on push.
- **Resolution:** all findings resolved; no open findings.

<!--
### M0 — Foundation, CLI & halt journal (0.CR)

- **Scope:** ...
- **Findings:** ...
- **Gates:** suite <n> passed · coverage ≥ 95% · `ruff` zero · `mypy --strict` clean.
- **Resolution:** ...

### M1 — Halt store, dual choke & fail-closed (1.CR)
...
-->
