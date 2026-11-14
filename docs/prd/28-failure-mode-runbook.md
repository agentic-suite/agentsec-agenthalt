# PRD 28 — Failure-Mode Runbook

**BLUF:** This is the operator's survival doc — what to do when the stop itself is the thing that's broken.
For every failure mode: the symptom, the immediate action, the per-layer **manual fallback commands** (what you
run if agenthalt is down entirely), the escalation path, and the post-incident checklist. It ships with the
tool (`docs/runbooks/` + `agenthalt runbook --print`), because a kill switch whose fallback is "read the PRD"
is a liability. The store being down must never mean the fleet can't be stopped.

**Status:** Draft — v0.1.0 (2026-11-14) · **Owner:** @deghosal-2026 · **Parent:** agentic-suite #209 · PRD #216

## Triage table (symptom → section)

| Symptom | Go to |
|---|---|
| `agenthalt doctor` reports store unreachable | §1 |
| Receipt says `incomplete` / lists survivors | §2 |
| A descendant is still acting after a `complete` receipt | §2 (severity: incident) |
| Receipt says `partial-layer` (gateway/other unsupported) | §3 |
| Credentials still valid after a `kill` | §4 |
| `evidence: failed` on the receipt | §5 |
| A trigger fires that nobody sent / a halt you can't explain | §6 |
| agenthalt itself won't start or respond | §7 (manual fallback) |

## §1 — Halt store down

- **Behavior by design:** the choke **denies high-impact actions** (`reason_code=halt_store_unavailable`) — the
  fleet is *slower*, not *unstoppable* (CUJ-16).
- **Action:** `agenthalt doctor` → fix the store (disk, permissions, lock) → re-run `doctor` → verify a drill.
- **If the store can't be restored:** run §7's manual fallback for the affected agents — do not wait on the
  control plane to reappear.

## §2 — `incomplete` receipt / a survivor

- **Read the receipt:** `survivors[]` names ids, last-seen, and *why* (lineage gap / deadline / layer failure).
- **Immediate action:** re-halt the survivor by explicit target (`agenthalt kill --run <id>`) — explicit-id
  halts don't depend on lineage resolution.
- **If the survivor is unreachable by every layer:** the readout's `uncovered_routes` tells you where it can
  still act; cut those paths manually (network policy, vendor console) and record it.
- **Never:** edit the receipt or journal to "resolve" it (tamper — RK-11); the incomplete record **is** the
  incident evidence.
- **Severity:** a survivor observed *acting* post-halt is a Sev-1 and a release-blocker for the drill
  (RK-2/RK-16); file the miss with the drill output attached.

## §3 — `partial-layer` (a composed layer absent)

- **Meaning:** the stop completed everywhere except the named layer (Wave-0 default: no agentgate — DD-18).
- **Action:** compensate manually for the missing cut — e.g., without the gateway: firewall the agent's
  egress at the host/network layer; without agentkeys: revoke in the vendor console and note the residual
  window.
- **Follow-up:** install the missing layer (it composes automatically); re-run the drill.

## §4 — Credentials still valid after `kill`

- **Read `readout.unrevocable_grants[]`** — static keys and vendor grants outside agentkeys' reach are
  **expected** residue, listed with expiry windows (CUJ-5, E14); rotate them in the vendor console.
- **If an agentkeys-issued grant is still valid:** that's a `failed`/`requested` confirmation — check the
  confirmation's note; re-run `agenthalt kill --agent <id>` (idempotent for unconfirmed targets) or revoke
  directly via agentkeys.
- **Record** the residual window in the incident log — the receipt already did; your rotation closes it.

## §5 — Evidence failure (`evidence: failed`)

- **Behavior by design:** the stop completed; evidence collection degraded loudly; nothing was cancelled
  ([PRD 13](13-non-functional-requirements.md) — evidence is a side effect, not a gate).
- **Action:** for `pause`/`quarantine` runs — collect manually *now* (the process is still frozen, the scene
  is intact): `agenthalt evidence collect --halt <id> --retry`. For `kill` — salvage what the layers still
  hold (agentwatch window, process lists) and note the gap.
- **Never:** re-kill to "get evidence" — a second kill destroys what the first left.

## §6 — Unexplained / spoofed trigger

- **Immediate:** `agenthalt journal show --halt <id>` — actor, channel, signature, replay window.
- **If the trigger is illegitimate:** `agenthalt lift --halt <id> --reason "spoofed trigger"` (journaled), then
  rotate the trigger's credentials (HMAC key, PagerDuty/Slack tokens) — a spoofed trigger means a key leak
  (RK-5).
- **If you can't lift** (store suspect): §7 manual fallback for the affected agents, then rebuild the store
  from the journal segments (chain-verified).

## §7 — Manual fallback (agenthalt itself down)

The layer commands an operator runs **directly**, per layer — the runbook prints these for the deployed stack:

| Layer | Manual command (example form) |
|---|---|
| Process (macOS) | `pkill -STOP -g <pgid>` (freeze) · `pkill -TERM -g <pgid>` then `-KILL` (terminate) |
| Process (Linux) | `systemd-run`/cgroup freeze: `echo FROZEN > /sys/fs/cgroup/<agent>/cgroup.freeze` · kill: `systemctl kill --signal=KILL <agent-scope>` |
| Credentials | `agentkeys revoke --grant <id>` (agentkeys is a separate process) or the vendor console |
| Gateway | `agentgate session terminate --session <id>` or drop the agent's routes at the proxy |
| Sandbox/network | host firewall: `pfctl`/`iptables` block by uid/cgroup; sandbox profile re-apply |
| Everything | if only `kill -9` remains: kill the **process group**, then immediately rotate every credential the agent held and collect evidence by hand — and know that SIGKILL alone is the switch that empties nothing ([PRD 01](01-why.md)) |

> Manual fallbacks are **tested drill legs** (adversarial pack case: "control plane dead, fleet still
  stoppable"), not documentation decoration.

## Escalation tree

1. **Responder** — triage table → section action; everything is journaled either way.
2. **agenthalt maintainer / security on-call** — any §2 survivor, §6 spoof, or §7 dependency (these are
   product-defect classes first, ops problems second).
3. **Disclosure** — a confirmed stop-suppression or receipt-forgery path → private disclosure (PRD 06) with
   the fallback runbook attached to the advisory.

## Post-incident checklist

- [ ] Receipt(s) exported + `prove` output pasted into the incident record
- [ ] Survivors/residuals closed (explicit-id halt, rotations, manual cuts) — or accepted with windows noted
- [ ] Journal segment archived; chain verified
- [ ] Compensation list handed to the system owners (what already landed is *their* backlog — R13)
- [ ] A drill re-run on the affected stack before the incident closes
- [ ] If any §2/§6 event: file the miss (product defect) with the drill output; release-blocker review
