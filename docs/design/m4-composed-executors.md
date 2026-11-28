# M4 design — Credential, gateway and sandbox executors

**Status:** self-reviewed 2026-11-27 (the gateway/kernel scope, §4, decided by the owner) · **WBS:**
[M4](../wbs/v0.1.0/wbs-v0.1.0-part3-executors-evidence.md) (#448) · **Bound by:**
[PRD 02](../prd/02-architecture.md), [PRD 26](../prd/26-receipt-schema-and-examples.md),
[PRD 32](../prd/32-build-vs-integrate.md), [ADR-0003](../adr/0003-confirmations-not-requests.md),
[ADR-0011](../adr/0011-status-precedence-and-attestation.md) · DD-18, DD-40, DD-54..DD-58

## 1. Scope

| Item | In this milestone |
|---|---|
| Credentials (4.1, 4.2) | real executor over `agentkeys revoke` |
| Gateway (4.3) | the adapter slot and the `unsupported` path; **`agentgate` does not exist yet** (DD-57) |
| Kernel kill trigger (4.4) | the `unsupported` path; **`agentkernel` does not exist yet** (DD-57) |
| Degradation matrix (4.5), signing (4.6) | complete |

## 2. Layers and order

`gateway`, `credentials`, `process` and `sandbox` cuts run **in parallel** inside the one deadline, after the
block is written (DD-05). Composed adapters register in the same `agenthalt.executors` group; phases are
`disconnect` (gateway), `revoke` and `freeze` (credentials). A registered adapter replaces the built-in of its
layer. An absent layer is `unsupported` without anything being called.

## 3. Credentials

**Inventory** is what each run declared at enrollment (`--grant`, DD-58): `agentkeys:session:<id>`,
`agentkeys:agent:<id>` or `static:<name>[@YYYY-MM-DD]`. Env-held keys are not discovered at v0.1.0.

| Mode | agentkeys grant | static key |
|---|---|---|
| `pause` | untouched | untouched |
| `quarantine` | `unsupported`: agentkeys has no issuance freeze | `unsupported`, listed |
| `kill` | `agentkeys revoke --session/--agent … --json` | `unsupported`, listed in `unrevocable_grants` |

`confirmed` means agentkeys exited 0 and reported at least one revocation, before the deadline. No answer in time
is `requested`; a denial or unknown target is `failed`. **Nothing declared is `unsupported`**, never a pass.
A revoke is irreversible: `lift` does not restore it. Under `sudo`, agentkeys runs as the person halting.

agentkeys does not sign, so these confirmations are `attestation: self` (DD-56): agenthalt vouches that agentkeys
said so.

## 4. Gateway and kernel

Without a registered adapter the gateway row is `unsupported` (DD-18), so a halt is at best `partial-layer`.
The slot is exercised with a test adapter; nothing here claims `agentgate` or `agentkernel` integration.

## 5. Signing (closes open decisions #10 and #13)

- **Ed25519, OpenSSH SSHSIG, via `ssh-keygen`** (DD-54): public-key verification with no runtime dependency.
  Namespace `agenthalt-confirmation`. The signed bytes are `{halt_id, layer, phase, target, status}`.
- **Executor key custody (#13):** `<home>/keys/executor_ed25519`, `0600`, created as the invoking user.
  Rotation: remove the key pair; the next halt creates one and **appends** its public half.
- **Publication (#10, DD-55):** `<home>/keys/published/<signer>.pub`, one key per line, old keys kept. A release
  attestation bundle ships third parties' files (M13).
- A third party's `confirmed` counts only if its signature verifies against its published file; otherwise it is
  `requested`.
- Without `ssh-keygen`, agenthalt's own confirmations fall back to HMAC (`agenthalt-executor-hmac`), which only
  the key holder can check; `doctor` warns.
- Confirmations are signed together after the cut, so signing is not on the stop path.

## 6. Degradation matrix (4.5)

| Layer state | Row status | Outcome |
|---|---|---|
| not deployed, or nothing declared to cut | `unsupported` | `partial-layer` |
| answered "refused" or errored | `failed` | `incomplete` |
| no answer by the deadline | `requested` | `incomplete` |
| `confirmed` without a verifiable signature | `requested` | `incomplete` |
| every layer confirmed | `confirmed` | `complete` |

Tested in `tests/test_composed.py`.

## 7. Limits

Grants are only what was declared; a forged or mistaken declaration can revoke a grant that was not this agent's.
Self-attestation proves who wrote a line, not that it is true, and an agent running as the operator can read the
executor key. `--all` revokes the declared grants of enrolled runs, not every session in agentkeys.
