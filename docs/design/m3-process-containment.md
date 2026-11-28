# M3 design — Process-tree containment (executor core)

**Status:** self-reviewed 2026-11-27 (the macOS egress deferral, §7, decided by the owner) · **WBS:**
[M3](../wbs/v0.1.0/wbs-v0.1.0-part2-lineage-process.md) (#436) · **Bound by:**
[PRD 02](../prd/02-architecture.md), [PRD 18](../prd/18-stop-modes.md), [PRD 26](../prd/26-receipt-schema-and-examples.md),
[PRD 32](../prd/32-build-vs-integrate.md), [PRD 39](../prd/39-performance-budget.md) ·
[ADR-0003](../adr/0003-confirmations-not-requests.md), [ADR-0006](../adr/0006-snapshot-before-termination.md),
[ADR-0011](../adr/0011-status-precedence-and-attestation.md), [ADR-0012](../adr/0012-built-in-egress-fallback.md) ·
DD-01, DD-05, DD-23, DD-27, DD-39, DD-40, DD-45, DD-49..DD-52

M3 is the first milestone where a halt stops a running agent: it suspends, cuts the network where it can, and
kills. Credentials (M4), evidence (M5) and receipts (M6) are not here.

## 1. Modules

| Module | Responsibility |
|---|---|
| `agenthalt/executors.py` | the adapter contract, result validation, the registry, confirmation signing |
| `agenthalt/process_exec.py` | the process-tree executor (macOS and Linux) |
| `agenthalt/egress.py` | the built-in egress fallback (Linux) and its `unsupported` paths |
| `agenthalt/coordinator.py` | ordering, deadline, confirmations, outcome, release on lift |

## 2. Executor contract

An adapter declares `name`, `layer` (`process` / `sandbox`), `version` and `attestation`, and implements:

- `suspend(targets, ctx)`, `block(targets, ctx)`, `terminate(targets, ctx)`, `release(record, ctx)` — each returns
  a list of `Result(target, status, note, undo)`; an adapter implements the phases its layer has.
- `status` is `confirmed` / `requested` / `unsupported` / `failed`. There is no other value.

The coordinator, not the adapter, decides **what** to cut, in **which** order and under **which** mode: an
adapter receives targets and reports outcomes. It is never given the halt store and contains no policy.

**Validation.** An unknown adapter name, a missing attribute or a wrong layer is a `ConfigError` at load. At run
time a result with an unknown status becomes `failed`; a result for a target that was not asked (a child found
while stopping) is kept only if it carries a note; a target with no result becomes `requested`; an adapter that raises yields `failed` for all its targets. Third-party adapters
register through the `agenthalt.executors` entry-point group; a registered `sandbox` adapter (agentseatbelt,
agentkernel) takes precedence over the built-in one.

## 3. Order and deadline (DD-05, ADR-0006)

1. **Block** — the store write, synchronous. If it fails the outcome is `failed` and nothing else is claimed.
2. **Resolve** — target to members, from lineage.
3. **Cut, in parallel:** suspend the tree · cut the network (`quarantine`, `kill`).
4. **Evidence slot** — empty until M5; it sits here so termination can never move ahead of it.
5. **Terminate** (`kill`).
6. **Record** the confirmations and the outcome in the journal.

One deadline (`halt.deadline_ms`, default 1000, `--deadline-ms`) covers 2–5. What is not confirmed when it
expires is `requested`, even if it would have succeeded a moment later. A hung adapter cannot hold the halt:
each phase runs in a daemon thread. A third-party adapter is abandoned 2 s after the deadline; the built-in ones
have a longer hard cap (process 30 s, egress 10 s), because stopping halfway through a tree is worse than being
late. **Signals are sent even when the deadline has passed**; only `confirmed` depends on it. Resolving and
listing processes use their own timeouts.

State locks are waited for at most 2 s: the holder may be the process just frozen. If the lock needed for the
block cannot be had, the processes are **cut anyway** and the outcome is `failed`.

## 4. Process executor (DD-23)

**Targets** are `(pid, start)` pairs from lineage members, plus what the executor's own walk finds while
stopping. It loops (observe → stop what is new → observe) until a pass finds nothing new or time runs out, so a
child forked during the stop is caught.

**Safety rules, applied before every signal:**

1. The `(pid, start)` identity is re-read. A reused pid is not signalled. On Linux the signal goes through a
   pidfd opened before the re-read, which closes the race.
2. Never pid 0 or 1, never the halting process, never an ancestor of it (report `failed`: halt from outside).
3. Unless the invoking user is root, never a uid-0 process, and never another user's, except the `--user` uid of
   that run, believed only from a root-owned record (`keys/users/<run id>`). A forged lineage record therefore
   cannot aim `sudo agenthalt halt` at system processes or other people.
4. Never a process group or cgroup by number or path alone: members are signalled individually; a cgroup is
   used only if its path ends in `agenthalt-<that run id>` and does not contain the halting process.

Children found after the first stop are suspended too, and `kill` looks again after terminating. A process
that something continues during the stop is signalled again. A live member with no confirmation is a survivor.

**Suspend:** `SIGSTOP`; on Linux also `cgroup.freeze` for runs with their own cgroup (atomic against forks).
**Terminate:** `SIGKILL` (plus `cgroup.kill`). `kill` always suspends first.

**Confirmation** is observation, never the return of the signal call: suspend is `confirmed` when the process is
seen stopped or gone; terminate when it is gone or a zombie. Anything else is `requested`. Denied permission is
`failed`.

**Marker-only members** (found by `AGENTHALT_RUN_ID` alone, DD-50) are cut like any other, subject to the M2
checks (same user, no older than the run). Each result says how the member was found.

## 5. Confirmations (DD-40, DD-49)

Each result is signed by the executor key `<home>/keys/executor.key` (`0600`, HMAC-SHA256, never a coordinator
key) with `attestation: self` and `signed_by: agenthalt-executor`. **No signature ⇒ the `confirmed` is
downgraded to `requested`.** The scheme is provisional until 4.6 defines the key model; a verifier must treat it
as self-attestation, which anyone holding the key can produce.

## 6. Outcome

Precedence is DD-39. `failed`: blocking was not established. `incomplete`: any process result is `requested` or
`failed`, the member list is incomplete (unknown target, deadline, damaged lineage), or something still holds a
run's liveness handle. `partial-layer`: otherwise, when a layer is `unsupported`. In M3 `credentials` and
`gateway` are always `unsupported`, so the best outcome is `partial-layer` (exit 2).

Findings from M2 (`lineage_gap`) set `lineage_verified: false` in the output; a member that left its group is
still cut individually.

## 7. Egress fallback (DD-45, DD-51)

**Linux.** For each run with its own cgroup, `iptables` and `ip6tables` rules in `OUTPUT`, inserted first,
matching `-m cgroup --path <the run's cgroup>`: TCP is rejected with a reset, everything else rejected, each
rule tagged `agenthalt:<halt id>`. Verified in a privileged container: new connections are refused, an open
connection fails on its next send, nothing sent after the rule arrives, IPv4, IPv6, UDP and nested cgroups
included, and processes outside the cgroup are unaffected. `confirmed` means the rules were read back and every
live member of the run is inside the cgroup.

The ADR's `nft socket cgroupv2` form is **not** used: Docker Desktop's kernel lacks `nft_socket`.

**`unsupported`** when: not Linux · not root · `iptables`/`ip6tables` missing · the run has no cgroup of its own
(attached runs) · the path does not end in `agenthalt-<run id>`. Rules never match by user, so the operator's
network is never touched.

**macOS: `unsupported`.** The pf cut moves to 0.3.0 (DD-51, owner decision). `quarantine` on macOS is a freeze
without a network cut and reports `partial-layer`.

**Cleanup.** `kill` removes its rules once the members are confirmed gone; `quarantine` keeps them until `lift`.

## 8. The cut record, and lift (DD-52)

**Write-ahead.** Before each `SIGSTOP`, cgroup freeze or firewall insert, the intended change is appended to
`<home>/cuts/<halt id>.jsonl`. The file is append-only and takes no lock, so a crash, a timeout, a hung adapter or
a lift midway never loses what a halt changed.

`resume` is M9. Until then `lift` removes the halt and then releases what **that** halt recorded: its egress rules
(deleted by rule, never by position), its cgroup freeze and the processes it stopped, identity re-checked. A
process that was already stopped before the halt stays stopped. One that another active halt also covers stays
frozen and its record moves to that halt. If lineage cannot be trusted and other halts are active, nothing is
continued. For a `kill` the rules are removed and nothing is continued. What cannot be released stays recorded,
exits `1`, and **`lift` of the same id again retries it**. A halt lifted while it is still cutting is released at
once.

A `kill` removes its own rules only when there is no survivor **and** the member list is complete.

## 9. Re-raising (DD-27, DD-53)

An identical halt keeps the same id and **cuts again**: reporting an earlier success while the agent runs would
be worse than repeating a signal.

**Failure handling.** Only a failure to write the block is `failed` (exit 3). Any later trouble (resolving,
journaling, lifecycle) is reported as `incomplete` and does not stop the cut. A third-party adapter that cannot
load is a `ConfigError` at load; the CLI reports it and halts with the built-ins.

## 10. Privileges

A same-user run needs none. A `--user` run needs `sudo`. Under `sudo`, state is written with the invoking
user's ids (as in M2) and only signalling, observation and the firewall use root.

## 11. Supervisor

When its agent is frozen, `run` hands the terminal back and says so, and returns it on continue.

## 12. Test plan

Contract and registry load failures · identity re-check, ancestor and root refusals · suspend/kill of a real
tree, a fork during the stop, a process that ignores signals · deadline and hung adapter · unsigned downgrade ·
ordering (block before signal, evidence slot before terminate) · zero-hook fixture stops acting · lift release
and overlap · egress `unsupported` paths with a fake `iptables`; the real cut and real cgroup freeze/kill in a
privileged Linux container.

## 13. Limits

A process in uninterruptible sleep stays `requested`. Third-party adapters are loaded before the block is written
(as root under `sudo`), so a hanging import delays the halt. A `continued` result reports the signal, not an
observation. A halt run from inside the halted tree may not converge. Damaged lineage makes every later halt
`incomplete` until it is repaired. Between a pid check and a signal on macOS there is a small
reuse window. Without `--user`, an agent running as you can send itself `SIGCONT`, delete the executor key or
forge lineage; it cannot do so while stopped. Inbound packets still arrive under the egress cut; the replies do
not leave.
