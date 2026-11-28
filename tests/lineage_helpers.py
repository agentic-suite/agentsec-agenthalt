"""Shared fixtures for the M2 lineage tests: a registry in a temp home and a fake process table."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agenthalt.journal import Journal
from agenthalt.lineage import AdapterCredential, LineageRegistry
from agenthalt.observe import ObserveError, Proc


def make_registry(home: Path, **kwargs: Any) -> LineageRegistry:
    return LineageRegistry(home, journal=Journal(home), **kwargs)


def edge(parent: str, child: str, **meta: Any) -> dict[str, Any]:
    return {"parent_run": parent, "child_run": child, "child": meta}


def root(run: str, name: str = "bot", **meta: Any) -> dict[str, Any]:
    return edge(f"sup_{run}", run, enrollment="run", name=name, **meta)


def adapters(reg: LineageRegistry) -> dict[str, AdapterCredential]:
    return {s: reg.register_adapter(f"{s}-adapter", s) for s in ("process", "runtime", "hook")}


def proc(pid: int, ppid: int, *, pgid: int | None = None, uid: int = 501, start: int = 0) -> Proc:
    group = pid if pgid is None else pgid
    return Proc(pid=pid, ppid=ppid, pgid=group, sid=group, uid=uid, start=str(start or pid * 10))


@dataclass
class FakeObserver:
    procs: dict[int, Proc] = field(default_factory=dict)
    markers: dict[int, str] = field(default_factory=dict)
    cgroups: dict[int, str] = field(default_factory=dict)
    fail: bool = False

    def add(self, *procs: Proc) -> None:
        for item in procs:
            self.procs[item.pid] = item

    def snapshot(self, timeout_s: float = 5.0) -> dict[int, Proc]:
        if self.fail:
            raise ObserveError("process table unavailable")
        return dict(self.procs)

    def run_markers(self, timeout_s: float = 5.0) -> dict[int, str]:
        return dict(self.markers)

    def cgroup_of(self, pid: int) -> str | None:
        return self.cgroups.get(pid)
