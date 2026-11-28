"""2.2 (#426): process observation, against a fake ``/proc`` and sample ``ps`` output."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from agenthalt.observe import ObserveError, Proc, SystemObserver, node_id, parse_ps, parse_stat

STARTED = "Fri Nov 27 08:57:21 2026"


def stat_line(pid: int, ppid: int, comm: str = "sh", state: str = "S", start: int = 77) -> str:
    fields = [state, str(ppid), str(pid), str(pid), *["0"] * 15, str(start), "0"]
    return f"{pid} ({comm}) " + " ".join(fields)


def fake_proc(root: Path, pid: int, ppid: int, *, env: bytes = b"", cgroup: str = "") -> None:
    directory = root / str(pid)
    directory.mkdir(parents=True)
    (directory / "stat").write_text(stat_line(pid, ppid))
    (directory / "environ").write_bytes(env)
    (directory / "cgroup").write_text(cgroup)


def test_parse_stat_handles_awkward_names_and_skips_zombies() -> None:
    proc = parse_stat(stat_line(12, 3, comm="a) (b c"), uid=501)
    assert proc == Proc(pid=12, ppid=3, pgid=12, sid=12, uid=501, start="0000000000077")
    assert node_id(proc) == "proc_12_0000000000077"
    assert parse_stat(stat_line(12, 3, state="Z"), uid=0) is None
    assert parse_stat("12 (x) S 1", uid=0) is None
    assert parse_stat("no parentheses", uid=0) is None


def test_parse_ps_skips_zombies_and_junk() -> None:
    def sid(pid: int) -> int:
        if pid == 11:
            raise PermissionError
        return 5

    output = "\n".join(
        [
            f"   10     1    10   501 Ss   {STARTED}",
            f"   11    10    10   501 S    {STARTED}",
            f"   12    10    10   501 Z    {STARTED}",
            "   13    10    10   501 S    not a date at all here",
            "short line",
        ]
    )
    table = parse_ps(output, sid_of=sid)
    assert sorted(table) == [10, 11]
    assert (table[10].sid, table[11].sid) == (5, 0)
    assert table[10].start.isdigit()


def test_linux_snapshot_markers_and_cgroup(tmp_path: Path) -> None:
    fake_proc(tmp_path, 20, 1, env=b"A=1\0AGENTHALT_RUN_ID=run_x\0", cgroup="1:a:/x\n0::/grp\n")
    fake_proc(tmp_path, 21, 20, env=b"B=2\0")
    (tmp_path / "22").mkdir()  # exited between the listing and the read
    (tmp_path / "self").mkdir()
    seen = SystemObserver(platform="linux", proc_root=tmp_path)
    assert sorted(seen.snapshot()) == [20, 21]
    assert seen.snapshot()[21].uid == os.getuid()
    assert seen.run_markers() == {20: "run_x"}
    assert seen.cgroup_of(20) == "/grp"
    assert seen.cgroup_of(21) is None
    assert seen.cgroup_of(999) is None


def test_linux_failures_are_loud(tmp_path: Path) -> None:
    with pytest.raises(ObserveError):
        SystemObserver(platform="linux", proc_root=tmp_path / "missing").snapshot()
    fake_proc(tmp_path, 20, 1)
    with pytest.raises(ObserveError, match="deadline"):
        SystemObserver(platform="linux", proc_root=tmp_path).snapshot(timeout_s=-1)


def test_macos_uses_ps(monkeypatch: pytest.MonkeyPatch) -> None:
    argv = ["30 python agent.py", "31 grep AGENTHALT_RUN_ID=run_fake", "32 sleep 1", "33 gone"]
    env = {
        "30": " HOME=/x AGENTHALT_RUN_ID=run_abc PATH=/bin",
        "31": " HOME=/x AGENTHALT_RUN_ID=run_real",
        "32": "",
    }

    def fake(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        if "-axEww" in args:
            rows = [line + env[line[:2]] for line in argv[:3]]
            rows += ["34 new AGENTHALT_RUN_ID=run_unlisted", "garbage AGENTHALT_RUN_ID=run_z"]
        elif "-axww" in args:
            rows = argv
        else:
            rows = [f"30 1 30 501 S {STARTED}"]
        return subprocess.CompletedProcess(args, 0, "\n".join(rows) + "\n", "")

    monkeypatch.setattr(subprocess, "run", fake)
    seen = SystemObserver(platform="darwin")
    assert list(seen.snapshot()) == [30]
    assert seen.run_markers() == {30: "run_abc", 31: "run_real"}
    assert seen.cgroup_of(30) is None


@pytest.mark.parametrize(
    "error",
    [OSError("gone"), subprocess.TimeoutExpired("ps", 1), subprocess.CalledProcessError(1, "ps")],
)
def test_a_failing_ps_is_an_observe_error(
    monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    def fail(*args: object, **kwargs: object) -> None:
        raise error

    monkeypatch.setattr(subprocess, "run", fail)
    with pytest.raises(ObserveError):
        SystemObserver(platform="darwin").snapshot()


def test_the_real_observer_sees_this_process() -> None:
    assert os.getpid() in SystemObserver().snapshot()


def test_linux_probe_reads_only_the_asked_processes(tmp_path: Path) -> None:
    (tmp_path / "10").mkdir()
    (tmp_path / "10" / "stat").write_text("10 (x) T 1 10 10 " + "0 " * 15 + "77 0")
    seen = SystemObserver(platform="linux", proc_root=tmp_path)
    found = seen.probe([10, 11])
    assert list(found) == [10] and found[10].state == "T"


@pytest.mark.parametrize(("error", "empty"), [(ProcessLookupError, True), (PermissionError, False)])
def test_macos_probe_failure_is_empty_only_if_none_exist(
    monkeypatch: pytest.MonkeyPatch, error: type[OSError], empty: bool
) -> None:
    def fail(*args: object, **kwargs: object) -> None:
        raise subprocess.CalledProcessError(1, "ps")

    def kill(pid: int, signum: int) -> None:
        raise error

    monkeypatch.setattr(subprocess, "run", fail)
    monkeypatch.setattr(os, "kill", kill)
    seen = SystemObserver(platform="darwin")
    if empty:
        assert seen.probe([10]) == {}
    else:
        with pytest.raises(ObserveError):
            seen.probe([10])
