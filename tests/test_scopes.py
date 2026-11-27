"""1.1 (#413): scopes, targets and mode ordering (M1 design §2)."""

from __future__ import annotations

import pytest

from agenthalt.scopes import Mode, Scope, Target


@pytest.mark.parametrize(
    "text",
    [
        "all",
        "tenant:acme",
        "agent:release-bot",
        "subtree:run_1",
        "run:run_1",
        "session:s1",
        "tool:shell",
        "writes-disabled",
    ],
)
def test_parse_round_trips(text: str) -> None:
    assert str(Scope.parse(text)) == text


@pytest.mark.parametrize(
    "bad",
    ["", "agent:", "agent:../x", "galaxy:1", "tool:", "all:x", "agent:a b", "writes-disabled:x"],
)
def test_parse_rejects(bad: str) -> None:
    with pytest.raises(ValueError):
        Scope.parse(bad)


def test_matching() -> None:
    t = Target(
        agent="bot",
        run="r3",
        session="s1",
        tenant="acme",
        ancestors=("r1", "r2"),
        tool="shell",
        writes=True,
    )
    hits = [
        "all",
        "tenant:acme",
        "agent:bot",
        "run:r3",
        "session:s1",
        "subtree:r1",
        "subtree:r2",
        "subtree:r3",
        "tool:shell",
        "writes-disabled",
    ]
    misses = ["tenant:other", "agent:other", "run:r1", "session:s2", "subtree:r9", "tool:curl"]
    for s in hits:
        assert Scope.parse(s).matches(t), s
    for s in misses:
        assert not Scope.parse(s).matches(t), s


def test_writes_disabled_only_hits_writes() -> None:
    assert not Scope.parse("writes-disabled").matches(Target(agent="bot", writes=False))


def test_empty_target_only_matches_global() -> None:
    t = Target()
    assert Scope.parse("all").matches(t)
    assert not Scope.parse("agent:bot").matches(t)
    assert not Scope.parse("subtree:r1").matches(t)


def test_target_validates_ids() -> None:
    with pytest.raises(ValueError):
        Target(agent="../etc")
    with pytest.raises(ValueError):
        Target(ancestors=("ok", "no way"))


def test_impact_defaults_to_high() -> None:
    assert Target().impact == "high"  # unclassified ⇒ high-impact (fail-closed)
    with pytest.raises(ValueError):
        Target(impact="medium")  # type: ignore[arg-type]


def test_mode_order_is_a_ladder() -> None:
    assert Mode.PAUSE < Mode.QUARANTINE < Mode.KILL
    assert max(Mode.PAUSE, Mode.KILL, Mode.QUARANTINE) is Mode.KILL
    assert Mode.parse("kill") is Mode.KILL
    with pytest.raises(ValueError):
        Mode.parse("nuke")
