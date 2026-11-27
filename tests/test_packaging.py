"""0.1 Scaffold & identity (#400): the package installs and identifies itself."""

from __future__ import annotations

import importlib.metadata as md
import re
import runpy
import subprocess
import sys

import pytest

import agenthalt


def test_version_is_pep440() -> None:
    assert re.fullmatch(r"\d+\.\d+\.\d+(?:(?:a|b|rc)\d+|\.dev\d+)?", agenthalt.__version__)


def test_distribution_metadata() -> None:
    dist = md.distribution("agentsec-agenthalt")
    assert dist.version == agenthalt.__version__
    assert dist.metadata["License-Expression"] == "Apache-2.0"
    assert dist.metadata["Requires-Python"] == ">=3.10"


def test_console_script_registered() -> None:
    eps = md.entry_points(group="console_scripts")
    assert any(ep.name == "agenthalt" and ep.value == "agenthalt.cli:main" for ep in eps)


def test_python_m_agenthalt_version() -> None:
    out = subprocess.run(
        [sys.executable, "-m", "agenthalt", "--version"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert out.stdout.strip() == f"agenthalt {agenthalt.__version__}"


def test_module_entry_point_in_process(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["agenthalt", "--version"])
    with pytest.raises(SystemExit) as exc:
        runpy.run_module("agenthalt", run_name="__main__")
    assert exc.value.code == 0
