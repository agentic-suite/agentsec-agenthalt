"""2.7 / 2.5 surface: ``run``, ``attach``, the ``status`` lineage section and the ``doctor`` check."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

import agenthalt.supervisor as supervisor_module
from agenthalt.cli import main
from agenthalt.config import load_config
from agenthalt.doctor import Probes, run_checks
from tests.lineage_helpers import adapters, edge, make_registry, root

PY = sys.executable


@pytest.fixture(autouse=True)
def _isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("AGENTHALT_RUN_ID", raising=False)
    monkeypatch.setattr(supervisor_module, "default_containment", lambda: "pgroup")


def cli(capsys: pytest.CaptureFixture[str], *argv: str) -> tuple[int, str, str]:
    code = main(["--log-level", "error", *argv])
    out, err = capsys.readouterr()
    return code, out, err


def status(capsys: pytest.CaptureFixture[str]) -> tuple[int, dict]:  # type: ignore[type-arg]
    code, out, _ = cli(capsys, "status", "--json")
    return code, json.loads(out)["lineage"]


def test_run_enrolls_and_returns_the_agents_status(capsys: pytest.CaptureFixture[str]) -> None:
    code, _, err = cli(capsys, "run", "--name", "bot", "--", PY, "-c", "raise SystemExit(3)")
    assert code == 3
    assert "enrolled" in err
    _, lineage = status(capsys)
    assert [(r["name"], r["enrollment"]) for r in lineage["runs"]] == [("bot", "run")]


def test_run_refusals_exit_5(capsys: pytest.CaptureFixture[str]) -> None:
    code, _, err = cli(capsys, "run", "--", "definitely-not-a-command")
    assert code == 5 and "not found" in err
    assert cli(capsys, "run")[0] == 5
    code, _, err = cli(capsys, "run", "--user", "nobody", "--", PY, "-c", "pass")
    if os.geteuid() != 0:
        assert code == 5 and "root" in err


def test_a_halted_agent_cannot_be_run(capsys: pytest.CaptureFixture[str]) -> None:
    cli(capsys, "halt", "--agent", "bot", "--mode", "kill", "--reason", "r")
    code, _, err = cli(capsys, "run", "--name", "bot", "--", PY, "-c", "pass")
    assert code == 5 and "spawn refused" in err


def test_run_reports_gaps_and_survivors(capsys: pytest.CaptureFixture[str]) -> None:
    body = (
        "import subprocess, sys, time;"
        "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(2)'],"
        " start_new_session=True); time.sleep(0.8)"
    )
    code, _, err = cli(capsys, "run", "--", PY, "-c", body)
    assert code == 0
    assert "lineage gap" in err and "still running" in err
    _, lineage = status(capsys)
    assert lineage["gaps"] and not lineage["runs"][0]["lineage_verified"]
    code, out, _ = cli(capsys, "status")
    assert "gap" in out


def test_attach_and_status(capsys: pytest.CaptureFixture[str]) -> None:
    process = subprocess.Popen([PY, "-c", "import time; time.sleep(20)"])
    try:
        time.sleep(0.5)
        code, out, _ = cli(capsys, "attach", "--pid", str(process.pid), "--name", "late")
        assert code == 0 and "lineage_verified: true" in out
        code, out, _ = cli(capsys, "attach", "--pid", str(process.pid))
        assert code == 0 and "already enrolled" in out
        _, lineage = status(capsys)
        assert lineage["runs"][0]["lineage_verified"]
        code, out, _ = cli(capsys, "status")
        assert "late" in out
    finally:
        process.kill()
        process.wait()


def test_orphans_and_tamper_are_surfaced(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    home = tmp_path / ".agenthalt"
    reg = make_registry(home)
    cred = adapters(reg)["process"]
    reg.append_edges(cred, [root("run_a")])
    reg.append_edges(cred, [edge("run_lost", "run_orphan")])
    code, lineage = status(capsys)
    assert code == 0 and lineage["orphans"] == ["run_orphan"]
    code, out, _ = cli(capsys, "status")
    assert "run_orphan" in out

    segment = home / "lineage" / "seg-000001.jsonl"
    segment.write_text(segment.read_text().splitlines()[0] + "\n")
    code, lineage = status(capsys)
    assert code == 1 and lineage["tamper"]
    assert not lineage["runs"][0]["lineage_verified"]
    code, out, err = cli(capsys, "status")
    assert code == 1 and "tamper" in out + err
    checks = {c.name: c for c in run_checks(load_config(), Probes.real())}
    assert checks["lineage"].result == "fail"


def test_doctor_lineage_check(tmp_path: Path) -> None:
    def check() -> str:
        return {c.name: c for c in run_checks(load_config(), Probes.real())}["lineage"].result

    assert check() == "pass"
    reg = make_registry(tmp_path / ".agenthalt")
    reg.append_edges(adapters(reg)["process"], [root("run_a")])
    assert check() == "pass"


def test_an_unreadable_lineage_is_reported_not_raised(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    home = tmp_path / ".agenthalt"
    reg = make_registry(home)
    reg.append_edges(adapters(reg)["process"], [root("run_a")])
    (home / "journal" / "seg-000001.jsonl").write_text("garbage\n")
    code, lineage = status(capsys)
    assert code == 1 and lineage["tamper"]
