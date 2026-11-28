"""The built-in egress fallback (DD-45, DD-51, M3 design §7): Linux only, by cgroup.

Rules match the run's own cgroup and nothing else, so the operator's network is never touched. Where
the cut cannot be made safely the answer is ``unsupported``.
"""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from agenthalt.executors import Context, Member, Result
from agenthalt.observe import ObserveError, Observer
from agenthalt.process_exec import own_cgroup

__all__ = ["EgressExecutor", "unsupported_reason"]

TOOLS = ("iptables", "ip6tables")
Runner = Callable[[Sequence[str]], "tuple[int, str]"]


def _run(command: Sequence[str]) -> tuple[int, str]:
    try:
        done = subprocess.run(  # noqa: S603 - resolved binary, fixed flags, validated ids
            list(command), capture_output=True, text=True, timeout=5, check=False
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return 127, str(exc)
    return done.returncode, done.stdout if done.returncode == 0 else done.stderr.strip()


def unsupported_reason(
    *,
    platform: str | None = None,
    euid: int | None = None,
    which: Callable[[str], str | None] = shutil.which,
) -> str | None:
    """Why this host cannot make the cut at all, or ``None``."""
    platform = sys.platform if platform is None else platform
    if platform == "darwin":
        return "no network cut on macOS in this version (planned for 0.3.0)"
    if platform != "linux":
        return f"no network cut on {platform}"
    if (os.geteuid() if euid is None else euid) != 0:
        return "the network cut needs root (run the halt with sudo)"
    missing = [tool for tool in TOOLS if which(tool) is None]
    if missing:
        return f"{' and '.join(missing)} not found"
    return None


def _rules(cgroup: str, tag: str) -> list[list[str]]:
    """In insertion order: each goes in at the top, so the TCP reset ends up first."""
    match = ["-m", "cgroup", "--path", cgroup.strip("/"), "-m", "comment", "--comment", tag]
    return [
        [*match, "-j", "REJECT"],
        ["-p", "tcp", *match, "-j", "REJECT", "--reject-with", "tcp-reset"],
    ]


class EgressExecutor:
    name = "egress-fallback"
    layer = "sandbox"
    version = "1"
    attestation = "self"
    grace_s = 10.0

    def __init__(
        self,
        observer: Observer,
        *,
        runner: Runner = _run,
        cgroup_root: Path = Path("/sys/fs/cgroup"),
        unsupported: Callable[[], str | None] = unsupported_reason,
    ) -> None:
        self.observer = observer
        self.runner = runner
        self.cgroup_root = cgroup_root
        self.unsupported = unsupported

    def block(self, targets: Sequence[Member], ctx: Context) -> list[Result]:
        runs: dict[str, list[Member]] = {}
        for member in targets:
            runs.setdefault(member.run, []).append(member)
        why = self.unsupported()
        if why is not None:
            return [Result(run, "unsupported", why) for run in runs]
        return [self._block_run(run, members, ctx) for run, members in runs.items()]

    def _block_run(self, run: str, members: list[Member], ctx: Context) -> Result:
        cgroup = members[0].cgroup
        if own_cgroup(cgroup, run, self.cgroup_root) is None or cgroup is None:
            return Result(run, "unsupported", "the run has no cgroup of its own")
        tag = f"agenthalt:{ctx.halt_id}:{run}"
        undo = {"halt": ctx.halt_id, "run": run}
        ctx.record("sandbox", undo)  # before the first rule goes in
        for tool in TOOLS:
            for rule in _rules(cgroup, tag):
                if self.runner([tool, "-w", "-C", "OUTPUT", *rule])[0] == 0:
                    continue
                code, message = self.runner([tool, "-w", "-I", "OUTPUT", "1", *rule])
                if code != 0:
                    return Result(run, "failed", f"{tool}: {message}", undo)
            for rule in _rules(cgroup, tag):  # read back: the kernel is the witness
                if self.runner([tool, "-w", "-C", "OUTPUT", *rule])[0] != 0:
                    return Result(run, "failed", f"{tool}: the rule is not in place", undo)
        outside = []
        for member in members:
            try:
                current = self.observer.probe([member.pid]).get(member.pid)
            except ObserveError:
                outside.append(member.pid)
                continue
            if current is None or current.start != member.start:
                continue
            where = self.observer.cgroup_of(member.pid) or ""
            if where != cgroup and not where.startswith(cgroup.rstrip("/") + "/"):
                outside.append(member.pid)
        if outside:
            listed = ", ".join(map(str, sorted(outside)))
            return Result(run, "failed", f"not cut: pid {listed} is outside the run's cgroup", undo)
        if ctx.expired():
            return Result(run, "requested", "rules in place after the deadline", undo)
        return Result(run, "confirmed", "outbound traffic of the run's cgroup rejected", undo)

    def _tagged(self, tool: str, tag: str) -> tuple[list[list[str]], str]:
        code, listing = self.runner([tool, "-w", "-S", "OUTPUT"])
        if code != 0:
            return [], f"{tool}: {listing}"
        rules = (shlex.split(line) for line in listing.splitlines() if line.startswith("-A "))
        return [rule for rule in rules if tag in rule], ""

    def release(self, record: Sequence[Mapping[str, Any]], ctx: Context) -> list[Result]:
        """Delete by rule, never by position: other rules come and go while we work."""
        results = []
        for item in record:
            halt_id, run = str(item["halt"]), str(item["run"])
            tag = f"agenthalt:{halt_id}:{run}"
            problem = ""
            for tool in TOOLS:
                rules, why = self._tagged(tool, tag)
                for rule in rules:
                    code, message = self.runner([tool, "-w", "-D", *rule[1:]])
                    if code != 0:
                        why = f"{tool}: {message}"
                left, listing_error = self._tagged(tool, tag)
                why = why or listing_error or (f"{tool}: a rule is still there" if left else "")
                problem = why or problem
            results.append(
                Result(run, "failed", problem)
                if problem
                else Result(run, "confirmed", "network cut removed")
            )
        return results
