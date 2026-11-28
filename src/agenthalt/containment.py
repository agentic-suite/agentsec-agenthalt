"""Cutting a halted subtree: resolve, suspend, cut the network, kill (M3 design §3, §6, §8).

The coordinator calls this after the halt is on record, so the choke already denies new actions.
Everything here is reported as it was observed; nothing is rounded up to a stop.
"""

from __future__ import annotations

import contextlib
import os
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agenthalt.cutlog import LAYERS, CutLog, CutWriter
from agenthalt.executors import (
    GRACE_S,
    Confirmation,
    Context,
    ExecutorSigner,
    Member,
    Result,
    confirmation,
    run_phase,
)
from agenthalt.exit_codes import ReceiptStatus, status_for
from agenthalt.journal import JournalError
from agenthalt.lineage import LineageError, LineageRegistry
from agenthalt.logs import get_logger
from agenthalt.observe import ObserveError, Observer, Proc
from agenthalt.scopes import Mode, Scope
from agenthalt.store import HaltState
from agenthalt.subtree import Graph, Resolver, discover, lineage_target
from agenthalt.supervisor import LIVENESS_GAP

__all__ = ["Containment", "Cut", "recorded_uid"]

_log = get_logger("containment")
_TARGET_KINDS = {
    "run": "run",
    "subtree": "run",
    "agent": "agent",
    "session": "session",
    "all": "all",
}


def recorded_uid(home: Path, run: str, *, owner: int = 0) -> int | None:
    """The ``run --user`` uid, believed only from a file that ``owner`` (root) wrote."""
    if "/" in run:
        return None
    try:
        fd = os.open(home / "keys" / "users" / run, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            if os.fstat(fd).st_uid != owner:
                return None
            named, uid = os.read(fd, 256).decode().split()
        finally:
            os.close(fd)
        return int(uid) if named == run else None
    except (OSError, ValueError):
        return None


def _alive(member: Member, procs: Mapping[int, Proc]) -> bool:
    proc = procs.get(member.pid)
    return proc is not None and proc.start == member.start


@dataclass
class Cut:
    """What one execution of a halt did."""

    confirmations: list[Confirmation] = field(default_factory=list)
    survivors: list[dict[str, Any]] = field(default_factory=list)
    members: list[dict[str, Any]] = field(default_factory=list)
    undo: dict[str, list[dict[str, Any]]] = field(
        default_factory=lambda: {"process": [], "sandbox": []}
    )
    complete: bool = True
    lineage_verified: bool = False
    reason: str | None = None

    def layers(self) -> dict[str, str]:
        """One word per layer: the worst final status among its targets."""
        order = ("failed", "requested", "unsupported", "confirmed")
        final: dict[tuple[str, str], str] = {}
        for item in self.confirmations:  # later phases overwrite earlier ones per target
            final[(item.layer, item.target)] = item.status
        found: dict[str, str] = {"runtime_choke": "enforced"}
        for (layer, _), status in final.items():
            if layer not in found or order.index(status) < order.index(found[layer]):
                found[layer] = status
        return found

    def outcome(self) -> ReceiptStatus:
        layers = self.layers()
        survivor = (
            bool(self.survivors)
            or not self.complete
            or any(s in ("failed", "requested") for s in layers.values())
        )
        return status_for(
            survivor=survivor,
            unsupported_layer="unsupported" in layers.values(),
            blocking_failed=False,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "confirmations": [c.to_dict() for c in self.confirmations],
            "survivors": self.survivors,
            "members": self.members,
            "undo": self.undo,
            "complete": self.complete,
            "lineage_verified": self.lineage_verified,
            "reason": self.reason,
        }


@dataclass
class Containment:
    registry: LineageRegistry
    observer: Observer
    adapters: Mapping[str, Any]
    """``layer -> executor adapter``."""
    signer: ExecutorSigner | None = None
    deadline_ms: int = 1000
    invoking_uid: int = field(default_factory=os.getuid)
    elevate: Callable[[], AbstractContextManager[None]] = contextlib.nullcontext
    """Privileges for signalling and the firewall; state is written outside it."""
    evidence: Callable[[str, Sequence[Member]], None] = lambda halt_id, members: None
    """The evidence slot (M5): after suspend, before anything is terminated."""
    actor: str = "agenthalt"

    @property
    def cutlog(self) -> CutLog:
        return CutLog(self.registry.home)

    # ----------------------------------------------------------------------- members

    def _resolve(self, scope: Scope, cut: Cut, deadline: float) -> tuple[Graph, list[str]]:
        kind = _TARGET_KINDS[scope.kind]
        resolver = Resolver(self.registry, self.observer, actor=self.actor)
        tree = resolver.resolve(
            kind, scope.value, deadline_ms=max(int((deadline - time.monotonic()) * 1000), 1)
        )
        cut.complete, cut.reason = tree.complete, tree.reason
        cut.lineage_verified = tree.lineage_verified
        read = self.registry.read()
        graph = Graph(read.edges)
        nodes = list(tree.members)
        if not tree.complete and tree.roots:  # out of time: still cut everything on record
            nodes = list(dict.fromkeys([*nodes, *graph.walk(list(tree.roots))[0]]))
        if read.findings:
            cut.complete, cut.reason = False, "lineage is damaged or was tampered with"
        held_open = {
            f.get("node")
            for f in self.registry.findings("lineage_gap")
            if f.get("why") == LIVENESS_GAP
        }
        if held_open & set(nodes):
            cut.complete, cut.reason = False, LIVENESS_GAP
        return graph, nodes

    def _member(self, graph: Graph, node: str, meta: Mapping[str, Any], via: str) -> Member:
        owner = next(
            (n for n in (node, *graph.ancestors(node)) if graph.meta.get(n, {}).get("enrollment")),
            node,
        )
        owned = graph.meta.get(owner, {})
        cgroup = owned.get("cgroup") if owned.get("containment") == "cgroup" else None
        uid = recorded_uid(self.registry.home, owner) if owned.get("user") else None
        return Member(node, int(meta["pid"]), str(meta["start"]), owner, via, cgroup, uid)

    def _live(self, graph: Graph, nodes: Sequence[str], procs: Mapping[int, Proc]) -> list[Member]:
        found: dict[tuple[int, str], Member] = {}
        for node in nodes:
            meta = graph.meta.get(node, {})
            if "pid" not in meta or "start" not in meta:
                continue
            pid, start = int(meta["pid"]), str(meta["start"])
            if pid in procs and procs[pid].start == start:
                via = str(meta.get("via", "enrollment"))
                found.setdefault((pid, start), self._member(graph, node, meta, via))
        return list(found.values())

    def _expander(
        self, graph: Graph, nodes: Sequence[str], edges: list[dict[str, Any]]
    ) -> Callable[[dict[int, Proc]], list[Member]]:
        """Find members the lineage does not know yet. Read-only: edges are recorded later."""
        known = graph.process_index()
        roots = [n for n in nodes if graph.meta.get(n, {}).get("enrollment")]
        subtrees = {root: set(graph.walk([root])[0]) for root in roots}
        found: dict[str, Member] = {}
        guard = threading.Lock()

        def expand(procs: dict[int, Proc]) -> list[Member]:
            with guard:  # the executor's thread and ours both look
                return look(procs)

        def look(procs: dict[int, Proc]) -> list[Member]:
            markers = self.observer.run_markers(5.0)
            for root in roots:
                result = discover(
                    root,
                    graph.meta[root],
                    known,
                    subtrees[root],
                    procs,
                    markers=markers,
                    cgroup_of=self.observer.cgroup_of,
                )
                for edge in result.edges:
                    edges.append(edge)
                    node, meta = edge["child_run"], edge["child"]
                    base = self._member(graph, root, graph.meta[root], meta["via"])
                    found[node] = Member(
                        node,
                        meta["pid"],
                        meta["start"],
                        base.run,
                        meta["via"],
                        base.cgroup,
                        base.uid,
                    )
            return list(found.values())

        return expand

    # ----------------------------------------------------------------------- phases

    def _phases(
        self, calls: Sequence[tuple[str, str, Sequence[Any], Sequence[str]]], ctx: Context
    ) -> list[list[Result]]:
        """Run ``(layer, phase, targets, names)`` calls in parallel, abandoning a hung adapter."""
        boxes: list[list[Result]] = [[] for _ in calls]
        done = [threading.Event() for _ in calls]

        def work(index: int) -> None:
            layer, phase, targets, names = calls[index]
            boxes[index] = run_phase(self.adapters[layer], phase, targets, names, ctx)
            done[index].set()

        for index in range(len(calls)):
            threading.Thread(target=work, args=(index,), daemon=True).start()
        started = max(ctx.deadline, time.monotonic())
        out = []
        for index, (layer, _, _, names) in enumerate(calls):
            limit = started + getattr(self.adapters[layer], "grace_s", GRACE_S)
            if done[index].wait(max(limit - time.monotonic(), 0)):
                out.append(boxes[index])
            else:
                out.append([Result(n, "requested", "the adapter did not answer") for n in names])
        return out

    def _record(
        self,
        cut: Cut,
        halt: HaltState,
        layer: str,
        phase: str,
        results: Sequence[Result],
        writer: CutWriter | None = None,
    ) -> None:
        adapter = self.adapters.get(layer)
        attestation = getattr(adapter, "attestation", "self")
        for result in results:
            cut.confirmations.append(
                confirmation(
                    halt.halt_id,
                    layer,
                    phase,
                    result,
                    attestation=attestation,
                    signer=self.signer,
                )
            )
            if result.undo is not None and writer is not None and layer in LAYERS:
                writer.cut(layer, result.undo)  # adapters that did not record as they went

    def _unsupported(self, cut: Cut, halt: HaltState, layer: str, why: str) -> None:
        self._record(cut, halt, layer, "block", [Result(str(halt.scope), "unsupported", why)])

    # ----------------------------------------------------------------------- cut

    def cut(self, halt: HaltState) -> Cut:
        cut = Cut()
        deadline = time.monotonic() + self.deadline_ms / 1000
        self._unsupported(cut, halt, "gateway", "agentgate is not composed (DD-18)")
        if halt.mode is not Mode.PAUSE:
            self._unsupported(cut, halt, "credentials", "credential revoke and freeze land in M4")
        if halt.scope.kind not in _TARGET_KINDS:
            self._unsupported(cut, halt, "process", f"a {halt.scope.kind} halt names no process")
            return cut
        edges: list[dict[str, Any]] = []
        writer = self.cutlog.writer(halt.to_dict())  # opened before any elevation
        try:
            self._cut(cut, halt, deadline, writer, edges)
        except Exception as exc:  # whatever breaks, the halt reports it and carries on
            cut.complete, cut.reason = False, str(exc)
            _log.error("containment.failed", extra={"fields": {"error": str(exc)}})
        finally:
            writer.close()
        if writer.failed:
            cut.complete, cut.reason = False, f"{writer.failed}; lift may not undo this halt"
        cut.undo = self.cutlog.read(halt.halt_id).pending
        if edges:
            with contextlib.suppress(LineageError, JournalError, OSError):
                self.registry.append_edges(
                    self.registry.register_adapter("process-observer", "process"), edges
                )
        return cut

    def _look(
        self,
        cut: Cut,
        everyone: dict[str, Member],
        expand: Callable[[dict[int, Proc]], Sequence[Member]],
    ) -> dict[int, Proc] | None:
        """List processes again and take in anything new. ``None``: we could not look."""
        try:
            table = self.observer.snapshot(5.0)
            for member in expand(table):
                everyone.setdefault(member.node, member)
        except ObserveError as exc:
            cut.complete, cut.reason = False, str(exc)
            return None
        return table

    def _cut(
        self,
        cut: Cut,
        halt: HaltState,
        deadline: float,
        writer: CutWriter,
        edges: list[dict[str, Any]],
    ) -> None:
        graph, nodes = self._resolve(halt.scope, cut, deadline)
        procs = self.observer.snapshot(5.0)
        members = self._live(graph, nodes, procs)
        expand = self._expander(graph, nodes, edges)
        ctx = Context(
            halt.halt_id,
            deadline,
            expand=expand,
            invoking_uid=self.invoking_uid,
            held=lambda: self.cutlog.held(besides=halt.halt_id),
            record=writer.cut,
        )
        quiet = "process" not in self.adapters
        if quiet:
            self._unsupported(cut, halt, "process", "no process executor")
        network = halt.mode is not Mode.PAUSE
        if network and "sandbox" not in self.adapters:
            self._unsupported(cut, halt, "sandbox", "no sandbox executor")
            network = False

        everyone = {m.node: m for m in members}
        table: dict[int, Proc] | None = procs
        with self.elevate():
            calls: list[tuple[str, str, Sequence[Any], Sequence[str]]] = []
            if not quiet:
                calls.append(("process", "suspend", members, [m.node for m in members]))
            if network and members:
                calls.append(("sandbox", "block", members, sorted({m.run for m in members})))
            results = self._phases(calls, ctx)
            for (layer, phase, _, _), found in zip(calls, results, strict=True):
                self._record(cut, halt, layer, phase, found, writer)
            for _ in range(5):  # children found after the stop must be cut too
                table = self._look(cut, everyone, expand)
                if table is None or quiet:
                    break
                answered = {c.target for c in cut.confirmations if c.layer == "process"}
                late = [m for m in everyone.values() if m.node not in answered and _alive(m, table)]
                if not late:
                    break
                found = self._phases([("process", "suspend", late, [m.node for m in late])], ctx)[0]
                self._record(cut, halt, "process", "suspend", found, writer)
            if network and len(everyone) > len(members):
                inside = list(everyone.values())
                found = self._phases(
                    [("sandbox", "block", inside, sorted({m.run for m in inside}))], ctx
                )[0]
                self._record(cut, halt, "sandbox", "block", found, writer)
        if not quiet and not everyone:
            # an unknown or unreadable target proves nothing; a known one with nothing running does
            status = "confirmed" if cut.complete else "requested"
            why = "nothing enrolled is running" if cut.complete else str(cut.reason)
            self._record(cut, halt, "process", "suspend", [Result(str(halt.scope), status, why)])
        if halt.mode is Mode.KILL and not quiet:
            self.evidence(halt.halt_id, list(everyone.values()))  # before anything dies (DD-10)
            targets = list(everyone.values())
            with self.elevate():
                for _ in range(3):
                    killed = self._phases(
                        [("process", "terminate", targets, [m.node for m in targets])], ctx
                    )[0]
                    self._record(cut, halt, "process", "terminate", killed, writer)
                    done = set(everyone)
                    table = self._look(cut, everyone, expand)
                    if table is None:
                        break
                    targets = [m for n, m in everyone.items() if n not in done and _alive(m, table)]
                    if not targets:
                        break
        members = list(everyone.values())
        cut.members = [{"id": m.node, "pid": m.pid, "run": m.run, "via": m.via} for m in members]
        if not quiet:
            self._survivors(cut, halt, members, table)
        if halt.mode is Mode.KILL and not quiet and not cut.survivors and cut.complete:
            self._retire(cut, halt, ctx, writer)

    def _survivors(
        self,
        cut: Cut,
        halt: HaltState,
        members: Sequence[Member],
        table: Mapping[int, Proc] | None,
    ) -> None:
        final = {c.target: c for c in cut.confirmations if c.layer == "process"}
        for member in members:
            item = final.get(member.node)
            proc = None if table is None else table.get(member.pid)
            alive = proc is not None and proc.start == member.start
            why = None
            if item is not None and item.status != "confirmed":
                why = item.note
            elif item is None and (table is None or alive):
                why = "never cut"
            elif (
                alive
                and proc is not None
                and halt.mode is not Mode.KILL
                and member.cgroup is None  # a frozen cgroup does not show as stopped
                and proc.state
                and not proc.state.startswith(("T", "t"))
            ):
                why = "running again"
            if why is None:
                continue
            cut.survivors.append({"id": member.node, "pid": member.pid, "why": why})
            if item is None or item.status == "confirmed":
                self._record(
                    cut, halt, "process", "suspend", [Result(member.node, "requested", why)]
                )

    def _retire(self, cut: Cut, halt: HaltState, ctx: Context, writer: CutWriter) -> None:
        """After a complete kill nothing is left to continue or to cut off."""
        record = self.cutlog.read(halt.halt_id)
        for item in record.pending["process"]:
            writer.done("process", item)
        with self.elevate():
            for item in record.pending["sandbox"]:
                results = self._release_one("sandbox", item, ctx)
                if all(r.status == "confirmed" for r in results):
                    writer.done("sandbox", item)
                else:
                    why = f"rules not removed: {results[0].note}"
                    self._record(
                        cut, halt, "sandbox", "release", [Result(results[0].target, "failed", why)]
                    )

    # ----------------------------------------------------------------------- release

    def _release_one(self, layer: str, item: Mapping[str, Any], ctx: Context) -> list[Result]:
        adapter = self.adapters.get(layer)
        if adapter is None:
            return [Result(layer, "failed", "no executor to release with")]
        try:
            return list(adapter.release([item], ctx))
        except Exception as exc:
            return [Result(layer, "failed", f"release failed: {exc}")]

    def release(
        self, halt: HaltState, remaining: Sequence[HaltState], *, everything: bool = False
    ) -> list[Result]:
        """Undo what ``halt`` cut, except what another active halt still covers (DD-52).

        What cannot be released stays on record, so lifting again retries it. ``everything``
        also re-releases items already marked done (the halt was lifted while still cutting).
        """
        record = self.cutlog.read(halt.halt_id)
        items = record.ever if everything else record.pending
        ctx = Context(halt.halt_id, time.monotonic() + 5.0, invoking_uid=self.invoking_uid)
        writer = self.cutlog.writer(halt.to_dict())
        results: list[Result] = []
        process: list[Mapping[str, Any]] = []
        try:
            if halt.mode is Mode.KILL:
                for item in items["process"]:
                    writer.done("process", item)  # a kill continues nothing
            elif items["process"]:
                read = self.registry.read()
                unsure = not read.complete or bool(read.findings)
                graph = Graph(read.edges)
                for item in items["process"]:
                    run = str(item.get("run"))
                    name = f"cgroup:{run}" if "freeze" in item else ""
                    name = name or f"proc_{item.get('pid')}_{item.get('start')}"
                    targets = [lineage_target(graph, n) for n in (run, *graph.ancestors(run))]
                    covering = [h for h in remaining if any(h.scope.matches(t) for t in targets)]
                    if covering:
                        for other in covering:  # it is theirs to release now
                            heir = self.cutlog.writer(other.to_dict())
                            heir.cut("process", item)
                            heir.close()
                        writer.done("process", item)
                        why = f"stays frozen: also covered by {covering[0].halt_id}"
                        results.append(Result(name, "requested", why))
                    elif unsure and remaining:
                        why = "stays frozen: lineage cannot be trusted and other halts are active"
                        results.append(Result(name, "failed", why))
                    else:
                        process.append(item)
            process.sort(key=lambda item: "freeze" not in item)  # thaw before continuing
            with self.elevate():
                work = [("sandbox", i) for i in items["sandbox"]]
                for layer, entry in [*work, *(("process", i) for i in process)]:
                    found = self._release_one(layer, entry, ctx)
                    results.extend(found)
                    if all(r.status == "confirmed" for r in found):
                        writer.done(layer, dict(entry))
        finally:
            writer.close()
        return results
