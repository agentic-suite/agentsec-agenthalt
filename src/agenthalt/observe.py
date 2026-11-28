"""Process observation (ADR-0008, M2 design §4/§7): what containment can actually act on.

Linux reads ``/proc``; macOS asks ``/bin/ps``. Stdlib only. A listing that cannot be taken raises
``ObserveError`` — the caller reports an incomplete walk, never an empty one.
"""

from __future__ import annotations

import calendar
import os
import re
import subprocess
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

__all__ = ["RUN_ENV", "ObserveError", "Observer", "Proc", "SystemObserver", "node_id"]

RUN_ENV = "AGENTHALT_RUN_ID"
_MARKER = re.compile(rf"(?:^|[\s\0]){RUN_ENV}=(run_[0-9A-Za-z]+)")
_PS = "/bin/ps"


class ObserveError(Exception):
    """The process table could not be read."""


@dataclass(frozen=True)
class Proc:
    pid: int
    ppid: int
    pgid: int
    sid: int
    uid: int
    start: str
    """Start time, digits only. Together with ``pid`` it identifies a process across pid reuse."""
    state: str = field(default="", compare=False)
    """Scheduler state letters; ``T`` or ``t`` means stopped. Not part of the identity."""


def node_id(proc: Proc) -> str:
    return f"proc_{proc.pid}_{proc.start}"


class Observer(Protocol):
    def snapshot(self, timeout_s: float = ...) -> dict[int, Proc]: ...

    def run_markers(self, timeout_s: float = ...) -> dict[int, str]: ...

    def cgroup_of(self, pid: int) -> str | None: ...

    def probe(self, pids: Sequence[int], timeout_s: float = ...) -> dict[int, Proc]: ...


def _exists(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except OSError:
        return True
    return True


def parse_stat(text: str, uid: int, boot: int = 0) -> Proc | None:
    """Parse ``/proc/<pid>/stat``. The command name may contain spaces and parentheses."""
    head, _, tail = text.rpartition(")")
    fields = tail.split()
    if not head or len(fields) < 20 or fields[0] in ("Z", "X"):
        return None  # a zombie cannot act
    return Proc(
        pid=int(head.split("(", 1)[0]),
        ppid=int(fields[1]),
        pgid=int(fields[2]),
        sid=int(fields[3]),
        uid=uid,
        start=f"{boot}{int(fields[19]):012d}",  # ticks alone repeat after a reboot
        state=fields[0],
    )


def parse_ps(output: str, sid_of: object = None) -> dict[int, Proc]:
    """Parse ``ps -axo pid=,ppid=,pgid=,uid=,stat=,lstart=`` (C locale)."""
    getsid = sid_of if callable(sid_of) else os.getsid
    table: dict[int, Proc] = {}
    for line in output.splitlines():
        fields = line.split(None, 5)
        if len(fields) != 6 or fields[4].startswith("Z"):
            continue
        try:
            pid, ppid, pgid, uid = (int(v) for v in fields[:4])
            started = calendar.timegm(time.strptime(fields[5].strip(), "%a %b %d %H:%M:%S %Y"))
        except ValueError:
            continue
        try:
            sid = int(getsid(pid))
        except OSError:
            sid = 0
        table[pid] = Proc(pid, ppid, pgid, sid, uid, str(int(started)), fields[4])
    return table


class SystemObserver:
    def __init__(self, *, platform: str = sys.platform, proc_root: Path = Path("/proc")) -> None:
        self.platform = platform
        self.proc_root = proc_root

    def _ps(self, args: list[str], timeout_s: float) -> str:
        try:
            done = subprocess.run(  # noqa: S603 - fixed binary and arguments
                [_PS, *args],
                capture_output=True,
                text=True,
                errors="replace",
                timeout=max(timeout_s, 0.001),
                env={"LC_ALL": "C", "TZ": "UTC0"},
                check=True,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise ObserveError(f"cannot list processes: {exc}") from None
        return done.stdout

    def _proc_dirs(self) -> list[Path]:
        try:
            return [p for p in self.proc_root.iterdir() if p.name.isdigit()]
        except OSError as exc:
            raise ObserveError(f"cannot list processes: {exc}") from None

    def _boot_time(self) -> int:
        """A number fixed for this boot. Not ``btime``, which moves when the clock is stepped."""
        try:
            text = (self.proc_root / "sys" / "kernel" / "random" / "boot_id").read_text()
            return int(text.strip().replace("-", "")[:8], 16)
        except (OSError, ValueError):
            return 0

    def snapshot(self, timeout_s: float = 5.0) -> dict[int, Proc]:
        if self.platform != "linux":
            return parse_ps(self._ps(["-axo", "pid=,ppid=,pgid=,uid=,stat=,lstart="], timeout_s))
        deadline = time.monotonic() + timeout_s
        boot = self._boot_time()
        table: dict[int, Proc] = {}
        for path in self._proc_dirs():
            if time.monotonic() > deadline:
                raise ObserveError("process listing ran past its deadline")
            try:
                proc = parse_stat(
                    (path / "stat").read_text(errors="replace"), path.stat().st_uid, boot
                )
            except OSError:
                continue  # exited while we were looking
            if proc is not None:
                table[proc.pid] = proc
        return table

    def probe(self, pids: Sequence[int], timeout_s: float = 5.0) -> dict[int, Proc]:
        """The given processes only: the cheap identity check made just before a signal."""
        if self.platform != "linux":
            try:
                listing = self._ps(
                    ["-o", "pid=,ppid=,pgid=,uid=,stat=,lstart=", "-p", ",".join(map(str, pids))],
                    timeout_s,
                )
            except ObserveError:
                if any(_exists(pid) for pid in pids):
                    raise
                return {}  # ps exits non-zero when none of them exists
            return parse_ps(listing)
        boot = self._boot_time()
        table: dict[int, Proc] = {}
        for pid in pids:
            path = self.proc_root / str(pid)
            try:
                proc = parse_stat(
                    (path / "stat").read_text(errors="replace"), path.stat().st_uid, boot
                )
            except OSError:
                continue
            if proc is not None:
                table[pid] = proc
        return table

    def run_markers(self, timeout_s: float = 5.0) -> dict[int, str]:
        """``pid -> run id`` for processes whose environment names an enrolled run.

        Only environments this user may read are visible. This finds a daemonized child that left
        the tree between two polls (M2 design §7, signal 2).
        """
        found: dict[int, str] = {}
        if self.platform != "linux":
            argv = dict(self._rows(["-axww", "-o", "pid=,command="], timeout_s))
            for pid, full in self._rows(["-axEww", "-o", "pid=,command="], timeout_s):
                plain = argv.get(pid)
                if plain is None or not full.startswith(plain):
                    continue  # cannot tell arguments from environment: do not guess
                match = _MARKER.findall(full[len(plain) :])
                if match:
                    found[pid] = match[-1]
            return found
        deadline = time.monotonic() + timeout_s
        for path in self._proc_dirs():
            if time.monotonic() > deadline:
                raise ObserveError("environment scan ran past its deadline")
            try:
                env = (path / "environ").read_bytes().split(b"\0")
            except OSError:
                continue
            for item in env:
                if item.startswith(RUN_ENV.encode() + b"="):
                    found[int(path.name)] = item.split(b"=", 1)[1].decode(errors="replace")
        return found

    def _rows(self, args: list[str], timeout_s: float) -> list[tuple[int, str]]:
        rows = []
        for line in self._ps(args, timeout_s).splitlines():
            pid, _, rest = line.strip().partition(" ")
            if pid.isdigit():
                rows.append((int(pid), rest.strip()))
        return rows

    def cgroup_of(self, pid: int) -> str | None:
        if self.platform != "linux":
            return None
        try:
            text = (self.proc_root / str(pid) / "cgroup").read_text()
        except OSError:
            return None
        return next((ln[3:] for ln in text.splitlines() if ln.startswith("0::")), None)
