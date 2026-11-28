"""4.1/4.2: revoking declared grants through agentkeys, and honest unrevocable keys."""

from __future__ import annotations

import json
import sys
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest

from agenthalt.credentials import AgentkeysExecutor, Grant, parse_grant, unrevocable
from agenthalt.executors import Context


def ctx(ms: int = 5000) -> Context:
    return Context("hlt_1", time.monotonic() + ms / 1000)


def envelope(ok: bool = True, **data: Any) -> str:
    body: dict[str, Any] = {"ok": ok, "exit_class": "ok" if ok else "denied", "data": data}
    if not ok:
        body["reason"] = "unknown agent: bot"
    return json.dumps(body)


class Fake:
    def __init__(self, code: int, out: str) -> None:
        self.code, self.out, self.calls = code, out, []  # type: ignore[var-annotated]

    def __call__(
        self, command: Sequence[str], timeout: float, ids: Mapping[str, Any]
    ) -> tuple[int, str]:
        self.calls.append(list(command))
        return self.code, self.out


REVOKED = envelope(revocations=[{"session_id": "s1", "epoch_before": 0, "epoch_after": 1}])


@pytest.mark.parametrize(
    ("code", "out", "status", "words"),
    [
        (0, REVOKED, "confirmed", "s1 epoch 1"),
        (2, envelope(ok=False), "failed", "unknown agent"),
        (0, envelope(revocations=[]), "failed", "nothing revoked"),
        (1, "Traceback: boom", "failed", "exited 1"),
        (0, "[]", "failed", "exited 0"),
        (-1, "agentkeys did not answer in time", "requested", "in time"),
    ],
)
def test_agentkeys_answers_map_to_honest_statuses(
    code: int, out: str, status: str, words: str
) -> None:
    fake = Fake(code, out)
    (result,) = AgentkeysExecutor("/x/agentkeys", runner=fake).revoke(
        [Grant("agentkeys:agent:bot", "run_a")], ctx()
    )
    assert result.status == status and words in result.note
    assert fake.calls[0][:4] == ["/x/agentkeys", "revoke", "--agent", "bot"]
    assert "--json" in fake.calls[0] and "agenthalt hlt_1" in fake.calls[0]


def test_a_revoke_after_the_deadline_is_requested() -> None:
    (result,) = AgentkeysExecutor("/x", runner=Fake(0, REVOKED)).revoke(
        [Grant("agentkeys:session:s1", "r")], ctx(-1)
    )
    assert result.status == "requested" and "after the deadline" in result.note


def test_static_keys_are_never_claimed_revoked() -> None:
    fake = Fake(0, REVOKED)
    executor = AgentkeysExecutor("/x", runner=fake)
    grants = [Grant("static:GH_PAT@2026-12-01", "r"), Grant("static:VENDOR", "r")]
    for phase in (executor.revoke, executor.freeze):
        dated, undated = phase(grants, ctx())
        assert dated.status == undated.status == "unsupported"
        assert "2026-12-01" in dated.note and "no expiry" in undated.note
    assert fake.calls == []
    assert unrevocable("static:GH_PAT@2026-12-01") == {
        "ref": "static:GH_PAT",
        "expires": "2026-12-01",
        "window_note": "usable until 2026-12-01",
    }


def test_quarantine_cannot_freeze_issuance_and_says_so() -> None:
    (result,) = AgentkeysExecutor("/x").freeze([Grant("agentkeys:agent:bot", "r")], ctx())
    assert result.status == "unsupported" and "kill revokes" in result.note


def test_without_agentkeys_nothing_is_claimed() -> None:
    executor = AgentkeysExecutor("")  # "" means: known to be absent
    (result,) = executor.revoke([Grant("agentkeys:agent:bot", "r")], ctx())
    assert result.status == "unsupported" and "not installed" in result.note
    assert executor.release([{"x": 1}], ctx()) == []


@pytest.mark.parametrize(
    "ref",
    ["agentkeys:agent:bot", "agentkeys:session:s-1.2", "static:GH_PAT", "static:K@2026-01-02"],
)
def test_good_grants_parse(ref: str) -> None:
    assert parse_grant(ref) == ref


@pytest.mark.parametrize(
    "ref", ["agentkeys:token:x", "static:", "static:a b", "agentkeys:agent:x;rm", "static:K@soon"]
)
def test_bad_grants_are_refused(ref: str) -> None:
    with pytest.raises(ValueError, match="bad grant"):
        parse_grant(ref)


def test_the_real_runner_reports_a_hang_and_a_missing_binary(tmp_path: Path) -> None:
    from agenthalt.credentials import _run

    script = tmp_path / "slow.py"
    script.write_text("import time; time.sleep(5)")
    assert _run([sys.executable, str(script)], 0.2, {})[0] == -1
    assert _run([str(tmp_path / "missing")], 1.0, {})[0] == 127
    assert _run([sys.executable, "-c", "print('{}')"], 5.0, {}) == (0, "{}\n")
