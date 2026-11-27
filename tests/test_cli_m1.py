"""1.6 (#418): `status`, and the M1 halt/lift CLI (record + enforce at the choke, exit 1)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agenthalt.choke import RuntimeChoke
from agenthalt.cli import main
from agenthalt.reasons import ReasonCode
from agenthalt.scopes import Target
from agenthalt.store import Store


@pytest.fixture(autouse=True)
def _cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)


def run(capsys: pytest.CaptureFixture[str], *argv: str) -> tuple[int, str, str]:
    code = main(list(argv))
    out, err = capsys.readouterr()
    return code, out, err


def test_kill_records_enforces_and_exits_incomplete(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code, out, _ = run(capsys, "kill", "--agent", "bot", "--reason", "prod mutation")
    assert code == 1
    assert "enforced at the runtime choke" in out
    assert "NOT done in this build" in out and "incomplete" in out
    choke = RuntimeChoke(Store(tmp_path / ".agenthalt"), cache_ttl_s=0)
    d = choke.check(Target(agent="bot"))
    assert not d.allow and d.reason is ReasonCode.HALTED


def test_halt_json_and_scopes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = run(capsys, "halt", "--run", "r1", "--mode", "pause", "--json")
    assert code == 1
    data = json.loads(out)
    assert (
        data["scope"] == "subtree:r1"
        and data["mode"] == "pause"
        and data["outcome"] == "incomplete"
    )
    assert (
        data["layers"]["runtime_choke"] == "enforced" and data["layers"]["process"] == "unsupported"
    )
    assert data["created"] is True
    code, out, _ = run(capsys, "pause", "--session", "s1", "--json")
    assert json.loads(out)["scope"] == "session:s1"


def test_duplicate_halt_is_idempotent(capsys: pytest.CaptureFixture[str]) -> None:
    run(capsys, "kill", "--agent", "bot", "--reason", "a")
    code, out, _ = run(capsys, "kill", "--agent", "bot", "--reason", "b", "--json")
    assert code == 1 and json.loads(out)["created"] is False


def test_fleet_halt_after_confirmation(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = run(capsys, "kill", "--all", "--reason", "key compromise", "--yes", "--json")
    assert code == 1 and json.loads(out)["scope"] == "all"


def test_status_lists_halts_and_health(capsys: pytest.CaptureFixture[str]) -> None:
    run(capsys, "kill", "--agent", "bot", "--reason", "prod")
    code, out, _ = run(capsys, "status")
    assert code == 0
    assert "agent:bot" in out and "kill" in out and "store: ok" in out
    code, out, _ = run(capsys, "status", "--json")
    data = json.loads(out)
    assert data["health"]["status"] == "ok" and data["health"]["armed"] is True
    (halt,) = data["halts"]
    assert halt["scope"] == "agent:bot" and halt["status"] == "finished"
    code, out, _ = run(capsys, "status", "--halt", halt["halt_id"], "--json")
    assert [h["halt_id"] for h in json.loads(out)["halts"]] == [halt["halt_id"]]


def test_status_unknown_halt(capsys: pytest.CaptureFixture[str]) -> None:
    code, _, err = run(capsys, "status", "--halt", "hlt_nope")
    assert code == 5 and "hlt_nope" in err


def test_status_creates_the_store_when_missing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code, out, _ = run(capsys, "status")
    assert code == 0 and "no active halts" in out
    assert (tmp_path / ".agenthalt" / "store" / "state.json").is_file()


def test_status_reports_tampering(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    run(capsys, "kill", "--agent", "bot", "--reason", "prod")
    path = tmp_path / ".agenthalt" / "store" / "state.json"
    data = json.loads(path.read_text())
    data["halts"] = []
    path.write_text(json.dumps(data))
    code, out, err = run(capsys, "status")
    assert code == 1 and "head_mismatch" in (out + err)


def test_status_recovers_after_a_crash(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    run(capsys, "kill", "--agent", "bot", "--reason", "prod")
    store = Store(tmp_path / ".agenthalt")
    state = store.load()
    from agenthalt.scopes import Mode, Scope
    from agenthalt.store import HaltState

    halt = HaltState.new(
        halt_id="hlt_crash", scope=Scope.parse("all"), mode=Mode.PAUSE, actor="m", reason="r"
    )
    store.journal.append(
        "raise",
        actor="m",
        halt_id="hlt_crash",
        scope="all",
        mode="pause",
        payload={
            "store": {"op": "upsert", "generation": state.generation + 1, "halt": halt.to_dict()}
        },
    )
    code, out, _ = run(capsys, "status")
    assert code == 0 and "recovered" in out and "hlt_crash" in out


def test_lift(capsys: pytest.CaptureFixture[str]) -> None:
    run(capsys, "kill", "--agent", "bot", "--reason", "prod")
    halt_id = json.loads(run(capsys, "status", "--json")[1])["halts"][0]["halt_id"]
    code, out, _ = run(capsys, "lift", "--halt", halt_id, "--reason", "false alarm")
    assert code == 0 and "lifted" in out
    assert json.loads(run(capsys, "status", "--json")[1])["halts"] == []


def test_lift_unknown_or_blank_reason(capsys: pytest.CaptureFixture[str]) -> None:
    assert run(capsys, "lift", "--halt", "hlt_nope", "--reason", "x")[0] == 5
    run(capsys, "kill", "--agent", "bot", "--reason", "prod")
    halt_id = json.loads(run(capsys, "status", "--json")[1])["halts"][0]["halt_id"]
    assert run(capsys, "lift", "--halt", halt_id, "--reason", "  ")[0] == 5


def test_duplicate_halt_text_output(capsys: pytest.CaptureFixture[str]) -> None:
    run(capsys, "kill", "--agent", "bot", "--reason", "a")
    code, out, _ = run(capsys, "kill", "--agent", "bot", "--reason", "b")
    assert code == 1 and "already active" in out and "idempotent" in out


def test_status_with_a_broken_journal(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    run(capsys, "kill", "--agent", "bot", "--reason", "prod")
    seg = tmp_path / ".agenthalt" / "journal" / "seg-000001.jsonl"
    seg.write_text(seg.read_text() + "{not json\n")  # unparsable: replay cannot run either
    code, out, _ = run(capsys, "status")
    assert code == 1 and "head_mismatch" in out and "journal does not verify" in out
