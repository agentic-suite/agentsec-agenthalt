"""The credential executor (M4 design §3, WBS 4.1 and 4.2): revoke a subtree's grants via agentkeys.

The inventory is what each run declared with ``--grant`` when it was enrolled. Two kinds:

* ``agentkeys:session:<id>`` / ``agentkeys:agent:<id>``: revoked with ``agentkeys revoke``.
* ``static:<name>[@YYYY-MM-DD]``: a key nobody can revoke from here. It is listed as unrevocable,
  with its expiry if one was declared, and never reported as revoked.

agentkeys does not sign its answers yet, so a revoke is reported ``attestation: self``: agenthalt
vouches that agentkeys said so (DD-56).
"""

from __future__ import annotations

import json
import os
import pwd
import re
import shutil
import subprocess
import time
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any

from agenthalt.executors import Context, Result

__all__ = ["GRANT", "AgentkeysExecutor", "Grant", "parse_grant", "unrevocable"]

GRANT = re.compile(
    r"(?:agentkeys:(?:session|agent):[A-Za-z0-9_.:@-]{1,128}"
    r"|static:[A-Za-z0-9_.-]{1,128}(?:@\d{4}-\d{2}-\d{2})?)"
)
Runner = Callable[[Sequence[str], float, "Mapping[str, Any]"], "tuple[int, str]"]


def parse_grant(ref: str) -> str:
    if not GRANT.fullmatch(ref):
        raise ValueError(
            f"bad grant {ref!r}: use agentkeys:session:<id>, agentkeys:agent:<id> "
            "or static:<name>[@YYYY-MM-DD]"
        )
    return ref


@dataclass(frozen=True)
class Grant:
    ref: str
    run: str
    """The enrolled run that declared it."""


def unrevocable(ref: str) -> dict[str, Any]:
    name, _, expires = ref.partition("@")
    window = f"usable until {expires}" if expires else "usable until rotated (no expiry declared)"
    return {"ref": name, "expires": expires or None, "window_note": window}


def _run(command: Sequence[str], timeout: float, ids: Mapping[str, Any]) -> tuple[int, str]:
    try:
        done = subprocess.run(  # noqa: S603 - resolved binary, validated arguments
            list(command),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            **ids,
        )
    except subprocess.TimeoutExpired:
        return -1, "agentkeys did not answer in time"
    except (OSError, subprocess.SubprocessError) as exc:
        return 127, str(exc)
    return done.returncode, done.stdout or done.stderr


def _as_user(uid: int) -> dict[str, Any]:
    """Under sudo, agentkeys runs as the person halting, with their home: it is their broker."""
    if os.getuid() != 0 or uid == 0:
        return {}
    entry = pwd.getpwuid(uid)
    env = {**os.environ, "HOME": entry.pw_dir, "USER": entry.pw_name, "LOGNAME": entry.pw_name}
    ids: dict[str, Any] = {"user": uid, "group": entry.pw_gid, "env": env}
    if os.geteuid() == 0:  # only root may set the group list
        ids["extra_groups"] = os.getgrouplist(entry.pw_name, entry.pw_gid)
    return ids


def _find(uid: int) -> str | None:
    """sudo resets ``PATH``, so also look where the person halting installs their tools."""
    found = shutil.which("agentkeys")
    if found or os.getuid() != 0 or uid == 0:
        return found
    return shutil.which("agentkeys", path=f"{pwd.getpwuid(uid).pw_dir}/.local/bin")


class AgentkeysExecutor:
    name = "agentkeys"
    layer = "credentials"
    version = "1"
    attestation = "self"
    grace_s = 10.0

    def __init__(self, command: str | None = None, *, runner: Runner = _run) -> None:
        self.command = command
        self.runner = runner

    def revoke(self, targets: Sequence[Grant], ctx: Context) -> list[Result]:
        end = max(ctx.deadline, time.monotonic() + 2.0)  # one budget for all of them
        with ThreadPoolExecutor(max_workers=8) as pool:
            return list(pool.map(lambda grant: self._safely(grant, ctx, end), targets))

    def freeze(self, targets: Sequence[Grant], ctx: Context) -> list[Result]:
        results = []
        for grant in targets:
            if grant.ref.startswith("static:"):
                results.append(self._static(grant))
            else:
                why = (
                    "agentkeys has no issuance freeze yet; the grant stays usable (kill revokes it)"
                )
                results.append(Result(grant.ref, "unsupported", why))
        return results

    def release(self, record: Sequence[Mapping[str, Any]], ctx: Context) -> list[Result]:
        return []  # a revoke cannot be undone; a new grant is a new decision

    def _static(self, grant: Grant) -> Result:
        found = unrevocable(grant.ref)
        return Result(
            grant.ref, "unsupported", f"static key: cannot be revoked, {found['window_note']}"
        )

    def _safely(self, grant: Grant, ctx: Context, end: float) -> Result:
        """One grant's trouble never loses another grant's result."""
        try:
            return self._revoke(grant, ctx, end)
        except Exception as exc:
            return Result(grant.ref, "failed", f"agentkeys: {exc}")

    def _revoke(self, grant: Grant, ctx: Context, end: float) -> Result:
        if grant.ref.startswith("static:"):
            return self._static(grant)
        binary = _find(ctx.invoking_uid) if self.command is None else self.command
        if not binary:
            return Result(grant.ref, "unsupported", "agentkeys is not installed")
        _, scope, ident = grant.ref.split(":", 2)
        command = [
            binary,
            "revoke",
            f"--{scope}",
            ident,
            "--reason",
            f"agenthalt {ctx.halt_id}",
            "--principal",
            "agenthalt",
            "--json",
        ]
        left = max(end - time.monotonic(), 0.5)
        code, out = self.runner(command, left, _as_user(ctx.invoking_uid))
        if code == -1:
            return Result(grant.ref, "requested", out)
        try:
            envelope = json.loads(out.strip().splitlines()[-1])
            if not isinstance(envelope, dict):
                raise ValueError("not an object")
        except (ValueError, IndexError):
            return Result(grant.ref, "failed", f"agentkeys exited {code}: {out.strip()[:200]}")
        if code != 0 or not envelope.get("ok"):
            why = envelope.get("reason") or envelope.get("exit_class") or f"exit {code}"
            return Result(grant.ref, "failed", f"agentkeys: {why}")
        data = envelope.get("data")
        revocations = data.get("revocations") if isinstance(data, dict) else None
        if not isinstance(revocations, list) or not all(isinstance(r, dict) for r in revocations):
            revocations = []
        if not revocations:
            return Result(grant.ref, "failed", "agentkeys reported nothing revoked")
        epochs = [f"{r.get('session_id')} epoch {r.get('epoch_after')}" for r in revocations]
        note = f"agentkeys revoked {len(revocations)} session(s): {', '.join(epochs)}"
        if ctx.expired():
            return Result(grant.ref, "requested", f"{note}, after the deadline")
        return Result(grant.ref, "confirmed", note)
