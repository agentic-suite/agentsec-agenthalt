"""0.6 CI & quality gate (#405): the workflow enforces the standing milestone gate."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CI = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")


def test_every_action_is_pinned_to_a_commit_sha() -> None:
    for workflow in (ROOT / ".github" / "workflows").glob("*.yml"):
        for line in workflow.read_text(encoding="utf-8").splitlines():
            match = re.search(r"uses:\s*(\S+)", line)
            if match:
                ref = match.group(1).split("@", 1)[1]
                assert re.fullmatch(r"[0-9a-f]{40}", ref), f"{workflow.name}: {line.strip()}"
                assert "#" in line, f"{workflow.name}: pin has no version comment: {line.strip()}"


def test_matrix_covers_supported_pythons_and_platforms() -> None:
    for version in ("3.10", "3.11", "3.12", "3.13"):
        assert f'"{version}"' in CI
    assert "ubuntu-latest" in CI and "macos-latest" in CI


def test_gate_steps() -> None:
    assert "ruff check src tests" in CI
    assert "ruff format --check src tests" in CI
    assert re.search(r"^\s+run: mypy\s*$", CI, re.M)
    assert "--cov=agenthalt" in CI and "--cov-fail-under=95" in CI


def test_install_smoke() -> None:
    for command in ("pip install .", "agenthalt --version", "agenthalt --help", "agenthalt doctor"):
        assert command in CI


def test_least_privilege_and_triggers() -> None:
    assert re.search(r"^permissions:\n\s+contents: read", CI, re.M)
    assert "pull_request:" in CI
    assert '"feat/**"' in CI
    # all v0.1.0 work lands on the integration branch, so pushes there must run the gate
    assert '"docs/v0.1.0-planning"' in CI


def test_dco_workflow_present() -> None:
    dco = (ROOT / ".github" / "workflows" / "dco.yml").read_text(encoding="utf-8")
    assert "Signed-off-by" in dco
