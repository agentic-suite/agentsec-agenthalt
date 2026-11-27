"""0.2 (#401): the reserved command surface and its exit-code behaviour."""

from __future__ import annotations

import os
import subprocess
import sys

import pytest

from agenthalt.cli import COMMANDS, main

ALL_COMMANDS = [
    "run",
    "attach",
    "halt",
    "pause",
    "quarantine",
    "kill",
    "resume",
    "escalate",
    "lift",
    "status",
    "prove",
    "drill",
    "journal",
    "evidence",
    "doctor",
    "runbook",
]


@pytest.fixture(autouse=True)
def _isolated(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    # halts now write state (M1): never let a test touch the repo's working directory
    monkeypatch.chdir(tmp_path)  # type: ignore[arg-type]


def run(capsys: pytest.CaptureFixture[str], *argv: str) -> tuple[int, str, str]:
    code = main(list(argv))
    out, err = capsys.readouterr()
    return code, out, err


def test_registry_matches_prd37() -> None:
    assert sorted(COMMANDS) == sorted(ALL_COMMANDS)


def test_help_lists_every_command(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    for name in ALL_COMMANDS:
        assert name in out
    assert "Exit codes" in out


def test_run_and_attach_flags_in_help(capsys: pytest.CaptureFixture[str]) -> None:
    for cmd, flags in {"run": ["--name"], "attach": ["--pid", "--name"]}.items():
        with pytest.raises(SystemExit):
            main([cmd, "--help"])
        out = capsys.readouterr().out
        for flag in flags:
            assert flag in out
    with pytest.raises(SystemExit):
        main(["run", "--help"])
    assert "-- <cmd>" in capsys.readouterr().out


def test_unknown_command_is_usage_not_partial_layer(capsys: pytest.CaptureFixture[str]) -> None:
    # argparse would exit 2, which is reserved for partial-layer.
    code, _, err = run(capsys, "frobnicate")
    assert code == 5
    assert "frobnicate" in err


def test_bad_flag_is_usage(capsys: pytest.CaptureFixture[str]) -> None:
    code, _, _ = run(capsys, "halt", "--agent", "a", "--nope")
    assert code == 5


def test_no_command_prints_help_and_exits_usage(capsys: pytest.CaptureFixture[str]) -> None:
    code, _, err = run(capsys)
    assert code == 5
    assert "usage" in err.lower()


@pytest.mark.parametrize("cmd", ["halt", "pause", "quarantine", "kill"])
def test_halt_family_requires_exactly_one_target(
    capsys: pytest.CaptureFixture[str], cmd: str
) -> None:
    assert run(capsys, cmd, "--reason", "r")[0] == 5
    assert run(capsys, cmd, "--agent", "a", "--run", "b", "--reason", "r")[0] == 5


def test_kill_requires_reason(capsys: pytest.CaptureFixture[str]) -> None:
    code, _, err = run(capsys, "kill", "--agent", "release-bot")
    assert code == 5
    assert "--reason" in err
    code, _, err = run(capsys, "halt", "--agent", "release-bot", "--mode", "kill")
    assert code == 5
    assert "--reason" in err


def test_all_requires_reason(capsys: pytest.CaptureFixture[str]) -> None:
    code, _, err = run(capsys, "pause", "--all", "--yes")
    assert code == 5
    assert "--reason" in err


def test_fleet_halt_without_tty_or_yes_is_rejected(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    code, _, err = run(capsys, "kill", "--all", "--reason", "key compromise")
    assert code == 4
    assert "--yes" in err


def test_fleet_halt_typed_confirmation_mismatch_is_rejected(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda _prompt="": "yes")
    code, _, _ = run(capsys, "kill", "--all", "--reason", "key compromise")
    assert code == 4


def test_fleet_halt_confirmed_is_recorded(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda _prompt="": "halt all")
    code, out, _ = run(capsys, "kill", "--all", "--reason", "key compromise")
    assert code == 1  # M1: recorded + enforced at the choke, layers not yet: incomplete
    assert "all · kill" in out


@pytest.mark.parametrize("cmd", ["halt", "pause", "quarantine", "kill"])
def test_valid_halt_is_recorded_with_manual_fallback(
    capsys: pytest.CaptureFixture[str], cmd: str
) -> None:
    code, out, _ = run(capsys, cmd, "--agent", "release-bot", "--reason", "prod mutation")
    assert code == 1  # incomplete: enforced at the choke only (M1 design §7)
    assert "enforced at the runtime choke" in out
    assert "28-failure-mode-runbook.md" in out  # the manual fallback pointer


def test_halt_mode_choices(capsys: pytest.CaptureFixture[str]) -> None:
    assert run(capsys, "halt", "--agent", "a", "--mode", "explode", "--reason", "r")[0] == 5


def test_deadline_must_be_positive(capsys: pytest.CaptureFixture[str]) -> None:
    assert run(capsys, "halt", "--agent", "a", "--reason", "r", "--deadline-ms", "0")[0] == 5


def test_target_id_validated(capsys: pytest.CaptureFixture[str]) -> None:
    code, _, err = run(capsys, "halt", "--agent", "../etc", "--reason", "r")
    assert code == 5
    assert "invalid identifier" in err


def test_run_requires_command_after_dashdash(capsys: pytest.CaptureFixture[str]) -> None:
    code, _, err = run(capsys, "run", "--name", "bot")
    assert code == 5
    assert "--" in err
    code, _, _ = run(capsys, "run", "--name", "bot", "--")
    assert code == 5


def test_run_with_command_is_unavailable(capsys: pytest.CaptureFixture[str]) -> None:
    code, _, err = run(capsys, "run", "--name", "bot", "--", "sleep", "1")
    assert code == 5
    assert "not available in this build" in err


def test_attach_missing_pid(capsys: pytest.CaptureFixture[str]) -> None:
    code, _, err = run(capsys, "attach", "--pid", "999999999")
    assert code == 5
    assert "no such process" in err


def test_attach_non_numeric_pid(capsys: pytest.CaptureFixture[str]) -> None:
    assert run(capsys, "attach", "--pid", "abc")[0] == 5


def test_attach_foreign_pid(capsys: pytest.CaptureFixture[str]) -> None:
    if os.geteuid() == 0:
        pytest.skip("root can signal every process")
    code, _, err = run(capsys, "attach", "--pid", "1")
    assert code == 5
    assert "another user" in err


def test_attach_own_pid_is_unavailable(capsys: pytest.CaptureFixture[str]) -> None:
    code, _, err = run(capsys, "attach", "--pid", str(os.getpid()))
    assert code == 5
    assert "not available in this build" in err


@pytest.mark.parametrize(
    "argv",
    [
        ["resume", "--halt", "hlt_1"],
        ["escalate", "--halt", "hlt_1", "--to", "kill"],
        ["prove", "--receipt", "r.json"],
        ["drill"],
        ["evidence", "export", "--halt", "hlt_1"],
        ["runbook"],
    ],
)
def test_unavailable_commands_exit_usage(
    capsys: pytest.CaptureFixture[str], argv: list[str]
) -> None:
    code, _, err = run(capsys, *argv)
    assert code == 5
    assert "not available in this build" in err


def test_lift_requires_reason(capsys: pytest.CaptureFixture[str]) -> None:
    assert run(capsys, "lift", "--halt", "hlt_1")[0] == 5


def test_console_script_end_to_end() -> None:
    out = subprocess.run(
        [sys.executable, "-m", "agenthalt", "frobnicate"], capture_output=True, text=True
    )
    assert out.returncode == 5
