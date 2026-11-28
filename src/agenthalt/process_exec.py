"""The process-tree executor: suspend, then kill (M3 design §4, DD-23).

Every signal is preceded by an identity check (pid and start time), and a confirmation is always an
observation of the process, never the return value of the signal call.
"""

from __future__ import annotations

import contextlib
import os
import signal
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from agenthalt.executors import Context, Member, Result
from agenthalt.observe import ObserveError, Observer, Proc

__all__ = ["ProcessExecutor", "own_cgroup", "refusal"]

STOPPED = ("T", "t")
POLL_S = 0.02
FLOOR_S = 1.0
"""Time one process listing gets even when the deadline has passed: signals are still sent."""


def _ancestors(procs: Mapping[int, Proc], pid: int) -> set[int]:
    found: set[int] = set()
    while pid in procs and procs[pid].ppid not in found and procs[pid].ppid > 0:
        pid = procs[pid].ppid
        found.add(pid)
    return found


def refusal(
    proc: Proc,
    procs: Mapping[int, Proc],
    *,
    invoking_uid: int,
    me: int | None = None,
    also: int | None = None,
) -> str | None:
    """Why this process must never be signalled, or ``None``."""
    me = os.getpid() if me is None else me
    if proc.pid <= 1:
        return "refused: pid 0 and 1 are never signalled"
    if proc.pid == me or proc.pid in _ancestors(procs, me):
        return "refused: it is running this halt; halt it from outside"
    if proc.uid == 0 and invoking_uid != 0:
        return "refused: a root process, and the person halting is not root"
    if invoking_uid != 0 and proc.uid not in (invoking_uid, also):
        return "refused: another user's process, which this run was not launched as"
    return None


def own_cgroup(cgroup: str | None, run: str, root: Path) -> Path | None:
    """The run's cgroup directory, only if the recorded path is unmistakably that run's."""
    if not cgroup or ".." in cgroup.split("/"):
        return None
    if cgroup.rstrip("/").rsplit("/", 1)[-1] != f"agenthalt-{run}":
        return None
    path = root / cgroup.strip("/")
    return path if path.is_dir() else None


def _contains(group: Path, pid: int) -> bool:
    try:
        return str(pid) in (group / "cgroup.procs").read_text().split()
    except OSError:
        return False


def _frozen(group: Path) -> bool:
    try:
        return "frozen 1" in (group / "cgroup.events").read_text()
    except OSError:
        return False


class ProcessExecutor:
    name = "process-tree"
    layer = "process"
    version = "1"
    attestation = "self"
    grace_s = 30.0
    """Hard cap past the deadline: stopping halfway through a tree is worse than being late."""

    def __init__(
        self,
        observer: Observer,
        *,
        cgroup_root: Path = Path("/sys/fs/cgroup"),
        kill: Callable[[int, int], None] = os.kill,
    ) -> None:
        self.observer = observer
        self.cgroup_root = cgroup_root
        self._kill = kill

    # ----------------------------------------------------------------------- signals

    def _send(self, member: Member, signum: int) -> str | None:
        """Signal one process if it is still the same process. ``None`` means sent or gone."""
        fd = None
        try:
            opener = getattr(os, "pidfd_open", None)  # Linux
            if opener is not None and self._kill is os.kill:
                fd = opener(member.pid)  # pins the process, then check who it is
            current = self.observer.probe([member.pid]).get(member.pid)
            if current is None or current.start != member.start:
                return None  # gone; a reused pid is someone else
            if fd is not None:
                getattr(signal, "pidfd_send_signal")(fd, signum)  # noqa: B009
            else:
                self._kill(member.pid, signum)
        except ProcessLookupError:
            return None
        except PermissionError:
            return "permission denied (a --user run needs sudo)"
        except (OSError, ObserveError) as exc:
            return str(exc)
        finally:
            if fd is not None:
                os.close(fd)
        return None

    def _inside(self, group: Path, cgroup: str, pid: int) -> bool:
        where = self.observer.cgroup_of(pid) or ""
        return (
            _contains(group, pid) or where == cgroup or where.startswith(cgroup.rstrip("/") + "/")
        )

    def _groups(self, members: Iterable[Member], procs: Mapping[int, Proc]) -> dict[str, Path]:
        """Per-run cgroups that are safe to act on as a whole."""
        chain = {os.getpid(), *_ancestors(procs, os.getpid())}
        found: dict[str, Path] = {}
        for member in members:
            group = own_cgroup(member.cgroup, member.run, self.cgroup_root)
            if group is None or member.cgroup is None:
                continue
            if not any(self._inside(group, member.cgroup, pid) for pid in chain):
                found[member.run] = group
        return found

    def _write(self, path: Path, value: str) -> None:
        with contextlib.suppress(OSError):  # the per-process signals still apply
            path.write_text(value)

    def _table(self, members: Iterable[Member]) -> dict[int, Proc]:
        """A listing to signal by: the full one, or failing that the targets and our ancestors."""
        for _ in range(2):
            with contextlib.suppress(ObserveError):
                return self.observer.snapshot(5.0)
        table = self.observer.probe([m.pid for m in members] or [os.getpid()])
        pid = os.getpid()
        for _ in range(64):  # our own chain, so that we are still never signalled
            found = self.observer.probe([pid]).get(pid)
            if found is None:
                break
            table[pid] = found
            pid = found.ppid
            if pid <= 0:
                break
        return table

    def _refusal(
        self, member: Member, proc: Proc, procs: Mapping[int, Proc], ctx: Context
    ) -> str | None:
        return refusal(proc, procs, invoking_uid=ctx.invoking_uid, also=member.uid)

    # ----------------------------------------------------------------------- suspend

    def suspend(self, targets: Sequence[Member], ctx: Context) -> list[Result]:
        pending: dict[str, Member] = {m.node: m for m in targets}
        seen: set[str] = set()
        undo: dict[str, dict[str, Any]] = {}
        notes: dict[str, str] = {}
        frozen: dict[str, Path] = {}
        procs: dict[int, Proc] = {}
        observed = time.monotonic()
        overtime = 0
        try:
            procs = self._table(pending.values())
        except ObserveError as exc:
            return [Result(n, "requested", f"cannot observe, nothing sent: {exc}") for n in pending]
        lost = ""
        while True:
            try:
                for member in ctx.expand(procs):
                    pending.setdefault(member.node, member)
            except ObserveError as exc:
                lost = str(exc)
            held = ctx.held()
            # parents before children: a stopped parent cannot fork
            order = sorted(pending.values(), key=lambda m: len(_ancestors(procs, m.pid)))
            for member in order:
                proc = procs.get(member.pid)
                if member.node in notes or proc is None or proc.start != member.start:
                    continue
                stopped = proc.state.startswith(STOPPED)
                if stopped and member.node in seen:
                    continue
                seen.add(member.node)  # anything still running is signalled again
                why = self._refusal(member, proc, procs, ctx)
                if why is None:
                    if not stopped or (member.pid, member.start) in held:
                        item = {"pid": member.pid, "start": member.start, "run": member.run}
                        if member.uid is not None:
                            item["uid"] = member.uid
                        undo[member.node] = item
                        ctx.record("process", item)  # before the signal
                    why = self._send(member, signal.SIGSTOP)
                if why is not None:
                    notes[member.node] = why
            for run, group in self._groups(pending.values(), procs).items():
                if run in frozen:
                    continue
                cgroup = next(m.cgroup for m in pending.values() if m.run == run and m.cgroup)
                try:
                    already = (group / "cgroup.freeze").read_text().strip() == "1"
                except OSError:
                    already = False
                if not already or ("freeze", cgroup) in held:
                    ctx.record("process", {"freeze": cgroup, "run": run})
                self._write(group / "cgroup.freeze", "1")
                frozen[run] = group
            try:
                procs = self.observer.snapshot(max(ctx.remaining(), FLOOR_S))
                observed = time.monotonic()
                again = [m for m in ctx.expand(procs) if m.node not in pending]
            except ObserveError as exc:
                lost = str(exc)
                break
            for member in again:
                pending[member.node] = member
            running = [
                m
                for n, m in pending.items()
                if n not in notes and not self._stopped(m, procs, frozen)
            ]
            if not running and not again:
                break
            if ctx.expired():
                overtime += 1  # one more round for what has not been signalled yet
                if overtime > 3 or all(m.node in seen for m in again):
                    break
            time.sleep(POLL_S)
        late = observed > ctx.deadline
        results = []
        for node, member in pending.items():
            note = f"found by {member.via}"
            if node in notes:
                results.append(Result(node, "failed", f"{notes[node]}; {note}"))
                continue
            if lost:
                results.append(Result(node, "requested", f"cannot observe: {lost}", undo.get(node)))
                continue
            proc = procs.get(member.pid)
            alive = proc is not None and proc.start == member.start
            stopped = self._stopped(member, procs, frozen) and not late
            if not alive:
                note += "; gone"
            results.append(
                Result(
                    node,
                    "confirmed" if stopped else "requested",
                    note,
                    undo.get(node) if alive else None,
                )
            )
        return results

    def _stopped(self, member: Member, procs: Mapping[int, Proc], frozen: dict[str, Path]) -> bool:
        proc = procs.get(member.pid)
        if proc is None or proc.start != member.start:
            return True  # gone is as stopped as it gets
        if proc.state.startswith(STOPPED):
            return True
        group = frozen.get(member.run)
        return group is not None and _frozen(group) and _contains(group, member.pid)

    # ----------------------------------------------------------------------- terminate

    def terminate(self, targets: Sequence[Member], ctx: Context) -> list[Result]:
        pending: dict[str, Member] = {m.node: m for m in targets}
        notes: dict[str, str] = {}
        try:
            procs = self._table(pending.values())
        except ObserveError as exc:
            return [Result(n, "requested", f"cannot observe, nothing sent: {exc}") for n in pending]
        groups = self._groups(pending.values(), procs)
        for node, member in pending.items():
            proc = procs.get(member.pid)
            if proc is None or proc.start != member.start:
                continue
            why = self._refusal(member, proc, procs, ctx)
            if why is None:
                why = self._send(member, signal.SIGKILL)  # sent even if the deadline passed
            if why is not None:
                notes[node] = why
        for group in groups.values():
            self._write(group / "cgroup.kill", "1")
        while True:
            try:
                procs = self.observer.snapshot(max(ctx.remaining(), FLOOR_S))
                observed = time.monotonic()
            except ObserveError as exc:
                return [Result(n, "requested", f"cannot observe: {exc}") for n in pending]
            alive = {
                n for n, m in pending.items() if m.pid in procs and procs[m.pid].start == m.start
            }
            if not alive - set(notes) or ctx.expired():
                break
            time.sleep(POLL_S)
        late = observed > ctx.deadline
        results = []
        for node, member in pending.items():
            note = f"found by {member.via}"
            if node in notes:
                results.append(Result(node, "failed", f"{notes[node]}; {note}"))
            elif node in alive or late:
                results.append(Result(node, "requested", f"not confirmed gone; {note}"))
            else:
                results.append(Result(node, "confirmed", note))
        return results

    # ----------------------------------------------------------------------- release

    def release(self, record: Sequence[Mapping[str, Any]], ctx: Context) -> list[Result]:
        """Thaw and continue what a halt stopped. Identity is re-checked first."""
        results = []
        for item in record:
            run = str(item["run"])
            if "freeze" in item:
                group = own_cgroup(str(item["freeze"]), run, self.cgroup_root)
                target = f"cgroup:{run}"
                if group is None:
                    results.append(Result(target, "confirmed", "cgroup already gone"))
                    continue
                try:
                    (group / "cgroup.freeze").write_text("0")
                except OSError as exc:
                    results.append(Result(target, "failed", f"cannot thaw: {exc}"))
                else:
                    results.append(Result(target, "confirmed", "thawed"))
                continue
            member = Member(
                node=f"proc_{item['pid']}_{item['start']}",
                pid=int(item["pid"]),
                start=str(item["start"]),
                run=run,
                uid=item.get("uid"),
            )
            try:
                procs = self.observer.snapshot(5.0)
            except ObserveError as exc:
                results.append(Result(member.node, "failed", str(exc)))
                continue
            proc = procs.get(member.pid)
            if proc is None or proc.start != member.start:
                results.append(Result(member.node, "confirmed", "already gone"))
                continue
            why = refusal(
                proc, procs, invoking_uid=ctx.invoking_uid, also=member.uid
            ) or self._send(member, signal.SIGCONT)
            results.append(
                Result(member.node, "failed", why)
                if why
                else Result(member.node, "confirmed", "continued")
            )
        return results
