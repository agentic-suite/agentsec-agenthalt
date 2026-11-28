"""Graph rules and the subtree resolver (R2, ADR-0008, M2 design §4-§6).

Edges union for existence; process observation wins for parentage. Resolution is bounded by one
deadline and never hangs: out of time, or blind, means ``complete=False``.
"""

from __future__ import annotations

import contextlib
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any

from agenthalt.choke import Decision, RuntimeChoke
from agenthalt.ids import ID_PATTERN
from agenthalt.journal import JournalError
from agenthalt.lineage import Edge, LineageError, LineageRegistry
from agenthalt.observe import ObserveError, Observer, Proc, node_id
from agenthalt.reasons import ReasonCode
from agenthalt.scopes import Impact, Target

__all__ = [
    "PRIORITY",
    "Conflict",
    "Discovery",
    "Graph",
    "Resolver",
    "Subtree",
    "check_lineage",
    "discover",
    "lineage_target",
    "separately_enrolled",
]

PRIORITY = {"process": 3, "runtime": 2, "hook": 1}
GrantSource = Callable[[tuple[str, ...]], Iterable[str]]


@dataclass(frozen=True)
class Conflict:
    child: str
    winner: str
    loser: str
    winner_source: str
    loser_source: str


class Graph:
    """The deduplicated lineage graph."""

    def __init__(self, edges: Iterable[Edge]) -> None:
        self.winner: dict[str, Edge] = {}
        self.meta: dict[str, dict[str, Any]] = {}
        self.conflicts: list[Conflict] = []
        claims: dict[str, list[Edge]] = {}
        for edge in edges:
            claims.setdefault(edge.child_run, []).append(edge)
        for child, found in claims.items():
            # highest priority first; the earliest record wins a tie
            found.sort(
                key=lambda e: (
                    e.parent_run.startswith("sup_"),
                    -PRIORITY[e.spawn_source],
                    e.seq,
                )
            )
            best = found[0]
            self.winner[child] = best
            merged: dict[str, Any] = {}
            for edge in reversed(found):
                merged.update(edge.child)
            self.meta[child] = merged
            losers: dict[str, Edge] = {}
            for edge in found[1:]:
                if edge.parent_run != best.parent_run and not edge.parent_run.startswith("sup_"):
                    losers.setdefault(edge.parent_run, edge)
            for parent, edge in losers.items():
                self.conflicts.append(
                    Conflict(child, best.parent_run, parent, best.spawn_source, edge.spawn_source)
                )
        self.children: dict[str, list[str]] = {}
        for child, edge in self.winner.items():
            self.children.setdefault(edge.parent_run, []).append(child)

    def __contains__(self, run: object) -> bool:
        return run in self.winner

    def parent(self, run: str) -> str | None:
        edge = self.winner.get(run)
        if edge is None or edge.parent_run.startswith("sup_"):
            return None
        return edge.parent_run

    def ancestors(self, run: str) -> tuple[str, ...]:
        chain: list[str] = []
        seen = {run}
        current = self.parent(run)
        while current is not None and current not in seen:
            chain.append(current)
            seen.add(current)
            current = self.parent(current)
        return tuple(chain)

    def enrolled(self) -> tuple[str, ...]:
        return tuple(run for run, meta in self.meta.items() if meta.get("enrollment"))

    def orphans(self) -> tuple[str, ...]:
        """Nodes whose parent is unknown: not a root, not hidden, never guessed about."""
        return tuple(
            child
            for child, edge in self.winner.items()
            if not self.meta[child].get("enrollment")
            and not edge.parent_run.startswith("sup_")
            and edge.parent_run not in self.winner
        )

    def agent_of(self, run: str) -> str | None:
        for node in (run, *self.ancestors(run)):
            name = self.meta.get(node, {}).get("name")
            if name:
                return str(name)
        return None

    def session_of(self, run: str) -> str | None:
        for node in (run, *self.ancestors(run)):
            session = self.meta.get(node, {}).get("session")
            if isinstance(session, str) and ID_PATTERN.fullmatch(session):
                return session
        return None

    def process_index(self) -> dict[tuple[int, str], str]:
        """``(pid, start) -> node``. An enrolled run wins over an observed ``proc_`` node."""
        index: dict[tuple[int, str], str] = {}
        for node, meta in sorted(
            self.meta.items(), key=lambda item: bool(item[1].get("enrollment"))
        ):
            if "pid" in meta and "start" in meta:
                index[(int(meta["pid"]), str(meta["start"]))] = node
        return index

    def walk(
        self, roots: Iterable[str], expired: Callable[[], bool] = lambda: False
    ) -> tuple[list[str], bool]:
        """Breadth-first members from ``roots``: ``(members, complete)``."""
        queue = list(dict.fromkeys(roots))
        seen = set(queue)
        index = 0
        while index < len(queue):
            if index % 256 == 0 and expired():
                return queue, False
            for child in self.children.get(queue[index], ()):
                if child not in seen:
                    seen.add(child)
                    queue.append(child)
            index += 1
        return queue, True


# --------------------------------------------------------------------------- discovery


@dataclass(frozen=True)
class Discovery:
    edges: tuple[dict[str, Any], ...]
    """New process-observed edges, parents before children."""
    gaps: tuple[tuple[str, int, str], ...]
    """``(node, pid, why)`` for descendants that left the observed set."""
    live: tuple[str, ...]


def discover(
    root: str,
    meta: dict[str, Any],
    known: dict[tuple[int, str], str],
    members: set[str],
    procs: dict[int, Proc],
    *,
    markers: dict[int, str],
    cgroup_of: Callable[[int], str | None],
    owned: bool = False,
) -> Discovery:
    """Find live processes belonging to the run rooted at ``root``.

    ``known`` maps ``(pid, start)`` to node id and is updated in place.
    """
    live: dict[int, str] = {}
    for pid, proc in procs.items():
        node = known.get((pid, proc.start))
        if node is not None and node in members:
            live[pid] = node
    edges: list[dict[str, Any]] = []
    gaps: list[tuple[str, int, str]] = []
    group = meta.get("pgid") if meta.get("containment") == "pgroup" else None
    cgroup = meta.get("cgroup") if meta.get("containment") == "cgroup" else None
    marker_run = meta.get("marker")
    if group is not None and not owned and not any(procs[p].pgid == group for p in live):
        group = None  # the run's processes are gone: the number may belong to someone else now

    def marked(pid: int, proc: Proc) -> bool:
        # 7: any process can carry the string, so it must also be the run's user and no older
        if marker_run is None or markers.get(pid) != marker_run:
            return False
        if "uid" in meta and proc.uid != meta["uid"]:
            return False
        return "start" not in meta or int(proc.start) >= int(meta["start"])

    def add(pid: int, parent: str, via: str) -> None:
        proc = procs[pid]
        node = known.get((pid, proc.start))
        if node is None:
            node = node_id(proc)
            known[(pid, proc.start)] = node
        if node not in members:
            members.add(node)
            child = {
                "pid": pid,
                "start": proc.start,
                "pgid": proc.pgid,
                "sid": proc.sid,
                "uid": proc.uid,
                "via": via,
            }
            edges.append({"parent_run": parent, "child_run": node, "child": child})
        live[pid] = node

    children: dict[int, list[int]] = {}
    for pid, proc in procs.items():
        children.setdefault(proc.ppid, []).append(pid)

    def descend(start: list[int]) -> None:
        queue = list(start)
        while queue:
            parent = queue.pop(0)
            for pid in children.get(parent, ()):
                if pid not in live:
                    add(pid, live[parent], "ancestry")
                    queue.append(pid)

    descend(list(live))
    # Contained but re-parented, then escaped (marker only): attach under the run's root.
    strays: list[tuple[int, str]] = []
    for pid, proc in procs.items():
        if pid in live:
            continue
        if cgroup is not None and cgroup_of(pid) == cgroup:
            strays.append((pid, "cgroup"))
        elif group is not None and proc.pgid == group:
            strays.append((pid, "pgroup"))
        elif marked(pid, proc):
            strays.append((pid, "marker"))
    for pid, via in strays:
        if pid not in live:
            add(pid, root, via)
            descend([pid])
    for pid, node in live.items():
        if cgroup is not None and cgroup_of(pid) not in (cgroup, None):
            gaps.append((node, pid, "left the run's cgroup"))
        elif group is not None and procs[pid].pgid != group:
            gaps.append((node, pid, "left the run's process group"))
    return Discovery(tuple(edges), tuple(gaps), tuple(live.values()))


def separately_enrolled(graph: Graph, root: str, procs: dict[int, Proc]) -> set[int]:
    """Pids contained by another supervisor below ``root``: leaving ``root``'s group is expected."""
    own = {
        pid
        for (pid, start), node in graph.process_index().items()
        if node != root
        and graph.meta[node].get("enrollment") == "run"
        and pid in procs
        and procs[pid].start == start
    }
    inside = set()
    for pid in procs:
        current, seen = pid, set()
        while current in procs and current not in seen:
            if current in own:
                inside.add(pid)
                break
            seen.add(current)
            current = procs[current].ppid
    return inside


# --------------------------------------------------------------------------- resolver


@dataclass(frozen=True)
class Subtree:
    target: str
    roots: tuple[str, ...]
    members: tuple[str, ...]
    grants: tuple[str, ...] = ()
    grants_status: str = "unavailable"
    orphans: tuple[str, ...] = ()
    gaps: tuple[str, ...] = ()
    complete: bool = True
    lineage_verified: bool = False
    reason: str | None = None


@dataclass
class Resolver:
    registry: LineageRegistry
    observer: Observer
    grants: GrantSource | None = None
    clock: Callable[[], float] = field(default=time.monotonic)
    actor: str = "agenthalt"

    def resolve(self, kind: str, value: str | None = None, *, deadline_ms: int = 5000) -> Subtree:
        if kind not in ("run", "agent", "all"):
            raise ValueError(f"cannot resolve a {kind!r} target (run, agent or all)")
        label = kind if value is None else f"{kind}:{value}"
        deadline = self.clock() + deadline_ms / 1000

        def expired() -> bool:
            return self.clock() >= deadline

        read = self.registry.read(expired=expired)
        graph = Graph(read.edges)
        with contextlib.suppress(LineageError, JournalError, OSError):
            self._log_conflicts(graph)  # re-tried by the next resolve
        if kind == "run":
            roots = [value] if value is not None and value in graph else []
        elif kind == "agent":
            roots = [r for r in graph.enrolled() if graph.meta[r].get("name") == value]
        else:
            roots = [*graph.enrolled(), *graph.orphans()]
        if not read.complete or expired():
            return Subtree(label, tuple(roots), tuple(roots), complete=False, reason="deadline")
        if not roots and kind != "all":
            return Subtree(
                label, (), (), complete=False, reason=f"unknown target {label}: no lineage"
            )

        members, complete = graph.walk(roots, expired)
        if not complete:
            return Subtree(label, tuple(roots), tuple(members), complete=False, reason="deadline")
        reason = None
        gaps: set[str] = set()
        try:
            added = self._observe(graph, members, deadline, gaps)
        except (ObserveError, LineageError, JournalError, OSError) as exc:
            complete, reason, added = False, str(exc), []
        members = list(dict.fromkeys([*members, *added]))
        if expired():
            complete, reason = False, reason or "deadline"

        inside = set(members)
        orphans = tuple(o for o in graph.orphans() if o in inside)
        try:
            recorded = self.registry.findings("lineage_gap")
        except (JournalError, OSError) as exc:
            recorded, complete, reason = [], False, reason or str(exc)
        gaps.update(str(f["node"]) for f in recorded if f.get("node") in inside)
        unverified = any(
            graph.meta.get(m, {}).get("enrollment") == "attach" and m not in read.verified
            for m in members
        )
        verified = complete and not (read.findings or gaps or orphans or unverified)
        granted: tuple[str, ...] = ()
        if self.grants is not None:
            granted = tuple(self.grants(tuple(members)))
        return Subtree(
            target=label,
            roots=tuple(roots),
            members=tuple(members),
            grants=granted,
            grants_status="unavailable" if self.grants is None else "listed",
            orphans=orphans,
            gaps=tuple(sorted(gaps)),
            complete=complete,
            lineage_verified=verified,
            reason=reason,
        )

    def _log_conflicts(self, graph: Graph) -> None:
        for item in graph.conflicts:
            self.registry.record_finding(
                "lineage_conflict",
                {
                    "child": item.child,
                    "winner": item.winner,
                    "loser": item.loser,
                    "winner_source": item.winner_source,
                    "loser_source": item.loser_source,
                },
                actor=self.actor,
                unique=("child", "winner", "loser"),
            )

    def _observe(
        self, graph: Graph, members: list[str], deadline: float, gaps: set[str]
    ) -> list[str]:
        """Walk the live processes of every enrolled member and record what is new."""
        enrolled = [m for m in members if graph.meta.get(m, {}).get("enrollment")]
        if not any("pid" in graph.meta.get(m, {}) for m in members):
            return []
        remaining = max(deadline - self.clock(), 0.001)
        procs = self.observer.snapshot(remaining)
        markers = self.observer.run_markers(max(deadline - self.clock(), 0.001))
        known = graph.process_index()
        credential = self.registry.register_adapter("process-observer", "process")
        added: list[str] = []
        for root in enrolled:
            if self.clock() >= deadline:
                break
            meta = graph.meta[root]
            subtree = set(graph.walk([root])[0])
            found = discover(
                root,
                meta,
                known,
                subtree,
                procs,
                markers=markers,
                cgroup_of=self.observer.cgroup_of,
            )
            self.registry.append_edges(credential, list(found.edges))
            added.extend(e["child_run"] for e in found.edges)
            separate = separately_enrolled(graph, root, procs) if found.gaps else set()
            for node, pid, why in found.gaps:
                if pid in separate:
                    continue
                gaps.add(node)
                self.registry.record_finding(
                    "lineage_gap",
                    {"run": root, "node": node, "pid": pid, "why": why},
                    actor=self.actor,
                    unique=("node", "why"),
                )
            self._check_supervisor(root, meta, procs)
        return added

    def _check_supervisor(self, root: str, meta: dict[str, Any], procs: dict[int, Proc]) -> None:
        supervisor = meta.get("supervisor")
        if not supervisor:
            return

        def alive(pid: Any, start: Any) -> bool:
            return pid in procs and procs[pid].start == start

        if alive(meta.get("pid"), meta.get("start")) and not alive(
            supervisor["pid"], supervisor["start"]
        ):
            self.registry.record_finding(
                "supervisor_lost",
                {"run": root, "node": root, "supervisor_pid": supervisor["pid"]},
                actor=self.actor,
                unique=("run",),
            )


# --------------------------------------------------------------------------- the choke


def lineage_target(
    graph: Graph, run: str, *, intact: bool = True, impact: Impact = "high"
) -> Target:
    """The choke target for ``run``, with its ancestry filled from the registry."""
    return Target(
        run=run,
        agent=graph.agent_of(run),
        session=graph.session_of(run),
        ancestors=graph.ancestors(run),
        lineage_known=intact and run in graph,
        impact=impact,
    )


def check_lineage(
    choke: RuntimeChoke,
    graph: Graph,
    run: str,
    *,
    intact: bool = True,
    impact: Impact = "high",
) -> Decision:
    """The post-halt spawn rule: a halt on any ancestor, in any scope kind, covers ``run``."""
    own = choke.check(lineage_target(graph, run, intact=intact, impact=impact))
    if own.reason is ReasonCode.HALTED:
        return own
    for ancestor in graph.ancestors(run):
        decision = choke.check(lineage_target(graph, ancestor, intact=intact, impact=impact))
        if decision.reason is ReasonCode.HALTED:
            return decision
    return own
