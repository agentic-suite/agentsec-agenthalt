"""0.7 Identity & governance docs (#406): the docs match the shipped identity."""

from __future__ import annotations

import re
from pathlib import Path

import agenthalt

ROOT = Path(__file__).resolve().parents[1]
README = (ROOT / "README.md").read_text(encoding="utf-8")
LINK = re.compile(r"\]\((?!https?://|#|mailto:)([^)#\s]+)")


def test_readme_names_the_identity() -> None:
    assert "pip install agentsec-agenthalt" in README
    assert "agenthalt doctor" in README
    assert "Apache-2.0" in README


def test_readme_status_matches_the_build() -> None:
    # Pre-release: the README must not claim a shipped v0.1.0 or runnable halts.
    assert agenthalt.__version__.endswith(".dev0")
    assert "in development" in README
    assert "not yet" in README.lower()


def test_exit_code_table_matches_the_contract() -> None:
    for code, word in [
        (0, "complete"),
        (1, "incomplete"),
        (2, "partial-layer"),
        (3, "failed"),
        (4, "rejected"),
        (5, "Usage"),
    ]:
        assert re.search(rf"\| `{code}` \| .*{word}", README, re.I), (code, word)


def test_relative_links_resolve() -> None:
    for doc in [
        ROOT / "README.md",
        ROOT / "SECURITY.md",
        *sorted((ROOT / "docs" / "reference").glob("*.md")),
        *sorted((ROOT / "docs" / "guides").glob("*.md")),
    ]:
        for target in LINK.findall(doc.read_text(encoding="utf-8")):
            assert (doc.parent / target).exists(), f"{doc.relative_to(ROOT)} -> {target}"


def test_state_layout_is_documented() -> None:
    layout = (ROOT / "docs" / "reference" / "state-layout.md").read_text(encoding="utf-8")
    for part in (
        "journal/",
        "seg-000001.jsonl",
        "0700",
        "0600",
        "store/",
        "receipts/",
        "evidence/",
    ):
        assert part in layout


def test_traceability_names_real_test_files() -> None:
    prd12 = (ROOT / "docs" / "prd" / "12-traceability.md").read_text(encoding="utf-8")
    m0_row = next(line for line in prd12.splitlines() if line.startswith("| M0 |"))
    named = re.findall(r"`(tests/[\w/]+\.py)`", m0_row)
    assert named, "PRD 12 M0 row names no test files"
    for path in named:
        assert (ROOT / path).is_file(), path
