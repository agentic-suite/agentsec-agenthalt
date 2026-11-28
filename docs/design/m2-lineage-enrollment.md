# M2 design — Lineage registry, subtree resolution & enrollment

**Status:** self-reviewed 2026-11-27 (the `--user` decision, §7, confirmed by the owner) · **WBS:**
[M2](../wbs/v0.1.0/wbs-v0.1.0-part2-lineage-process.md) (#424) · **Bound by:**
[PRD 27](../prd/27-lineage-model.md), [PRD 15](../prd/15-data-model.md), [PRD 06](../prd/06-security-baseline.md) ·
[ADR-0008](../adr/0008-lineage-process-observation-priority.md), [ADR-0009](../adr/0009-enrollment-supervisor.md),
[ADR-0010](../adr/0010-self-tamper-triggers-v010.md), [ADR-0012](../adr/0012-built-in-egress-fallback.md) ·
DD-23, DD-24, DD-36, DD-38, DD-44, DD-46, DD-47, DD-48

M2 gives a halt something to walk: runs enroll through a supervisor, every spawn becomes an authenticated
append-only edge, and a resolver turns a target into its members. **Nothing is suspended or killed** (M3).

## 1. Modules

| Module | Responsibility |
|---|---|
| `agenthalt/lineage.py` | records, adapter credentials, hash-chained segments, journal checkpoints, tamper detection |
| `agenthalt/observe.py` | process table (pid, ppid, pgid, sid, uid, start), cgroup membership, run-id marker |
| `agenthalt/subtree.py` | graph (dedup, priority, conflicts, orphans), deadline-bounded resolver, scope inheritance |
| `agenthalt/supervisor.py` | `run` / `attach`: containment, gated launch, escape detection, privilege handling |

## 2. Records and nodes

Node ids: `run_<ulid>` (an enrolled run), `sup_<ulid>` (the supervisor, parent of a root edge),
`proc_<pid>_<start>` (an observed process; the start time guards against pid reuse).

Record (`agenthalt.lineage.v1`), one JSON object per line in `<home>/lineage/seg-NNNNNN.jsonl`:
`schema, seq, recorded_at, kind, adapter, data, mac, prev_hash, chain_hash`.

| `kind` | `data` |
|---|---|
| `edge` | `parent_run`, `child_run`, `spawn_source` (`process`/`runtime`/`hook`), `child` (node metadata) |
| `verified` | `run`: an attached run whose full walk succeeded |
| `anchor` | rotation anchor: prior segment name, head, count, file SHA-256 |

A **root edge** is an edge whose `child` metadata has `enrollment: run | attach`.

## 3. Chain, journal checkpoint and authentication (DD-48)

- Each record is chained (`prev_hash` → `chain_hash`); segments rotate like the journal's.
- After every append batch the journal gets a `lineage` entry `{lineage_seq, lineage_head}`. The journal therefore
  remembers the lineage head, so deleting the newest edge, or rebuilding a segment, is detectable.
- Order is **lineage first, checkpoint second**: a crash between them leaves lineage *ahead* (harmless, the
  records still authenticate); lineage *behind* a checkpoint is tampering.
- Writes need an `AdapterCredential`. Each adapter has its own HMAC key in `<home>/keys/lineage/<name>.key`
  (`0600`). A record whose `mac` does not verify is a forged edge: refused at write, a finding on read.
- **Limit:** an agent running as the same OS user can read the keys and forge records. Only `run --user` (§7)
  removes that access.

**Tamper findings.** `LineageRegistry.check_tamper()` returns `TamperFinding(segment, seq, problem, detail,
detected_at)` and journals each one once as `finding: tamper_lineage`. Journaled before anything reacts to it;
8.2 consumes it as the `tamper_lineage` trigger.

## 4. Priority, conflicts, orphans

- **Union for existence:** an edge from any authenticated source enters the graph.
- **Priority for parentage:** a real parent outranks a supervisor placeholder (`sup_`); then `process` >
  `runtime` > `hook`; equal priority keeps the earliest. Duplicates
  collapse by `(parent, child)`. A disagreement is journaled once as `finding: lineage_conflict`.
- **Orphan:** a node whose parent is unknown and which is not a root. Listed in `orphans`, shown by `status`,
  never killed and never dropped.

## 5. Resolver

`resolve(target, deadline_ms)` returns `Subtree(roots, members, grants, grants_status, orphans, gaps,
complete, lineage_verified, reason)`.

- Targets: a run id (that run and its descendants), an agent name, or all.
- Members = recorded edges **plus** a live process walk from every live member (new descendants are recorded).
- Deadline-bounded: loading, walking, observation and waiting for the lineage lock all check one monotonic
  deadline; the process listing has that deadline as its timeout. Out of time, or unable to read or record
  ⇒ `complete: false` with a reason, never a hang. (The journal and store locks are not bounded.)
- A process group counts as the run's only while a known member still holds it, so a reused group number cannot
  adopt strangers. Linux start times include the boot time; macOS start times are read in UTC.
- `grants` come from a `GrantSource`; none exists before M4, so `grants_status` is `unavailable`, not empty.
- `lineage_verified` is false if the walk is incomplete, the chain has findings, a gap exists, or an attached run
  was never verified.
- A supervisor that is gone while its agent lives is a `supervisor_lost` finding.

## 6. Post-halt spawn rule

`check_lineage(choke, graph, run)` asks the choke about the run **and every ancestor**; any deny wins. A halt
on `agent:`, `run:`, `subtree:` or `session:` therefore reaches a child that was never enumerated. The
supervisor runs this check before launching, against **every** enrolled ancestor found by process ancestry (the
`AGENTHALT_RUN_ID` environment variable is only a second hint, since an agent can unset it). `session:` halts are
inherited where a runtime recorded a `session` on an edge; `run` itself records none. A refused spawn is
journaled as `finding: post_halt_spawn`. Unknown or damaged lineage ⇒ `lineage_known = False` ⇒ high-impact
actions are denied with `lineage_gap`. At launch: with a parent, damaged lineage refuses; with no parent found,
it refuses only while some halt is armed (the damage could be hiding that parent).

## 7. Enrollment supervisor

**Launch order** (`run [--name N] [--user U] -- cmd`): resolve the command → prepare containment → fork a child
that blocks on a gate pipe → verify the store against the journal (never recreate one that has history) → check
the choke → write the root edge → open the gate → the child execs. If the
supervisor dies or refuses, the gate closes and the command **never runs**.

**Containment.** Linux: a cgroup v2 child group; no delegation ⇒ refuse (exit 5). macOS: a process group; the
child gets the terminal foreground when there is one.

**`--user U` (DD-46, opt-in).** Needs root (`sudo`). The child drops to U (uid, gid, groups) before exec. The
supervisor then runs with the invoking user's effective ids (`SUDO_UID`), regaining root only to signal the
child. Refused when U is root or the invoking user, or when any ancestor of the state directory is owned by U or
writable by U (world-writable sticky directories excepted). State is written with the invoking user's ids under
`sudo`, with or without `--user`. The agent shares your terminal: where the kernel still allows `TIOCSTI`
and sudo does not allocate its own pty (`Defaults use_pty`), it could type into your shell (accepted limit).
Without `--user`, the agent runs as you and the store and lineage keys are **tamper-detected, not
protected** (DD-44). Consequences: an in-agent choke running as U cannot read the store and fails closed;
signalling such a run needs privileges (an M3 input). It is also what ADR-0012's macOS network cut requires.

**Escape detection** (every poll and once after the agent exits), each a `finding: lineage_gap`:

1. a descendant whose process group (macOS) or cgroup (Linux) differs from the run's;
2. a process carrying the run's `AGENTHALT_RUN_ID` outside the observed set (catches a double-fork between polls);
   only the environment is searched, and the process must be the run's user and no older than the run;
3. the run's liveness pipe still held after every observed member exited.

**Limit:** on macOS a child that double-forks between polls, clears its environment *and* closes inherited
descriptors is not seen. On Linux an unprivileged child with write access to a sibling cgroup (a delegated,
same-user hierarchy) can move out; the move is detected by (1), not prevented. `--user` prevents it.

**Exit status (DD-47).** `run` returns the agent's exit status (`128+N` for signal N), like any launcher. The
halt exit codes apply to halt commands, not to `run`. A refusal before launch is exit 5.

**Supervision never stops for a record failure.** If processes cannot be observed or the registry or journal
cannot be written, the supervisor keeps supervising, retries what it owes the record, and reports
`supervision degraded`.

**`attach --pid P`.** Only a process of the invoking user (anything else: exit 5, nothing enrolled). A process
already inside an enrolled run is recorded **under** that run, so attaching cannot shed a halt. Writes a
root edge with `lineage_verified: false`, walks descendants, and appends `verified` only if the walk saw
everything. Re-attaching the same process returns the existing run. `attach` creates no cgroup or group and does
not move the process.

## 8. Surface

`status` gains a lineage section (runs, orphans, gaps, tamper findings; also in `--json` under `lineage`).
`doctor` gains a `lineage` check (`fail` on a tamper finding). The `cgroup` check stays `warn`: it describes the
host, and `run` itself refuses where delegation is missing. This replaces the M0 note that M2 would promote it.

## 9. Test plan

| Area | Tests |
|---|---|
| chain | append-only, mid/newest/segment deletion, rebuild, rotation, forged and unauthenticated writes |
| graph | priority, dedup, conflict journaled once, orphans |
| resolver | 3 levels, 10 000-member flood, deadline expiry, observation failure, verified flag |
| choke | spawn mid-halt blocked for each scope kind, damaged lineage fails closed |
| supervisor | root before exec, gate closes ⇒ no exec, nested spawn refused, `setsid` and double-fork reported, supervisor killed, attach rules, `--user` refusals |
| Linux (container, root) | real cgroup containment and double-fork, real `--user` drop |

## 10. Not in M2

Suspend/kill, egress cut, grants, receipts, and the `tamper_lineage` halt itself (M3, M4, M6, M8).
