"""The enrollment supervisor (ADR-0009, DD-38/46/47, M2 design §7).

``run`` launches an agent behind a gate: the command execs only after the choke allowed it and the
root edge is on record. ``attach`` enrolls a running process, best-effort. Neither suspends or
kills anything (M3). The supervisor holds no credentials and makes no policy decision of its own.
"""

from __future__ import annotations

import contextlib
import os
import pwd
import re
import select
import shutil
import signal
import stat
import sys
import time
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NoReturn

from agenthalt.choke import RuntimeChoke
from agenthalt.ids import new_halt_id, validate_id
from agenthalt.journal import Journal, JournalError
from agenthalt.lineage import AdapterCredential, LineageError, LineageRegistry
from agenthalt.logs import get_logger
from agenthalt.observe import RUN_ENV, ObserveError, Observer, Proc, SystemObserver
from agenthalt.scopes import Target
from agenthalt.store import Store, StoreError
from agenthalt.subtree import (
    Discovery,
    Graph,
    check_lineage,
    discover,
    separately_enrolled,
)

__all__ = [
    "LIVENESS_GAP",
    "AttachResult",
    "EnrollmentError",
    "RunResult",
    "SpawnRefusedError",
    "Supervisor",
    "UserSpec",
    "effective",
    "invoking_ids",
    "prepare_cgroup",
    "resolve_user",
]

LIVENESS_GAP = "an unobserved process still holds the run's liveness handle"
_log = get_logger("supervisor")


class EnrollmentError(Exception):
    """Enrollment was refused; nothing is running that was not already."""


class SpawnRefusedError(EnrollmentError):
    """The choke denied the spawn (the post-halt spawn rule)."""


@dataclass(frozen=True)
class RunResult:
    run_id: str
    exit_code: int
    gaps: tuple[str, ...] = ()
    survivors: tuple[int, ...] = ()
    """Observed pids still alive after the agent exited. Nothing was done to them."""


@dataclass(frozen=True)
class AttachResult:
    run_id: str
    created: bool
    verified: bool
    members: tuple[str, ...]


@dataclass(frozen=True)
class UserSpec:
    name: str
    uid: int
    gid: int
    groups: tuple[int, ...]
    home: str


# --------------------------------------------------------------------------- privileges


def invoking_ids(
    env: Mapping[str, str] | None = None, *, euid: int | None = None
) -> tuple[int, int]:
    """The human behind the command: ``SUDO_UID``/``SUDO_GID`` when run under sudo."""
    env = os.environ if env is None else env
    euid = os.geteuid() if euid is None else euid
    if euid == 0:
        with contextlib.suppress(KeyError, ValueError):
            return int(env["SUDO_UID"]), int(env["SUDO_GID"])
    return os.getuid(), os.getgid()


def resolve_user(
    name: str,
    home: Path,
    *,
    euid: int | None = None,
    invoking_uid: int | None = None,
    lookup: Callable[[str], pwd.struct_passwd] = pwd.getpwnam,
    groups: Callable[[str, int], list[int]] = os.getgrouplist,
) -> UserSpec:
    """Validate ``--user``. Refuses anything that would not actually separate the agent."""
    euid = os.geteuid() if euid is None else euid
    invoking_uid = invoking_ids()[0] if invoking_uid is None else invoking_uid
    if euid != 0:
        raise EnrollmentError("--user needs root: run it with sudo")
    try:
        entry = lookup(name)
    except KeyError:
        raise EnrollmentError(f"no such user: {name}") from None
    if entry.pw_uid == 0:
        raise EnrollmentError("--user must not be root")
    if entry.pw_uid == invoking_uid:
        raise EnrollmentError("--user is yourself: that separates nothing")
    member_of = set(groups(name, entry.pw_gid))
    for path in (home, *home.parents):
        if not path.exists():
            continue
        info = path.stat()
        writable = info.st_mode & stat.S_IWOTH or (
            info.st_mode & stat.S_IWGRP and info.st_gid in member_of
        )
        if info.st_uid == entry.pw_uid or (writable and not info.st_mode & stat.S_ISVTX):
            raise EnrollmentError(
                f"the state directory is not safe from {name}: {path} is theirs or writable by them"
            )
    return UserSpec(
        name,
        entry.pw_uid,
        entry.pw_gid,
        tuple(groups(name, entry.pw_gid)),
        entry.pw_dir,
    )


@contextlib.contextmanager
def effective(uid: int, gid: int) -> Iterator[None]:
    """Temporarily change effective ids (only a process started as root can)."""
    before = os.geteuid(), os.getegid()
    if (uid, gid) == before:
        yield
        return
    os.seteuid(0)
    os.setegid(gid)
    os.seteuid(uid)
    try:
        yield
    finally:
        os.seteuid(0)
        os.setegid(before[1])
        os.seteuid(before[0])


# --------------------------------------------------------------------------- containment


def prepare_cgroup(
    run_id: str,
    *,
    root: Path = Path("/sys/fs/cgroup"),
    self_cgroup: Path = Path("/proc/self/cgroup"),
) -> tuple[Path, str]:
    """Create the run's cgroup v2 child group. No delegation means no enrollment."""
    hint = "run under `systemd-run --user --scope` or enable cgroup delegation"
    if not (root / "cgroup.controllers").exists():
        raise EnrollmentError("cgroup v2 is not mounted: enrollment refused")
    try:
        own = next(
            line[3:].strip()
            for line in self_cgroup.read_text().splitlines()
            if line.startswith("0::")
        )
        name = f"{own.rstrip('/')}/agenthalt-{run_id}"
        group = root / name.lstrip("/")
        group.mkdir()
    except (OSError, StopIteration) as exc:
        raise EnrollmentError(f"cannot create a cgroup for the run ({exc}); {hint}") from None
    return group, name


# --------------------------------------------------------------------------- the child


def _child(
    gate: int,
    errors: int,
    alive: int,
    exe: str,
    cmd: Sequence[str],
    env: dict[str, str],
    user: UserSpec | None,
) -> NoReturn:  # pragma: no cover - runs in the forked child, before exec
    try:
        os.set_inheritable(alive, True)
        if os.read(gate, 1) != b"1":
            os._exit(127)  # refused, or the supervisor died: the command never runs
        os.setpgid(0, 0)  # only now: the root edge is on record
        for name in ("SIGINT", "SIGTERM", "SIGHUP", "SIGPIPE", "SIGXFSZ", "SIGTTOU"):
            signal.signal(getattr(signal, name), signal.SIG_DFL)
        if user is not None:
            os.setgroups(list(user.groups))
            os.setgid(user.gid)
            os.setuid(user.uid)
        os.execve(exe, list(cmd), env)  # noqa: S606 - launching the operator's command is the job
    except OSError as exc:
        os.write(errors, str(exc).encode())
    finally:
        os._exit(127)


def default_containment() -> str:
    return "cgroup" if sys.platform == "linux" else "pgroup"


def _default_name(command: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "-", Path(command).name)[:128] or "agent"


class Supervisor:
    def __init__(
        self,
        home: Path | str,
        *,
        segment_max_entries: int = 10_000,
        cache_ttl_s: int = 0,
        observer: Observer | None = None,
        containment: str | None = None,
        cgroup_root: Path = Path("/sys/fs/cgroup"),
        actor: str = "agenthalt",
        poll_s: float = 0.25,
    ) -> None:
        self.home = Path(home).resolve()
        self.journal = Journal(self.home, segment_max_entries=segment_max_entries)
        self.registry = LineageRegistry(
            self.home, journal=self.journal, segment_max_entries=segment_max_entries
        )
        self.cache_ttl_s = cache_ttl_s
        self.observer = observer if observer is not None else SystemObserver()
        self.containment = containment or default_containment()
        self.cgroup_root = cgroup_root
        self.actor = actor
        self.poll_s = poll_s

    # ------------------------------------------------------------------- shared

    def _adapter(self, name: str = "supervisor") -> AdapterCredential:
        return self.registry.register_adapter(name, "process")

    def _graph(self) -> Graph:
        return Graph(self.registry.read().edges)

    def _snapshot(self) -> dict[int, Proc]:
        try:
            return self.observer.snapshot(5.0)
        except ObserveError as exc:
            raise EnrollmentError(str(exc)) from None

    def _enclosing(
        self, graph: Graph, procs: dict[int, Proc], pid: int, hint: str | None
    ) -> list[str]:
        """Enrolled nodes ``pid`` is running inside, nearest first, by process ancestry."""
        index = graph.process_index()
        found: list[str] = []
        current, seen = pid, set()
        while current in procs and current not in seen:
            seen.add(current)
            node = index.get((current, procs[current].start))
            if node is not None:
                found.append(node)
            current = procs[current].ppid
        if hint and hint not in found:
            found.append(hint)
        return found

    def _refusal(self, run_id: str, name: str, parents: list[str], graph: Graph) -> str | None:
        """The post-halt spawn rule (DD-05): ``None`` when the spawn may proceed."""
        store = Store(self.home, journal=self.journal)
        health = store.health()
        if not store.path.exists() and not health.armed:
            store.ensure()  # a first run: there is no halt to lose
        elif health.status == "recovering":
            store.rebuild()
        health = store.health()
        if health.status != "ok" or health.signal is not None:
            return f"store_integrity: {health.detail}"
        choke = RuntimeChoke(store, cache_ttl_s=self.cache_ttl_s)
        read = self.registry.read()
        if not read.complete:
            return "lineage_gap: the lineage could not be read"
        intact = not read.findings
        ancestors: list[str] = []
        for parent in parents:
            try:
                validate_id(parent, what="parent run")
            except ValueError:
                return "lineage_gap: the parent run hint is not a run id"
            intact = intact and parent in graph
            ancestors += [parent, *graph.ancestors(parent)]
        # With no parent found, damaged lineage matters only if there is a halt it could hide.
        known = intact if parents else intact or not store.load().halts
        target = Target(
            agent=name, run=run_id, ancestors=tuple(dict.fromkeys(ancestors)), lineage_known=known
        )
        decision = choke.check(target)
        for parent in parents:
            if not decision.allow:
                break
            decision = check_lineage(choke, graph, parent, intact=intact)
        if decision.allow:
            return None
        reason = decision.reason.value if decision.reason else "denied"
        return f"{reason}" + (f" (halt {decision.halt_id})" if decision.halt_id else "")

    # ------------------------------------------------------------------- run

    def run(
        self, command: Sequence[str], *, name: str | None = None, user: str | None = None
    ) -> RunResult:
        if not command:
            raise EnrollmentError("no command given")
        exe = shutil.which(command[0])
        if exe is None:
            raise EnrollmentError(f"command not found: {command[0]}")
        exe = os.path.abspath(exe)
        name = validate_id(name or _default_name(command[0]), what="agent name")
        spec = None if user is None else resolve_user(user, self.home)
        run_id = "run_" + new_halt_id()[4:]
        group: tuple[Path, str] | None = None
        if self.containment == "cgroup":
            group = prepare_cgroup(run_id, root=self.cgroup_root)
        try:
            if spec is not None:
                self._record_user(run_id, spec.uid)
            return self._launch(run_id, name, exe, command, spec, group)
        except (LineageError, JournalError, StoreError, OSError) as exc:
            raise EnrollmentError(f"enrollment failed, the command did not run: {exc}") from None
        finally:
            if group is not None:
                with contextlib.suppress(OSError):
                    group[0].rmdir()  # stays while the cgroup has members

    def _record_user(self, run_id: str, uid: int) -> None:
        """A root-owned note of the ``--user`` uid, which nothing running as the operator can
        forge: it is what lets a ``sudo`` halt signal that user (and no other)."""
        if os.geteuid() != 0:
            return
        directory = self.registry.home / "keys" / "users"
        with effective(*invoking_ids()):
            directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        fd = os.open(directory / run_id, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        try:
            os.write(fd, f"{run_id} {uid}".encode())
        finally:
            os.close(fd)

    def _launch(
        self,
        run_id: str,
        name: str,
        exe: str,
        command: Sequence[str],
        spec: UserSpec | None,
        group: tuple[Path, str] | None,
    ) -> RunResult:
        env = {k: v for k, v in os.environ.items() if not k.startswith(("AGENTHALT_", "SUDO_"))}
        env[RUN_ENV] = run_id
        if spec is not None:
            env.update(HOME=spec.home, USER=spec.name, LOGNAME=spec.name)
        operator = invoking_ids()  # state is never written as root
        elevated = (os.geteuid(), os.getegid())  # what observing and signalling need
        gate_r, gate_w = os.pipe()
        err_r, err_w = os.pipe()
        live_r, live_w = os.pipe()
        pid = os.fork()
        if pid == 0:  # pragma: no cover - the child
            for fd in (gate_w, err_r, live_r):
                os.close(fd)
            _child(gate_r, err_w, live_w, exe, command, env, spec)
        for fd in (gate_r, err_w, live_w):
            os.close(fd)
        opened = False
        terminal = _Terminal()
        try:
            if group is not None:
                (group[0] / "cgroup.procs").write_text(str(pid))
            with effective(*operator):
                meta = self._enroll(run_id, name, pid, spec, group)
                os.setpgid(pid, pid)  # the child does the same; whichever is first wins
                terminal.give(pid)  # before exec, so the agent never reads from the background
                os.write(gate_w, b"1")
                opened = True
                failure = os.read(err_r, 4096)  # EOF once exec succeeds (the fd is close-on-exec)
                if failure:
                    self._finding(
                        "exec_failed", run=run_id, detail=failure.decode(errors="replace")
                    )
                    raise EnrollmentError(f"cannot execute {command[0]}: {failure.decode()}")
                _log.info("run.started", extra={"fields": {"run": run_id, "pid": pid}})
                return self._supervise(run_id, meta, pid, live_r, terminal, signal_as=elevated)
        except BaseException:
            os.close(gate_w)
            gate_w = -1
            if not opened:
                os.waitpid(pid, 0)  # the gate closed: the child exits without running anything
            else:
                with contextlib.suppress(ChildProcessError):
                    os.waitpid(pid, os.WNOHANG)
            raise
        finally:
            terminal.take_back()
            for fd in (gate_w, err_r, live_r):
                if fd >= 0:
                    os.close(fd)

    def _enroll(
        self,
        run_id: str,
        name: str,
        pid: int,
        spec: UserSpec | None,
        group: tuple[Path, str] | None,
    ) -> dict[str, Any]:
        """Decide, then record the root edge. A refused spawn is recorded too."""
        procs = self._snapshot()
        child, me = procs.get(pid), procs.get(os.getpid())
        if child is None or me is None:
            raise EnrollmentError("cannot observe the new process")
        graph = self._graph()
        parents = self._enclosing(graph, procs, os.getpid(), os.environ.get(RUN_ENV))
        parent = parents[0] if parents else None
        refusal = self._refusal(run_id, name, parents, graph)
        supervisor_id = "sup_" + run_id[4:]
        meta: dict[str, Any] = {
            "enrollment": "run",
            "name": name,
            "pid": pid,
            "start": child.start,
            "pgid": pid,
            "uid": spec.uid if spec else child.uid,
            "marker": run_id,
            "containment": self.containment,
            "supervisor": {"pid": me.pid, "start": me.start},
        }
        if group is not None:
            meta["cgroup"] = group[1]
        if spec is not None:
            meta["user"] = spec.name
        known_parent = parent if parent is not None and parent in graph else supervisor_id
        self.registry.append_edges(
            self._adapter(),
            [{"parent_run": known_parent, "child_run": run_id, "child": meta}],
        )
        if refusal is not None:
            self._finding("post_halt_spawn", run=run_id, parent=parent, why=refusal)
            raise SpawnRefusedError(f"spawn refused: {refusal}")
        return meta

    def _finding(self, finding: str, **payload: Any) -> None:
        self.journal.append("finding", actor=self.actor, payload={"finding": finding, **payload})

    # ------------------------------------------------------------------- supervision

    def _supervise(
        self,
        run_id: str,
        meta: dict[str, Any],
        pid: int,
        live_r: int,
        terminal: _Terminal,
        *,
        signal_as: tuple[int, int],
    ) -> RunResult:
        watch = _Watch(self, run_id, meta)

        def forward(signum: int, frame: object = None) -> None:
            with contextlib.suppress(OSError), effective(*signal_as):
                os.killpg(pid, signum)

        previous = {}
        with contextlib.suppress(ValueError):  # not the main thread: nothing to forward
            for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
                previous[signum] = signal.signal(signum, forward)
        frozen = False
        try:
            while True:
                done, status = os.waitpid(pid, os.WNOHANG | os.WUNTRACED | os.WCONTINUED)
                if done and os.WIFCONTINUED(status):
                    if frozen:
                        frozen = False
                        terminal.give(pid)
                elif done and os.WIFSTOPPED(status):
                    if os.WSTOPSIG(status) == signal.SIGSTOP and not frozen:
                        frozen = True
                        terminal.take_back()
                        print(
                            f"agenthalt: {run_id} is frozen (see `agenthalt status`)",
                            file=sys.stderr,
                        )
                    if os.WSTOPSIG(status) == signal.SIGTSTP and terminal.interactive:
                        terminal.take_back()  # pragma: no cover - needs a job-control shell
                        os.kill(os.getpid(), signal.SIGSTOP)  # pragma: no cover
                        terminal.give(pid)  # pragma: no cover
                        forward(signal.SIGCONT)  # pragma: no cover
                elif done:
                    break
                watch.poll(signal_as)
                time.sleep(self.poll_s)
        finally:
            terminal.take_back()
            for signum, handler in previous.items():
                signal.signal(signum, handler)
        time.sleep(min(self.poll_s, 0.1))
        live = watch.poll(signal_as)
        code = os.waitstatus_to_exitcode(status)
        gaps = list(watch.gaps)
        if not live and not _closed(live_r):
            watch.gap(run_id, 0, LIVENESS_GAP)
            gaps = list(watch.gaps)
        return RunResult(
            run_id,
            128 - code if code < 0 else code,
            tuple(why for _, why in gaps),
            tuple(sorted(live)),
        )

    # ------------------------------------------------------------------- attach

    def attach(self, pid: int, *, name: str | None = None) -> AttachResult:
        procs = self._snapshot()
        target = procs.get(pid)
        if target is None:
            raise EnrollmentError(f"no such process: {pid}")
        if target.uid != invoking_ids()[0]:
            raise EnrollmentError(f"process {pid} belongs to another user; nothing enrolled")
        if name is not None:
            validate_id(name, what="agent name")
        try:
            with effective(*invoking_ids()):
                return self._attach(target, procs, name or f"pid-{pid}")
        except (LineageError, JournalError, StoreError, OSError) as exc:
            raise EnrollmentError(f"attach failed: {exc}") from None

    def _attach(self, target: Proc, procs: dict[int, Proc], name: str) -> AttachResult:
        graph = self._graph()
        existing = graph.process_index().get((target.pid, target.start))
        if existing is not None:
            verified = existing in self.registry.read().verified
            return AttachResult(existing, False, verified, tuple(graph.walk([existing])[0]))
        try:
            hint = self.observer.run_markers(5.0).get(target.pid)
        except ObserveError as exc:
            raise EnrollmentError(str(exc)) from None
        parents = self._enclosing(graph, procs, target.ppid, hint if hint in graph else None)
        run_id = "run_" + new_halt_id()[4:]
        meta = {
            "enrollment": "attach",
            "name": name,
            "pid": target.pid,
            "start": target.start,
            "pgid": target.pgid,
            "uid": target.uid,
            "containment": "observed",
        }
        credential = self._adapter()
        self.registry.append_edges(
            credential,
            [
                {
                    "parent_run": parents[0] if parents else "sup_" + run_id[4:],
                    "child_run": run_id,
                    "child": meta,
                }
            ],
        )
        watch = _Watch(self, run_id, meta)
        # a full walk: the process is still there and a second look finds nothing new
        first = watch.poll(None)
        second_ok = watch.poll(None)
        verified = (
            not watch.blind and target.pid in first and target.pid in second_ok and not watch.grew
        )
        if verified:
            self.registry.mark_verified(credential, run_id)
        members = tuple(self._graph().walk([run_id])[0])
        return AttachResult(run_id, True, verified, members)


class _Watch:
    """Repeated discovery for one enrolled run."""

    def __init__(self, supervisor: Supervisor, run_id: str, meta: dict[str, Any]) -> None:
        self.sup = supervisor
        self.run_id = run_id
        self.meta = meta
        self.known = {(int(meta["pid"]), str(meta["start"])): run_id}
        self.members = {run_id}
        self.gaps: dict[tuple[str, str], None] = {}
        self.blind = False
        self.grew = False
        self.polls = 0
        self.pending: list[dict[str, Any]] = []
        self.unrecorded_gaps: dict[tuple[str, str], int] = {}

    def gap(self, node: str, pid: int, why: str) -> None:
        if (node, why) in self.gaps:
            return
        self.gaps[(node, why)] = None
        self.unrecorded_gaps[(node, why)] = pid
        self._flush()

    def _flush(self) -> None:
        """Write what is still owed to the record; whatever fails is tried again."""
        if self.pending:
            with self._recording():
                self.sup.registry.append_edges(
                    self.sup._adapter("process-observer"), list(self.pending)
                )
                self.pending.clear()
        for (node, why), pid in list(self.unrecorded_gaps.items()):
            with self._recording():
                self.sup.registry.record_finding(
                    "lineage_gap",
                    {"run": self.run_id, "node": node, "pid": pid, "why": why},
                    actor=self.sup.actor,
                    unique=("node", "why"),
                )
                del self.unrecorded_gaps[(node, why)]

    @contextlib.contextmanager
    def _recording(self) -> Iterator[None]:
        """A damaged registry or journal must not end supervision of a running agent."""
        try:
            yield
        except Exception as exc:  # nothing about the record may end supervision
            self.blind = True
            why = f"supervision degraded: cannot record ({exc})"
            if (self.run_id, why) not in self.gaps:
                self.gaps[(self.run_id, why)] = None
                _log.error("supervise.degraded", extra={"fields": {"error": str(exc)}})

    def _discover(self, procs: dict[int, Proc], markers: dict[int, str]) -> Discovery:
        return discover(
            self.run_id,
            self.meta,
            dict(self.known),
            set(self.members),
            procs,
            markers=markers,
            cgroup_of=self.sup.observer.cgroup_of,
            owned=self.meta.get("enrollment") == "run",  # our group cannot be reused while we live
        )

    def poll(self, observe_as: tuple[int, int] | None) -> set[int]:
        """Observe once, record what is new, and return the live member pids."""
        try:
            with effective(*(observe_as or (os.geteuid(), os.getegid()))):
                procs = self.sup.observer.snapshot(5.0)
                markers = self.sup.observer.run_markers(5.0)
        except ObserveError as exc:
            self.blind = True
            _log.warning("observe.failed", extra={"fields": {"error": str(exc)}})
            self.gap(self.run_id, 0, "supervision degraded: processes could not be observed")
            return set()
        found = self._discover(procs, markers)
        self.polls += 1
        if found.edges:
            with self._recording():
                # a nested supervisor may have enrolled one of these under its own id
                for key, node in self.sup._graph().process_index().items():
                    self.known.setdefault(key, node)
                    if node != self.run_id and (int(key[0]), str(key[1])) in self.known:
                        self.known[key] = node
            found = self._discover(procs, markers)
        for edge in found.edges:  # remembered even if it cannot be recorded
            child = edge["child"]
            self.known[(child["pid"], child["start"])] = edge["child_run"]
            self.members.add(edge["child_run"])
        if found.edges:
            self.grew = self.polls > 1
            self.pending.extend(found.edges)
        self._flush()
        live = set()
        for key, node in self.known.items():
            pid, start = key
            if pid in procs and procs[pid].start == start:
                live.add(pid)
                self.members.add(node)
        if found.gaps:
            separate: set[int] = set()
            with self._recording():
                separate = separately_enrolled(self.sup._graph(), self.run_id, procs)
            for node, pid, why in found.gaps:
                if pid not in separate:
                    self.gap(node, pid, why)
        return live


class _Terminal:
    """Hand the controlling terminal to the agent's process group, and take it back."""

    def __init__(self) -> None:
        self.interactive = False
        with contextlib.suppress(OSError):
            self.interactive = os.isatty(0) and os.tcgetpgrp(0) == os.getpgrp()

    def _set(self, group: int) -> None:
        if not self.interactive:
            return
        previous = signal.signal(signal.SIGTTOU, signal.SIG_IGN)
        try:
            with contextlib.suppress(OSError):
                os.tcsetpgrp(0, group)
        finally:
            signal.signal(signal.SIGTTOU, previous)

    def give(self, pid: int) -> None:
        self._set(pid)

    def take_back(self) -> None:
        self._set(os.getpgrp())


def _closed(fd: int) -> bool:
    """True once every holder of the write end is gone."""
    ready, _, _ = select.select([fd], [], [], 0)
    return bool(ready) and os.read(fd, 1) == b""
