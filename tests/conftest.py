"""Shared pytest hooks."""

from __future__ import annotations

import os

import pytest


@pytest.hookimpl
def pytest_runtest_logstart(nodeid: str, location: object) -> None:
    """Tell the CI stop watchdog which test is running (see .github/ci/stop_watchdog.py)."""
    stamp = os.environ.get("AGENTHALT_TEST_STAMP")
    if stamp:
        with open(stamp, "w") as handle:
            handle.write(nodeid)
