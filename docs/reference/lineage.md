# Lineage and enrollment

How a run enters agenthalt, how its descendants are tracked, and what is and is not guaranteed.
Design: [M2](../design/m2-lineage-enrollment.md). **Nothing here suspends or kills anything** (M3).

## Enrolling

```bash
agenthalt run --name release-bot -- claude            # launch under the supervisor
sudo agenthalt run --user agentbot -- ./agent.sh      # ...as a separate OS user
agenthalt attach --pid 4242 --name release-bot        # enroll something already running
```

`run` records the root edge and checks the choke **before** the command executes. A halted agent name, `all`,
or a halted enclosing run refuses the launch. `run` returns the agent's own exit status (`128+N` for a signal);
a refusal is exit `5` and the command never runs.

| | Linux | macOS |
|---|---|---|
| Containment | a cgroup v2 child group; **refused** without delegation (try `systemd-run --user --scope`) | a process group |
| Daemonized child | stays in the cgroup | reported as `lineage_gap` |

`attach` accepts only your own processes; one that is already inside a run is recorded under that run. It reports `lineage_verified: false` until a full walk succeeds, and
does not move the process into any group.

### `--user`

Opt-in, needs `sudo`. The agent runs as that user; the halt state is written as you. It refuses root, yourself,
and a state directory whose parent that user owns or anyone can write. The agent cannot read the halt store, so a
choke running inside the agent denies high-impact actions. Put the state directory and the program somewhere that
user cannot modify. The agent shares your terminal, so keep sudo's `use_pty` on.

A launch is also refused when the halt store disagrees with the journal, or when the lineage is damaged while a
halt is armed.

## Edges

Each edge is `parent_run → child_run` with a `spawn_source`, a `recorded_at` and a `chain_hash`, in
`<home>/lineage/seg-NNNNNN.jsonl`. Records are chained, authenticated with a per-adapter key, and the head is
checkpointed in the [journal](journal-format.md).

- **Union for existence:** an edge from any authenticated source enters the graph.
- **Priority for parentage:** `process` > `runtime` > `hook`. A disagreement is journaled as `lineage_conflict`.
- **Orphans** (parent unknown) are listed by `status`. They are never killed and never dropped.

## The post-halt spawn rule

A child of a halted run is denied even if enumeration never saw it: the check covers the run **and every
ancestor**. Runtimes call `check_lineage(choke, graph, run)`; if the lineage cannot be established, high-impact
actions are denied with `lineage_gap`. A refused launch is journaled as `post_halt_spawn`.

## Findings

| Finding | Meaning |
|---|---|
| `lineage_gap` | a descendant left the run's group or cgroup, was found only by its run id, something still holds the run's liveness handle, or supervision was degraded |
| `lineage_conflict` | two sources disagree on parentage |
| `post_halt_spawn` | a spawn was refused because of a halt or unknown lineage |
| `supervisor_lost` | the supervisor is gone while its agent lives |
| `exec_failed` | enrolled, but the command could not execute |
| `forged_edge_refused` | a write that did not authenticate |
| `tamper_lineage` | an edge was deleted, edited, reordered or replaced; M8 turns this into a halt |

`agenthalt status` shows runs, orphans, gaps and tamper findings; tampering makes it exit `1`, and
`agenthalt doctor` fails its `lineage` check.

## Resolving a subtree

`Resolver.resolve("run" | "agent" | "all", value, deadline_ms=...)` returns members, orphans, gaps,
`complete` and `lineage_verified`. It walks recorded edges and live processes under one deadline; out of time or
unable to list processes means `complete: false`, never a hang and never an empty success. `grants_status` is
`unavailable` until agentkeys is composed (M4).

## Limits

- Without `--user`, the agent runs as you and can read the store and adapter keys: tampering is detectable, not
  prevented.
- Enumeration is best-effort. On macOS a child that double-forks between polls, clears its environment **and**
  closes inherited descriptors is not seen.
- On Linux, a same-user child with write access to a sibling cgroup (a delegated hierarchy) can move out of the
  run's cgroup. The move is detected, not prevented. `--user` prevents it.
- An agent that puts its own subprocesses in new process groups (job-control shells, some tool runners) shows
  `lineage_gap` findings on macOS and is reported `lineage_verified: false`.
- The `AGENTHALT_RUN_ID` marker can be set by any process of the same user, so membership found only that way is
  weaker evidence than ancestry or containment.
