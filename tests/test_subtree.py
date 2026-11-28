"""2.3 / 2.4 / 2.5 (#427-#429): graph rules, the resolver and the post-halt spawn rule."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from agenthalt.choke import RuntimeChoke
from agenthalt.coordinator import Coordinator
from agenthalt.journal import Journal
from agenthalt.reasons import ReasonCode
from agenthalt.scopes import Mode, Scope
from agenthalt.store import Store
from agenthalt.subtree import Graph, Resolver, check_lineage, lineage_target
from tests.lineage_helpers import FakeObserver, adapters, edge, make_registry, proc, root


def build(home: Path, *edges: dict, source: str = "process"):  # type: ignore[type-arg,no-untyped-def]
    reg = make_registry(home)
    creds = adapters(reg)
    if edges:
        reg.append_edges(creds[source], list(edges))
    return reg, creds


def findings(home: Path, kind: str) -> list[dict]:  # type: ignore[type-arg]
    return [e["payload"] for e in Journal(home).entries() if e["payload"].get("finding") == kind]


THREE_LEVELS = (
    root("run_a"),
    edge("run_a", "run_b"),
    edge("run_b", "run_c"),
    root("run_z", "other"),
)


def test_resolves_a_three_level_subtree(tmp_path: Path) -> None:
    reg, _ = build(tmp_path, *THREE_LEVELS)
    tree = Resolver(reg, FakeObserver()).resolve("run", "run_a")
    assert tree.members == ("run_a", "run_b", "run_c")
    assert tree.complete and tree.lineage_verified
    assert tree.grants == () and tree.grants_status == "unavailable"


def test_agent_and_all_targets(tmp_path: Path) -> None:
    reg, _ = build(tmp_path, *THREE_LEVELS)
    resolver = Resolver(reg, FakeObserver())
    assert resolver.resolve("agent", "other").members == ("run_z",)
    assert len(resolver.resolve("all").members) == 4


def test_unknown_target_is_incomplete_not_empty_success(tmp_path: Path) -> None:
    reg, _ = build(tmp_path, root("run_a"))
    tree = Resolver(reg, FakeObserver()).resolve("run", "run_nope")
    assert not tree.complete and not tree.lineage_verified
    assert "unknown target" in (tree.reason or "")
    with pytest.raises(ValueError):
        Resolver(reg, FakeObserver()).resolve("galaxy", "x")


def test_grants_come_from_a_source_when_there_is_one(tmp_path: Path) -> None:
    reg, _ = build(tmp_path, *THREE_LEVELS)
    tree = Resolver(reg, FakeObserver(), grants=lambda members: ["g:" + members[0]]).resolve(
        "run", "run_a"
    )
    assert tree.grants == ("g:run_a",) and tree.grants_status == "listed"


def test_live_descendants_are_discovered_and_recorded(tmp_path: Path) -> None:
    reg, _ = build(tmp_path, root("run_a", pid=100, start="1000", pgid=100, uid=501))
    seen = FakeObserver()
    seen.add(proc(100, 1), proc(101, 100, pgid=100), proc(102, 101, pgid=100), proc(900, 1))
    tree = Resolver(reg, seen).resolve("run", "run_a")
    assert tree.members == ("run_a", "proc_101_1010", "proc_102_1020")
    assert [e.parent_run for e in reg.read().edges[1:]] == ["run_a", "proc_101_1010"]
    assert len(Resolver(reg, seen).resolve("run", "run_a").members) == 3
    assert len(reg.read().edges) == 3  # recorded once


def test_observation_failure_is_incomplete(tmp_path: Path) -> None:
    reg, _ = build(tmp_path, root("run_a", pid=100, start="1000"))
    tree = Resolver(reg, FakeObserver(fail=True)).resolve("run", "run_a")
    assert not tree.complete and tree.members == ("run_a",)


def test_enumeration_flood(tmp_path: Path) -> None:
    reg, _ = build(tmp_path, root("run_a"), *[edge("run_a", f"run_{i}") for i in range(10_000)])
    started = time.monotonic()
    tree = Resolver(reg, FakeObserver()).resolve("run", "run_a", deadline_ms=20_000)
    assert tree.complete and len(tree.members) == 10_001
    short = Resolver(reg, FakeObserver()).resolve("run", "run_a", deadline_ms=1)
    assert not short.complete and "deadline" in (short.reason or "")
    assert time.monotonic() - started < 20


def test_conflict_priority(tmp_path: Path) -> None:
    reg, creds = build(tmp_path, root("run_a"), root("run_h", "hooked"))
    reg.append_edges(creds["hook"], [edge("run_h", "run_c")])
    reg.append_edges(creds["process"], [edge("run_a", "run_c")])
    resolver = Resolver(reg, FakeObserver())
    assert "run_c" in resolver.resolve("run", "run_a").members
    assert "run_c" not in resolver.resolve("run", "run_h").members
    logged = findings(tmp_path, "lineage_conflict")
    assert len(logged) == 1
    assert logged[0]["winner"] == "run_a" and logged[0]["loser"] == "run_h"


def test_priority_order_and_dedup(tmp_path: Path) -> None:
    reg, creds = build(tmp_path, root("run_a"), root("run_b"))
    reg.append_edges(creds["runtime"], [edge("run_a", "run_c"), edge("run_a", "run_c")])
    reg.append_edges(creds["hook"], [edge("run_b", "run_c")])
    graph = Graph(reg.read().edges)
    assert graph.parent("run_c") == "run_a"
    assert graph.winner["run_c"].spawn_source == "runtime"
    assert len(graph.conflicts) == 1


def test_orphan_surfaced(tmp_path: Path) -> None:
    reg, _ = build(tmp_path, root("run_a"), edge("run_lost", "run_orphan"))
    tree = Resolver(reg, FakeObserver()).resolve("all")
    assert tree.orphans == ("run_orphan",)
    assert "run_orphan" in tree.members  # not silently ignored
    assert not tree.lineage_verified
    assert Graph(reg.read().edges).orphans() == ("run_orphan",)


def test_a_cycle_does_not_hang(tmp_path: Path) -> None:
    reg, _ = build(tmp_path, edge("run_x", "run_y"), edge("run_y", "run_x"))
    graph = Graph(reg.read().edges)
    assert graph.ancestors("run_x") == ("run_y",)
    assert Resolver(reg, FakeObserver()).resolve("run", "run_x").members == ("run_x", "run_y")


def test_agent_name_is_inherited(tmp_path: Path) -> None:
    reg, _ = build(tmp_path, *THREE_LEVELS)
    target = lineage_target(Graph(reg.read().edges), "run_c")
    assert target.agent == "bot" and target.ancestors == ("run_b", "run_a")
    assert not lineage_target(Graph(reg.read().edges), "run_nope").lineage_known


@pytest.mark.parametrize(
    "scope", ["agent:bot", "run:run_a", "subtree:run_a", "run:run_b", "all", "agent:child"]
)
def test_spawn_race(tmp_path: Path, scope: str) -> None:
    """A child spawned mid-halt is blocked by inheritance, even if never enumerated."""
    reg, _ = build(tmp_path, root("run_a"), edge("run_a", "run_b", name="child"))
    store = Store(tmp_path)
    store.ensure()
    Coordinator(store).raise_halt(Scope.parse(scope), Mode.KILL, actor="op", reason="r")
    reg.append_edges(adapters(reg)["process"], [edge("run_b", "run_late", name="late")])
    decision = check_lineage(RuntimeChoke(store), Graph(reg.read().edges), "run_late")
    assert not decision.allow and decision.reason is ReasonCode.HALTED


def test_an_unrelated_run_is_allowed_and_unknown_lineage_fails_closed(tmp_path: Path) -> None:
    reg, _ = build(tmp_path, *THREE_LEVELS)
    store = Store(tmp_path)
    store.ensure()
    Coordinator(store).raise_halt(Scope("subtree", "run_a"), Mode.KILL, actor="op", reason="r")
    graph = Graph(reg.read().edges)
    assert check_lineage(RuntimeChoke(store), graph, "run_z").allow
    unknown = check_lineage(RuntimeChoke(store), graph, "run_nope")
    assert not unknown.allow and unknown.reason is ReasonCode.LINEAGE_GAP
    damaged = check_lineage(RuntimeChoke(store), graph, "run_z", intact=False)
    assert not damaged.allow and damaged.reason is ReasonCode.LINEAGE_GAP
