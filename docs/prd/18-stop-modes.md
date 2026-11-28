# PRD 18 — Stop Modes

**BLUF:** agenthalt ships three stop modes on one escalation ladder: **`pause`** (freeze, resumable — the
everyday "stop moving"), **`quarantine`** (freeze + cut network — investigate without destroying), and
**`kill`** (terminate + revoke everything — emergency containment). The ladder maps onto the AI Kill Switch
Act's graduated framework (throttle → disable → suspend → shut down) and the NCSC's "more than stopping the
processes" clause. v0.1.0 ships all three rungs as explicit operator commands: `pause`/`resume` (R7), a basic
`quarantine`, and `kill`. R15 adds escalate-on-act and the auto-escalation defaults at v0.2.0 (see DD-13); the mode design is
fixed **now** so the store format and the journal vocabulary never break.

**Status:** Draft — v0.1.0 (2026-11-14) · **Owner:** @deghosal-2026 · **Parent:** agentic-suite #209 · PRD #216

## The ladder

| Mode | What stops | What survives | Resumable | The question it answers |
|---|---|---|---|---|
| **`pause`** | New actions blocked at the choke; the process tree is **suspended** (SIGSTOP / cgroup freeze), not terminated | Session state, context, open file handles, the sandbox | **Yes** — `resume` restores full context (R7, 24 h test) | "Stop moving; I need to look." |
| **`quarantine`** | Pause + **network cut** (sandbox egress block, or the built-in fallback; open connections fail on next send) + credential **freeze** (no new issuance) | Process, state, evidence — everything but its reach | Yes (explicit un-quarantine) | "It might be compromised; contain without destroying." |
| **`kill`** | Pause + quarantine cuts, then **terminate** the tree and **revoke** every grant (agentkeys) | Only the evidence snapshot and the receipt | No — recovery is rescope-and-restart | "Stop it, everywhere, now." |

## Semantics

- **One ladder, one vocabulary.** Each mode is a **strict superset** of the previous: `kill` ⊃ `quarantine` ⊃
  `pause` ⊃ `blocking`. The store records the mode; the choke enforces at least the blocking layer for every
  mode. Escalation (`agenthalt escalate --halt <id> --to quarantine`) is one command and a journaled step —
  never a fresh halt that loses the id chain.
- **Block-new-first, at every rung.** The synchronous part of every mode is the choke write; suspension,
  network cuts, and revocation fan out in parallel within the deadline (DD-05). "Pause" that leaves new actions
  flowing is not a pause.
- **Escalate-on-act (v0.2.0).** A paused or quarantined subtree that attempts an action auto-escalates:
  pause → quarantine on a network attempt, quarantine → kill on a tamper or kernel-kill signal. The attempt,
  the escalation, and the trigger are all journaled. A soft stop that orphans children is not safer — it just
  fails quieter ([PRD 01](01-why.md)).
- **Pause has a max TTL** (default 24 h). Expiry auto-escalates to `kill` with `reason_code=pause_expired` —
  pause-limbo (warm credentials, rotting state, RK-15) is a designed non-state.
- **Kill order is fixed:** block-new → suspend → cut network → snapshot completion → terminate → revoke →
  receipt. Evidence before termination, always (DD-10).
- **Mode history is journaled.** Every escalation, resume, and expiry is an entry; the receipt for a
  `kill` shows the full path (paused 02:31 → quarantined 02:33 → killed 02:35) — the responder's decision
  timeline is reconstructable (CUJ-6/9).

## What performs the network cut

agentseatbelt or agentkernel where deployed; otherwise agenthalt's built-in egress fallback (DD-45, labelled
`attestation: self`). Where the fallback lacks privileges or, on macOS, a dedicated OS user for the run, the
network row reports `unsupported` and the receipt is `partial-layer`. The mode never reports a network cut it
did not make.

## What each mode never claims

- **Pause** does not claim the agent is *contained* — it claims *frozen*. Open sockets persist until quarantine
  cuts them; the readout says which.
- **Quarantine** does not claim credentials are dead — they are frozen for new issuance; already-issued grants
  live until `kill` revokes them (or they expire). The readout states the residual window (CUJ-23).
- **Kill** does not claim undo — `compensation[]` records what already landed; recovery is rescope-and-restart
  (R13).

## Mode selection guidance (the runbook's first page)

| Situation | First move | Why |
|---|---|---|
| Uncertain, investigating, might resume | `pause` | Preserves everything; reversible; cheap |
| Suspected compromise, exfiltration, injection | `quarantine` | Cuts reach without destroying evidence |
| Active damage, prod mutation, credential theft | `kill` | The Replit case — stop everything now |
| Fleet-wide key compromise | `kill --all` (local CLI + typed confirmation at v0.1.0, DD-16; dual control v0.2.0) | One switch, every breaker, proven |

> **`pause` is the documented first move for the uncertain case; `kill` requires an explicit reason** (RK-20 —
> muscle memory must not destroy evidence by default).

## Regulatory mapping (why the ladder matters legally)

| Framework clause | agenthalt rung |
|---|---|
| H.R. 9917 "Throttling or otherwise altering" the inference rate | the blocking scope `writes-disabled` / `tool:<name>` (v0.2.0 scope vocabulary) |
| H.R. 9917 "Disabling or restricting a capability" | `quarantine` (network cut) + tool-scoped blocks |
| H.R. 9917 "Suspending" / NCSC "halt autonomous activity" | `pause` |
| H.R. 9917 "Shutting down" / NCSC "more than stopping the processes" | `kill` (terminate + revoke — the composed stop) |
| EU AI Act Art. 14 human-interrupt procedure | any rung, from the panic key/CLI by an authorized person, journaled with actor |

This is **alignment documentation**, not a compliance claim (RK-18; [PRD 20](20-standards-and-claims.md) §G).

## Open questions

- **Quarantine credential semantics** — freeze-issuance only, or also revoke-on-quarantine for high-risk grant
  classes? (Hypothesis: freeze at v0.2.0; per-class policy later.)
- **Escalate-on-act defaults** — pause→quarantine on *any* attempt, or only network/tamper classes? (Needs
  design-partner input; false escalations burn trust.)
- **Resume preconditions** — should `resume` require an explicit check (the readout re-run) or be unconditional?
  (Hypothesis: unconditional resume, readout printed as warning — the operator asked for it.)
