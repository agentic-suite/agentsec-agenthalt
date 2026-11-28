# Executors and halting

What a halt does to running processes, how to read the result, and what it does not do.
Design: [M3](../design/m3-process-containment.md).

## What each mode does

| Mode | Processes | Network (Linux, root, own cgroup) | Credentials, gateway |
|---|---|---|---|
| `pause` | frozen (`SIGSTOP`, plus the cgroup freezer on Linux) | untouched | gateway `unsupported` |
| `quarantine` | frozen | outbound rejected | `unsupported` in this version |
| `kill` | frozen, then `SIGKILL` | rejected, rules removed once everything is gone | `unsupported` in this version |

The order is fixed: **block new actions** (the halt is written to the store) → **suspend** and **cut the
network** → evidence slot (empty until M5) → **terminate** → record.

A halt cuts only processes enrolled with [`run` or `attach`](lineage.md) under the same state directory, and
their descendants. `--all` means every enrolled run there, not every process on the host.

## Reading the result

Each target of each layer is `confirmed`, `requested`, `unsupported` or `failed`.

- **`confirmed` is something observed:** the process was seen stopped or gone; the firewall rules were read back
  and every live member is inside the cgroup. A signal being sent is never enough.
- **`requested`:** not seen to take effect before the deadline (`--deadline-ms`, default 1000).
- **`failed`:** refused or errored; the note says why.

| Outcome | Exit | When |
|---|---|---|
| `partial-layer` | 2 | everything named was cut, but some layer is `unsupported`. **The best possible outcome in this version** |
| `incomplete` | 1 | a survivor, an unknown target, an unreadable member list, or anything `requested`/`failed` |
| `failed` | 3 | the block itself could not be written: stop the agent by hand |

`lineage not verified` means there may be processes the halt does not know about.

## Refusals

agenthalt never signals pid 0 or 1, the halt command itself or any of its parents (halt from outside the
agent's own process tree), and, unless the person halting is root, a root process or another user's (except the
`--user` account the run was launched as). Such a target is `failed`.

## Lift

`agenthalt lift` removes the halt, then removes the firewall rules **that halt** added and continues the
processes **that halt** froze. A process another active halt covers stays frozen; one that was already stopped
beforehand is left alone. Lifting a `kill` removes its rules but continues nothing.

Anything that could not be released is listed and exits `1`. **Run the same `lift` again to retry**, with `sudo`
if the halt used it. What each halt changed is recorded in `<home>/cuts/` before it is changed.

Raising an identical halt again keeps the same id and cuts again.

## If a state file is locked

A lock is waited for at most 2 seconds. If the halt cannot be written because something holds it (possibly the
agent), the processes are still cut, the command says `HALT FAILED` and exits `3`: new actions are **not**
blocked. `lift --halt <id>` undoes the cut.

## Privileges

| | Needs |
|---|---|
| Freeze or kill your own agent | nothing |
| Halt an agent launched with `run --user` | `sudo` |
| The Linux network cut | `sudo`, `iptables` and `ip6tables`, and a run launched with `run` (its own cgroup) |

`agenthalt doctor` reports the adapters in use and whether the network cut is available.

**macOS has no network cut** in this version (planned for 0.3.0): `quarantine` freezes only and says
`unsupported`.

## Confirmations

Each is signed with `<home>/keys/executor.key` and marked `attestation: self`: agenthalt is vouching for its own
cut. The scheme is provisional until the key model of M4.

## Writing an adapter

Register a factory in the `agenthalt.executors` entry-point group. The object needs `name` (equal to the entry
point name), `layer` (`process` or `sandbox`), `version`, `attestation`, at least one of `suspend` / `block` /
`terminate`, and `release`. It replaces the built-in adapter of its layer. A `third_party` adapter must return
its own signature or its `confirmed` is recorded as `requested`. An adapter that fails to load is reported by
`doctor`, and `halt` carries on with the built-ins rather than not halting.

## Limits

- Without `run --user`, the agent runs as you: while running it can continue itself, or tamper with the state.
- A process in uninterruptible sleep stays `requested`.
- On macOS, a child that detaches completely between polls can go unseen (see [lineage](lineage.md)), and there
  is a very small pid-reuse window between the identity check and the signal.
- The network cut rejects outbound traffic only.
- Empty `agenthalt-run_*` cgroup directories can be left behind after a kill.

## Credentials

Declare what an agent holds when you enroll it:

```sh
agenthalt run --name release-bot \
  --grant agentkeys:agent:release-bot --grant static:GH_PAT@2026-12-01 -- ./agent
```

`kill` runs `agentkeys revoke` for each `agentkeys:` grant; this cannot be undone. A `static:` key cannot be
revoked from here and is listed as `UNREVOCABLE` with how long it stays usable. `quarantine` reports credentials
`unsupported` (agentkeys has no freeze yet); `pause` leaves them alone. With nothing declared the layer is
`unsupported`.

## Gateway

`agentgate` is not available yet: the gateway row is always `unsupported` unless an adapter is registered.

## Degradation matrix and signatures

An absent layer is `unsupported` (`partial-layer`); a layer that fails or does not answer makes the halt
`incomplete`; `complete` needs every layer confirmed. Confirmations are Ed25519-signed with `ssh-keygen`; public
keys are in `<home>/keys/published/`. Details: [M4 design](../design/m4-composed-executors.md).
