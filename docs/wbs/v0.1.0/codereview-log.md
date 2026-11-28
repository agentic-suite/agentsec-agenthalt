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

### M1 — Halt store, dual choke & fail-closed (1.CR, #422) — 2026-11-27

- **Scope:** `scopes`, `reasons`, `store`, `choke`, `coordinator`, the M1 CLI (`halt`/`status`/`lift`), the `doctor`
  store check, and their tests; reviewed against the [M1 design](../../design/m1-halt-store-choke.md), PRD 02/13/15/39,
  ADR-0001/0002/0004/0010, DD-27/36/43/44.
- **Findings:**
  - #1 [M1 Review] coordinator — `advance()` read the halt and wrote it back outside the store lock, so a lift
    landing in between was silently undone (the lifted halt re-inserted) → `Store.transition()` compare-and-set
    under the lock; `test_a_lift_racing_an_advance_is_never_undone`, `test_two_advancers_cannot_both_move_a_halt`.
  - #2 [M1 Review] journal — `verify()` raised on a non-UTF-8 segment, an unreadable segment, and an unlistable
    journal directory (crashing `journal verify`, `status`, `doctor`) → each is reported as a broken chain; three
    tests added; the now-dead `doctor` exception handler removed.
  - #3 [M1 Review] store — `replay()` silently skipped an unknown store op, which could drop a halt from a rebuild
    (fail-open) → raises `StoreCorruptError`; `health()` turns it into `head_mismatch`.
  - #4 [M1 Review] cli — `status` caught a bare `Exception` → narrowed to `StoreError`/`JournalError`; the
    halt-family branch of `_unavailable` became dead code once halts record → removed.
  - #5 [M1 Review] choke — the `GatewayChoke` protocol declared `name` as settable, so frozen implementations did
    not satisfy it → read-only property.
  - #6 [M1 Review] tests — CLI tests ran in the repo working directory and, once halts started writing state, left a
    `.agenthalt/` there → every CLI test runs in a temp dir (autouse fixture); stray state removed.
- **Accepted, not changed (stated limits):** same-OS-user store access is detectable, not prevented, until
  enrollment (DD-44, PRD 30); `health()` re-verifies the whole journal (O(history)) — acceptable for `status` and
  `doctor`, never on the halt path, where the choke reads only the store; a `subtree` halt reaches descendants only
  when the caller supplies `ancestors` until the lineage registry lands (M2).
- **Gates:** suite 313 passed · coverage 100.00% · `ruff` zero · `ruff format` clean · `mypy --strict` clean.
- **Resolution:** all findings resolved; no open findings.

### M2 — Lineage registry & subtree resolution (2.CR, #434) — 2026-11-27

- **Scope:** `lineage`, `observe`, `subtree`, `supervisor`, the M2 CLI, `status` and `doctor` changes, and their
  tests; reviewed against the [M2 design](../../design/m2-lineage-enrollment.md), PRD 06/27, ADR-0008/0009. An
  independent reviewer agent (read-only) plus self-review. Each finding has a regression test.
- **Findings:**
  - #1 [M2 Review] supervisor — damage to the journal mid-run aborted supervision and reported "the command did
    not run" for a running agent → recording failures degrade, never end, supervision.
  - #2 [M2 Review] lineage/journal — one malformed line crashed `status`, `doctor` and the supervisor → type-checked
    parsing; any bad record is a finding; undecodable journal is a `JournalError`.
  - #3 [M2 Review] supervisor — a halted run's child could `attach` itself as a fresh root and then `run`
    (fail-open) → attach records the run under its enrolled ancestors.
  - #4 [M2 Review] supervisor — `run` recreated a deleted halt store and launched, and trusted an edited one
    (fail-open) → the store is verified against the journal first.
  - #5 [M2 Review] observe — process start times depended on `TZ`, so a halted parent was not recognised → UTC;
    Linux start includes boot time.
  - #6 [M2 Review] supervisor — damaged lineage with no parent found did not block a spawn → refused while any
    halt is armed.
  - #7 [M2 Review] subtree — a dead run adopted processes of a reused process group → group needs a live member.
  - #8 [M2 Review] observe/subtree — the run-id marker matched command-line arguments and unrelated processes →
    environment only, same user, no older than the run.
  - #9 [M2 Review] subtree — a `sup_` placeholder outranked a real parent and edges were re-appended on every
    resolve → real parents win.
  - #10 [M2 Review] subtree — `session:` halts were not inherited → carried through lineage.
  - #11 [M2 Review] supervisor/lineage — blindness and failed writes were lost and `lineage_verified` read true; a
    broken journal chain was not a lineage finding → journaled, retried, flagged.
  - #12 [M2 Review] supervisor — `--user` checked only the nearest parent; `sudo` wrote state as root → every
    ancestor checked including group write; state written as the invoking user.
  - #13 [M2 Review] lineage — a held lock hung the resolver past its deadline; the resolver crashed when it could
    not record → bounded lock wait; `complete: false`.
  - #14 [M2 Review] cli — `agenthalt --home X run -- cmd` failed (present since M0) → global options are skipped
    when splitting at `--`.
- **Accepted, not changed (stated limits):** without `--user` a same-user agent can read the adapter keys; the
  agent shares the operator's terminal under `--user` (`TIOCSTI`, mitigated by sudo `use_pty`); the journal and
  store locks are not deadline-bounded; macOS cannot see a child that double-forks between polls, clears its
  environment and closes inherited descriptors; ACLs are not examined by the `--user` directory check.
- **Gates:** macOS (Python 3.12) 453 passed, 2 skipped (Linux-root-only), coverage 99%, M2 modules 96–99%; Linux
  container as root 451 passed, 4 skipped, including the real cgroup double-fork and `--user` drop tests; ruff and
  `mypy --strict` clean. CI does not run the two Linux-root tests; the container run is their evidence.
- **Resolution:** all findings resolved; no open findings.

### M3 — Process-tree containment (3.CR, #446) — 2026-11-27

- **Scope:** `executors`, `process_exec`, `egress`, `containment`, `coordinator`, `observe`, `cli`, `doctor`,
  `supervisor`; independent read-only review against the [M3 design](../../design/m3-process-containment.md),
  PRD 02/18/26/39, ADR-0003/0006/0011/0012. Regression tests: `tests/test_review_m3.py`.
- **Findings:**
  - #1 [M3 Review] process — a passed deadline returned without the undo record, leaving processes frozen for good
    → write-ahead cut record (`cutlog`).
  - #2 [M3 Review] containment — one late listing failure discarded the undo and skipped the kill → same record;
    the later listings are isolated and terminate always runs.
  - #3 [M3 Review] containment — a late child was reported frozen while running → late members are suspended,
    `kill` rescans, any unconfirmed live member is a survivor.
  - #4 [M3 Review] lift — overlapping halts could leave a process stopped with no halt active → records move to the
    covering halt.
  - #5 [M3 Review] lift — a lift racing a finishing halt released nothing → the record is read after removal.
  - #6 [M3 Review] lift — a failed release could not be retried → it stays recorded; `lift` again retries.
  - #7 [M3 Review] egress — `kill` restored the network although the member list was incomplete → requires complete.
  - #8 [M3 Review] egress — `kill` forgot rules it failed to remove → kept and reported `failed`.
  - #9 [M3 Review] egress — release deleted rules by line number and could delete someone else's → by rule, read back.
  - #10 [M3 Review] locks — a member holding a state lock hung every halt → 2 s bound; processes cut even when the
    block cannot be written (`failed`).
  - #11 [M3 Review] safety — forged lineage under `sudo` could signal other users' processes → only the invoking uid
    or a root-recorded `--user` uid.
  - #12 [M3 Review] deadline — an abandoned phase changed things nothing recorded → write-ahead record; longer caps
    for built-ins.
  - #13 [M3 Review] lift — unreadable lineage released covered processes → they stay frozen.
  - #14 [M3 Review] outcome — damaged lineage was not `incomplete` → it is.
  - #15 [M3 Review] deadline — past the deadline no `SIGSTOP` was sent → always sent.
  - #16 [M3 Review] process — a continued sibling was not stopped again → re-signalled.
  - #17 [M3 Review] cgroup — a freeze could be left with no thaw recorded → recorded as its own item.
  - #18 [M3 Review] safety — a halting process in a nested cgroup was not detected → checked by cgroup path.
  - #19 [M3 Review] identity — Linux start times were built on `btime`, which moves with the clock → boot id.
  - #20 [M3 Review] signing — a first-use race could leave an empty executor key → atomic create.
- **Own findings before the review:** a journal failure after the block aborted the cut; a block failure exited 1
  instead of 3; a broken third-party adapter stopped `halt` altogether; zero-member halts had no process row. All
  fixed with tests. On a real kernel, `nft socket cgroupv2` was unavailable → `iptables` cgroup match (ADR-0012).
- **Accepted, not changed (stated limits):** third-party adapters load before the block; `continued` reports the
  signal, not an observation; a halt from inside the halted tree may not converge; resolve and listing timeouts sit
  outside the deadline; without `--user` the agent can tamper with state while running; macOS has a small pid-reuse
  window and no network cut.
- **Not re-reviewed:** the fixes were verified by tests, not by a second independent review.
- **Gates:** macOS (Python 3.12) 575 passed, 5 skipped, coverage 98%, M3 modules 95% or higher; Linux container as
  root 576 passed, 4 skipped, including the real cgroup freeze/kill and `iptables` cut tests; ruff and
  `mypy --strict` clean. CI skips the Linux-root tests; the container run is their evidence.
- **Resolution:** all findings resolved or listed above as accepted.

<!--
### M0 — Foundation, CLI & halt journal (0.CR)

- **Scope:** ...
- **Findings:** ...
- **Gates:** suite <n> passed · coverage ≥ 95% · `ruff` zero · `mypy --strict` clean.
- **Resolution:** ...

### M1 — Halt store, dual choke & fail-closed (1.CR)
...
-->
