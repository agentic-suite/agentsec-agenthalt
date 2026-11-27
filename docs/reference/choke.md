# The choke and the fail-closed contract

The choke is what a runtime (and, from Wave 1, the gateway) calls **before every action** (R8, ADR-0002).
Implemented in [`src/agenthalt/choke.py`](../../src/agenthalt/choke.py) and
[`src/agenthalt/reasons.py`](../../src/agenthalt/reasons.py); design in
[M1 design §4, §5, §9](../design/m1-halt-store-choke.md).

## Calling it

```python
from agenthalt.choke import DualChoke, RuntimeChoke
from agenthalt.scopes import Target
from agenthalt.store import Store

choke = DualChoke(RuntimeChoke(Store(home), cache_ttl_s=2))
decision = choke.check(Target(agent="release-bot", run="r1", ancestors=("r0",), tool="shell",
                              writes=True, impact="high"))
if not decision.allow:
    refuse(decision.reason)        # e.g. ReasonCode.HALTED, with decision.runtime.halt_id / .mode
```

`Target` fields: `agent`, `run`, `session`, `tenant`, `ancestors` (the lineage chain you know), `tool`, `writes`,
`impact` (`high` | `low`, **default `high`**), `lineage_known` (default `True`). Unclassified actions are high-impact.

`Decision`: `status` (`allow` · `deny` · `unsupported`), `layer`, `reason`, `halt_id`, `mode`, `latency_ms`.
`DualDecision` carries both layers (`.runtime`, `.gateway`, `.layers`) and the combined `.allow` / `.reason`.

## Freshness

Every check `stat()`s the store (microseconds). A new halt or a lift is visible on the **next** check — well inside
the ≤ 50 ms choke budget ([PRD 39](../prd/39-performance-budget.md)), regardless of the cache TTL. The TTL
(`choke.cache_ttl_s`, 0–59, *seconds, never minutes*) only bounds how long an unchanged copy is trusted.

## Decision rules

1. Store unreachable or corrupt → **deny high-impact**; low-impact allowed with the reason attached.
2. An active halt matches the target → **deny**, any impact. When several match, the **strictest mode wins**
   (DD-43): a narrow `pause` never weakens a fleet `kill`.
3. No halt matches but `lineage_known=False` → deny high-impact (`lineage_gap`): a subtree halt cannot be ruled out.
4. Otherwise → allow.
5. **Any exception inside the choke → deny everything** (`adapter_failed`, ADR-0004).

## The gateway half

`GatewayChoke` is a protocol (`name`, `available()`, `check(target)`). Until agentgate ships (Wave 1) the default
is `AgentgateStub`, which answers `unsupported` with `layer_unsupported` in ≤ 1 ms (DD-18). `DualChoke` allows only
if the runtime allows **and** the gateway allows or is `unsupported` — and always reports both layers, so an
unsupported gateway is visible, never silently skipped. A failing gateway adapter denies.

## Reason codes

| Code | Meaning | Denies | Fail-closed |
|---|---|---|---|
| `halted` | an active halt covers the target | all | — |
| `halt_store_unavailable` | the store is missing or unreadable | high-impact | ✓ |
| `store_integrity` | the store is corrupt, truncated, or inconsistent with the journal | high-impact | ✓ |
| `adapter_failed` | the choke or an adapter raised | all | ✓ |
| `lineage_gap` | the target's lineage could not be established | high-impact | ✓ |
| `layer_unsupported` | a composed layer is absent — reported, not a decision | — | — |

Codes are additive: never renamed, never reused. Every fail-closed path has its own code, and a fuzzed failure
matrix (`tests/test_failclosed.py`) proves none of them ever allows a high-impact action.
