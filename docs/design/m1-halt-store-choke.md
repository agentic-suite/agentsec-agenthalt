# M1 design — Halt store, dual choke & fail-closed

**Status:** reviewed 2026-11-27 (decisions confirmed by the owner) · **WBS:** [M1](../wbs/v0.1.0/wbs-v0.1.0-part1-foundation-store.md) (#412) · **Bound by:**
[PRD 02](../prd/02-architecture.md), [PRD 13](../prd/13-non-functional-requirements.md),
[PRD 15](../prd/15-data-model.md), [PRD 39](../prd/39-performance-budget.md) ·
[ADR-0001](../adr/0001-out-of-band-halt-store.md), [ADR-0002](../adr/0002-dual-choke-enforcement.md),
[ADR-0004](../adr/0004-fail-closed-over-fail-open.md), [ADR-0010](../adr/0010-self-tamper-triggers-v010.md) ·
DD-02, DD-03, DD-05, DD-18, DD-27, DD-36

M1 delivers the safety spine: the **halt store** (the single source of stop truth), the **choke** that every
runtime and gateway consults before acting, and the **fail-closed** contract with distinct reason codes. After M1
a halt can be *recorded* and *enforced at the choke*. Nothing is suspended, revoked or killed yet — that is M3–M4.

## 1. Modules

| Module | Responsibility |
|---|---|
| `agenthalt/scopes.py` | `Scope` parsing/matching, `Target` (the thing asking to act), `Mode` ordering |
| `agenthalt/reasons.py` | the reason-code registry (fail-closed and deny reasons) |
| `agenthalt/store.py` | `HaltState` records, the store file, atomic writes, rebuild from the journal, health + integrity |
| `agenthalt/choke.py` | `RuntimeChoke` (store read + cache), `GatewayChoke` protocol + agentgate stub, `DualChoke` |
| `agenthalt/coordinator.py` | raise / lift with idempotency, scope composition, the halt lifecycle |

## 2. Scopes and targets

A **scope** names what a halt covers. Parsed from a string, validated (`ids.validate_id` on every id):

| Scope | String | Matches a target when |
|---|---|---|
| global | `all` | always |
| tenant | `tenant:<id>` | `target.tenant == id` |
| agent | `agent:<id>` | `target.agent == id` |
| subtree | `subtree:<run>` | `run` is `target.run` or in `target.ancestors` |
| run | `run:<id>` | `target.run == id` |
| session | `session:<id>` | `target.session == id` |
| tool | `tool:<name>` | `target.tool == name` (soft scope) |
| writes | `writes-disabled` | `target.writes is True` (soft scope) |

A **target** is what asks the choke for permission: `Target(agent, run, session, tenant, ancestors, tool,
writes, impact)`. `ancestors` is the lineage chain the caller knows; M2 fills it from the lineage registry, so in
M1 a `subtree` halt reaches descendants only when the caller supplies their ancestry. `impact` is `high` or
`low`, **default `high`** — an unclassified action is treated as high-impact (fail-closed).

**Modes** order `pause` < `quarantine` < `kill` (PRD 18: each is a superset of the one before).

## 3. The halt store

**Format.** One JSON file, `<home>/store/state.json` (`0600`, dir `0700`), schema `agenthalt.store.v1`:

```json
{ "schema": "agenthalt.store.v1", "generation": 7, "journal_seq": 41,
  "journal_head": "sha256:…", "halts": [ <HaltState>, … ] }
```

`HaltState` = `{ halt_id, scope, mode, status, actor, reason, set_at, ttl_s, journal_seq }` (PRD 15). Only **active**
halts live here (`pending`, `blocking`, `executing`, `finished` — not `lifted`). History is the journal's job, so
the store stays small and a read stays cheap. That is what "rotation" means for the store: lifted halts leave the
live file and remain in the journal for ever.

**The store is a materialised view of the journal.** Every mutation is **journal-first** (PRD 16):

1. take the store lock (`store/.lock`, `flock`),
2. append the journal entry (`raise` / `lift` / lifecycle `execute`/`complete`) whose payload carries the full
   `HaltState` and the next `generation`,
3. write `state.json.tmp`, `fsync`, `rename` over `state.json`, `fsync` the directory — atomic replace, so a
   reader never sees a half-written file,
4. release.

Because the journal holds every state change, the store can always be **rebuilt** from it (`Store.rebuild()`).
A crash between steps 2 and 3 leaves the store one generation behind the journal; that is a *recovery* case,
not tampering (§6).

**Writes are authenticated by position, not by password.** Only agenthalt code paths running as the store
owner write the store, and every write is committed to the journal, so an out-of-band edit is detectable
(§6). Running the agent under a separate OS user — so it cannot even open the file — is the structural fix and
arrives with enrollment (M2, ADR-0009). M1 states this as a residual risk rather than claiming more.

## 4. The choke (runtime half)

`RuntimeChoke.check(target) -> Decision`:

```
Decision(allow: bool, reason: ReasonCode | None, halt_id: str | None, mode: Mode | None,
         layer: "runtime", latency_ms: float)
```

**Read path.** `stat()` the store file on every check (microseconds). If `(inode, mtime_ns, size)` is unchanged and
the cached copy is younger than `choke.cache_ttl_s`, use the cache; otherwise re-read and re-parse. So:

- a new halt is visible on the **next** check — the stat sees the rename — well inside the ≤ 50 ms budget
  (PRD 39), not after the TTL;
- the TTL (seconds, never minutes) only bounds how long an unchanged copy is trusted, guarding against coarse
  filesystem timestamps;
- the cache never outlives a store that has become unreachable: a failing `stat()` is treated as unreachable
  immediately.

**Decision rules:**

1. Store unreachable, unreadable, or corrupt → `high` impact **denied** (`halt_store_unavailable` /
   `store_integrity`); `low` impact allowed with the reason attached, so the caller can log it.
2. Otherwise, collect every active halt whose scope matches the target. None → allow.
3. Any match → **deny**, with the strictest mode among the matches and that halt's id (§7). A halt denies every
   action in its scope regardless of impact; `impact` only matters when the store itself is down.

**Exceptions inside the choke are a deny**, never an allow (ADR-0004): `check()` catches everything, returns a
deny with `adapter_failed`, and logs it.

## 5. The gateway half and the dual choke

`GatewayChoke` is a protocol: `name`, `available() -> bool`, `check(target) -> Decision`. M1 ships
`AgentgateStub`: `available()` is `False`, and `check()` returns a decision with `status="unsupported"` and reason
`layer_unsupported` — an unsupported layer neither allows nor denies, it reports. It answers in ≤ 1 ms (PRD 39).

`Decision` therefore carries a `status` of `allow`, `deny` or `unsupported` (with `allow` as a derived boolean).

`DualChoke(runtime, gateway).check(target)` returns a `DualDecision` holding both layer decisions and the
combined verdict:

- combined **allow** only if the runtime allows **and** the gateway allows or is `unsupported`;
- the result always lists both layers, so an `unsupported` gateway is visible to the caller and to the receipt
  (`partial-layer`, DD-18) — never silently skipped.

## 6. Health and the integrity signal (input contract for 8.2)

`Store.health() -> StoreHealth(status, signal, detail)` where `status ∈ {ok, unavailable, recovering}` and
`signal ∈ {None, "unreachable", "truncated", "head_mismatch"}`.

| Situation | Journal says a halt is armed? | Result |
|---|---|---|
| file present, parses, generation and head match the journal | — | `ok`, no signal |
| file missing / unreadable | no | `unavailable`, **no** signal (a planned restart with nothing armed is a health event) |
| file missing / unreadable | yes | `unavailable`, signal `unreachable` |
| file truncated / unparsable | yes | signal `truncated` |
| store generation **behind** the journal, journal intact, every journal entry after the store's seq is a store mutation | either | `recovering` — rebuild from the journal, no signal |
| store head/generation matches **no** journal entry, or store content differs from the journal-derived state | either | signal `head_mismatch` |

"Armed" is computed from the **journal** (replaying it), not from the store — the agent cannot hide an armed halt
by deleting the store. The signal is the input M8.2's `tamper_store` trigger consumes; M1 produces it, logs it,
and surfaces it in `status` and `doctor`. It does not raise a halt itself.

## 7. Coordinator: idempotency, composition, lifecycle

**Lifecycle** (`HaltLifecycle`): `pending → blocking → executing → finished`, or `→ lifted` from any of them.
**Outcome** (`ReceiptStatus`, M0) is a separate type and never stored in the lifecycle field (PRD 15).
Transitions are validated (`pending→executing` is refused) and each is journaled. Each transition is a
**compare-and-set under the store lock** (`Store.transition`, refined in review 1.CR): a stale writer cannot
resurrect a lifted halt or skip a state.

In M1 a raise runs `pending → blocking` (store written: the choke now denies) `→ executing → finished`. There
are no executor layers yet, so `executing` attempts nothing and the outcome is computed honestly from what exists:
blocking was established at the runtime choke, nothing was suspended, and the gateway is `unsupported`. With no
lineage or process layer there is no member list to confirm, so the outcome is **`incomplete`** (exit 1) — never
`complete`.

**Idempotency (DD-27).** A raise whose `(scope, mode)` equals an active halt returns **that** halt (same id, no new
store generation); the duplicate is journaled as a `finding` (`duplicate_raise`) so it stays visible. A raise
during `blocking` therefore returns the same halt id.

**Composition.** Different halts coexist. When several match a target, the **strictest mode wins** and a tighter
scope can add a restriction but never loosen one. Example: `all=pause` + `agent:x=kill` ⇒ `agent:x` is under `kill`,
everyone else under `pause`. (DD-43 — PRD 13's "a tighter scope wins within its subtree" read
literally could let a narrow `pause` weaken a fleet `kill`.)

**Lift.** `lift(halt_id, actor, reason)` requires a reason, journals `lift`, removes the halt from the store. Lift
during `executing` is allowed and journaled; the receipt (M6) records that it was lifted mid-flight.

## 8. CLI in M1

- `status [--halt ID] [--json]`: live halt state from the store, plus store health and the integrity signal.
- `lift --halt ID --reason TEXT`: lifts (exit 0), unknown id → exit 5.
- `halt` / `pause` / `quarantine` / `kill`: record the halt and enforce it at the runtime choke; print what was
  and was not done; exit **1**. Fleet confirmation and kill-requires-reason (M0) still apply.

## 9. Reason codes (`reasons.py`)

| Code | Meaning | Choke result |
|---|---|---|
| `halted` | an active halt matches the target | deny |
| `halt_store_unavailable` | store missing / unreadable | deny high-impact |
| `store_integrity` | store corrupt, truncated, or inconsistent with the journal | deny high-impact |
| `adapter_failed` | the choke or an adapter raised | deny |
| `lineage_gap` | the caller could not establish the target's lineage (M2 sets it) | deny high-impact |
| `layer_unsupported` | a composed layer is absent (agentgate in Wave 0) | neither — reported |

Codes are a registry (code, description, decision); a test asserts every fail-closed path maps to a distinct code.

## 10. Tests (1.T)

`test_scopes.py` (parse/match/order, id validation) · `test_store.py` (persistence across restart, atomic write,
rebuild, health/signal table every row) · `test_choke.py` (≤ 50 ms visibility, TTL enforcement, stat-change
invalidation, unreachable ⇒ deny high/allow low, exception ⇒ deny, dual choke with the stub) ·
`test_coordinator.py` (idempotency, duplicate during blocking, composition strictest-wins, lifecycle exhaustive,
lift, concurrent raises from processes) · `test_failclosed.py` (fuzzed matrix: every failure injection denies,
each with a distinct code) · CLI tests for `status` / `lift`.

## Decisions (confirmed in review)

- **DD-43 — composition:** strictest mode wins; a tighter scope adds restrictions, never loosens (§7).
- **M1 `halt` CLI:** `halt`/`pause`/`quarantine`/`kill` record the halt (journal + store) so the runtime choke
  enforces it, then exit **1 (`incomplete`)** and say plainly that nothing was suspended or revoked yet (§7, §8).
- **DD-44 — store trust:** same-OS-user store with journal-anchored tamper detection in M1; OS-user separation with
  enrollment (M2). Recorded as a residual risk in PRD 30 (§3).
