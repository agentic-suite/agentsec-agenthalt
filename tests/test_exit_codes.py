"""0.2 (#401): the Tier-0 exit-code contract and the DD-39 status precedence."""

from __future__ import annotations

import itertools

import pytest

from agenthalt.exit_codes import ExitCode, ReceiptStatus, exit_code_for, status_for


def test_codes_are_frozen() -> None:
    # Tier-0 (PRD 40): these numbers never change once shipped.
    assert {c.name: int(c) for c in ExitCode} == {
        "COMPLETE": 0,
        "INCOMPLETE": 1,
        "PARTIAL_LAYER": 2,
        "FAILED": 3,
        "TRIGGER_REJECTED": 4,
        "USAGE": 5,
    }


def test_status_values() -> None:
    assert [s.value for s in ReceiptStatus] == ["complete", "partial-layer", "incomplete", "failed"]


def test_precedence_order() -> None:
    # DD-39: failed > incomplete > partial-layer > complete
    order = [
        ReceiptStatus.COMPLETE,
        ReceiptStatus.PARTIAL_LAYER,
        ReceiptStatus.INCOMPLETE,
        ReceiptStatus.FAILED,
    ]
    for lower, higher in itertools.combinations(order, 2):
        assert ReceiptStatus.worst(lower, higher) is higher
        assert ReceiptStatus.worst(higher, lower) is higher


def test_worst_requires_at_least_one() -> None:
    with pytest.raises(ValueError):
        ReceiptStatus.worst()


@pytest.mark.parametrize(
    ("survivor", "unsupported_layer", "blocking_failed", "expected"),
    [
        (s, u, b, (3 if b else 1 if s else 2 if u else 0))
        for s, u, b in itertools.product([False, True], repeat=3)
    ],
)
def test_every_combination_maps_to_one_code(
    survivor: bool, unsupported_layer: bool, blocking_failed: bool, expected: int
) -> None:
    status = status_for(
        survivor=survivor, unsupported_layer=unsupported_layer, blocking_failed=blocking_failed
    )
    assert int(exit_code_for(status)) == expected


def test_survivor_and_missing_gateway_is_incomplete() -> None:
    # The common Wave-0 case named in ADR-0011: exit 1, never 2.
    status = status_for(survivor=True, unsupported_layer=True, blocking_failed=False)
    assert status is ReceiptStatus.INCOMPLETE
    assert exit_code_for(status) is ExitCode.INCOMPLETE
