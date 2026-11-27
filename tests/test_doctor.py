"""0.5 doctor (#404): preflight checks, the verdict, and the platform checks with their fixes."""

from __future__ import annotations

import dataclasses
import json
import os
from pathlib import Path
from typing import Any

import pytest

from agenthalt.cli import main
from agenthalt.config import Config, ConfigError, load_config
from agenthalt.doctor import Check, Probes, run_checks, verdict
from agenthalt.journal import Journal
from agenthalt.store import Store

BASE = Probes(
    python=(3, 12),
    platform="darwin",
    ax_trusted=lambda: True,
    cgroup=lambda: (True, True),
    user_home=Path("/nonexistent-home"),
)


def probes(**overrides: Any) -> Probes:
    return dataclasses.replace(BASE, **overrides)


def by_name(checks: list[Check]) -> dict[str, Check]:
    return {c.name: c for c in checks}


def cfg(tmp_path: Path, **env: str) -> Config:
    return load_config(env=env, cwd=tmp_path)


def test_all_checks_present_and_healthy(tmp_path: Path) -> None:
    checks = by_name(run_checks(cfg(tmp_path), probes()))
    assert list(checks) == [
        "python",
        "platform",
        "config",
        "env",
        "home",
        "journal",
        "store",
        "adapters",
        "panic_key",
        "cgroup",
        "hooks",
    ]
    assert (
        checks["store"].result == "warn" and "agenthalt status" in checks["store"].fix
    )  # not created yet
    assert checks["adapters"].result == "n/a"
    assert checks["cgroup"].result == "n/a"  # linux-only check on darwin
    assert verdict(list(checks.values())) == "warn"


def test_verdict_is_the_worst_result() -> None:
    def mk(result: str) -> Check:
        return Check("x", result, "", "")

    assert verdict([mk("pass"), mk("n/a")]) == "pass"
    assert verdict([mk("pass"), mk("warn")]) == "warn"
    assert verdict([mk("warn"), mk("fail"), mk("pass")]) == "fail"


def test_old_python_fails(tmp_path: Path) -> None:
    check = by_name(run_checks(cfg(tmp_path), probes(python=(3, 9))))["python"]
    assert check.result == "fail" and "3.10" in check.fix


def test_windows_fails_with_plan(tmp_path: Path) -> None:
    check = by_name(run_checks(cfg(tmp_path), probes(platform="win32")))["platform"]
    assert check.result == "fail" and "PRD 40" in check.fix


def test_config_error_is_reported_with_key_and_source(tmp_path: Path) -> None:
    err = ConfigError("must be 1..60000, got 0", key="halt.deadline_ms", source="file:/x.toml")
    checks = by_name(run_checks(err, probes()))
    assert checks["config"].result == "fail"
    assert "halt.deadline_ms" in checks["config"].detail and "/x.toml" in checks["config"].detail
    assert checks["home"].result == "n/a" and checks["journal"].result == "n/a"


def test_env_typo_warns_with_suggestion(tmp_path: Path) -> None:
    checks = by_name(run_checks(cfg(tmp_path, AGENTHALT_DEADLNE_MS="5"), probes()))
    assert checks["env"].result == "warn"
    assert "AGENTHALT_DEADLINE_MS" in checks["env"].fix


def test_unrelated_env_name_passes(tmp_path: Path) -> None:
    checks = by_name(run_checks(cfg(tmp_path, AGENTHALT_HMAC_KEY="x"), probes()))
    assert checks["env"].result == "pass"


def test_home_too_open_fails(tmp_path: Path) -> None:
    home = tmp_path / ".agenthalt"
    home.mkdir()
    os.chmod(home, 0o755)  # noqa: S103 - deliberately too open: the check under test must fail
    check = by_name(run_checks(cfg(tmp_path), probes()))["home"]
    assert check.result == "fail" and "chmod 700" in check.fix


def test_home_not_a_directory_fails(tmp_path: Path) -> None:
    (tmp_path / ".agenthalt").write_text("x")
    check = by_name(run_checks(cfg(tmp_path), probes()))["home"]
    assert check.result == "fail"


def test_home_missing_parent_not_writable_fails(tmp_path: Path) -> None:
    locked = tmp_path / "locked"
    locked.mkdir()
    os.chmod(locked, 0o500)
    try:
        config = load_config(flags={"home": str(locked / "state")}, env={}, cwd=tmp_path)
        check = by_name(run_checks(config, probes()))["home"]
        if os.geteuid() != 0:
            assert check.result == "fail"
    finally:
        os.chmod(locked, 0o700)


def test_home_ok_existing(tmp_path: Path) -> None:
    (tmp_path / ".agenthalt").mkdir(mode=0o700)
    os.chmod(tmp_path / ".agenthalt", 0o700)
    assert by_name(run_checks(cfg(tmp_path), probes()))["home"].result == "pass"


def test_broken_journal_fails(tmp_path: Path) -> None:
    j = Journal(tmp_path / ".agenthalt")
    j.append("finding", actor="t")
    seg = j.dir / "seg-000001.jsonl"
    seg.write_text(seg.read_text().replace('"actor":"t"', '"actor":"m"'))
    check = by_name(run_checks(cfg(tmp_path), probes()))["journal"]
    assert check.result == "fail" and "journal verify" in check.fix


def test_intact_journal_passes(tmp_path: Path) -> None:
    Journal(tmp_path / ".agenthalt").append("finding", actor="t")
    check = by_name(run_checks(cfg(tmp_path), probes()))["journal"]
    assert check.result == "pass" and "1 entries" in check.detail


@pytest.mark.parametrize(("trusted", "result"), [(True, "pass"), (False, "warn"), (None, "warn")])
def test_panic_key_accessibility(tmp_path: Path, trusted: bool | None, result: str) -> None:
    check = by_name(run_checks(cfg(tmp_path), probes(ax_trusted=lambda: trusted)))["panic_key"]
    assert check.result == result
    if result == "warn":
        assert "Accessibility" in check.fix


def test_panic_key_na_on_linux(tmp_path: Path) -> None:
    checks = by_name(run_checks(cfg(tmp_path), probes(platform="linux")))
    assert checks["panic_key"].result == "n/a"


@pytest.mark.parametrize(
    ("state", "result", "fix_word"),
    [
        ((True, True), "pass", ""),
        ((True, False), "warn", "systemd-run"),
        ((False, False), "warn", "cgroup v2"),
    ],
)
def test_cgroup_check_on_linux(
    tmp_path: Path, state: tuple[bool, bool], result: str, fix_word: str
) -> None:
    check = by_name(run_checks(cfg(tmp_path), probes(platform="linux", cgroup=lambda: state)))[
        "cgroup"
    ]
    assert check.result == result
    assert fix_word in check.fix


def test_hooks_never_fail_and_report_presence(tmp_path: Path) -> None:
    home = tmp_path / "user"
    (home / ".claude").mkdir(parents=True)
    (home / ".claude" / "settings.json").write_text(
        json.dumps({"hooks": {"PreToolUse": [{"command": "agenthalt hook"}]}})
    )
    check = by_name(run_checks(cfg(tmp_path), probes(user_home=home)))["hooks"]
    assert check.result == "pass" and "claude-code" in check.detail
    check = by_name(run_checks(cfg(tmp_path), probes(user_home=tmp_path / "nobody")))["hooks"]
    assert check.result == "pass" and "none" in check.detail and "ADR-0005" in check.detail


def test_hooks_unreadable_settings_still_pass(tmp_path: Path) -> None:
    home = tmp_path / "user"
    (home / ".claude").mkdir(parents=True)
    (home / ".claude" / "settings.json").write_text("{not json")
    check = by_name(run_checks(cfg(tmp_path), probes(user_home=home)))["hooks"]
    assert check.result == "pass"


def test_real_probes_do_not_crash() -> None:
    real = Probes.real()
    assert real.platform
    if real.platform == "darwin":
        assert real.ax_trusted() in (True, False, None)
    if real.platform == "linux":
        v2, delegated = real.cgroup()
        assert isinstance(v2, bool) and isinstance(delegated, bool)


# --- CLI ----------------------------------------------------------------------------------


def test_cli_doctor_text_and_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    code = main(["doctor"])
    out = capsys.readouterr().out
    assert code in (0, 5)
    assert "verdict:" in out
    for name in ("python", "platform", "journal", "hooks"):
        assert name in out
    code = main(["doctor", "--json"])
    data = json.loads(capsys.readouterr().out)
    assert {c["name"] for c in data["checks"]} >= {"python", "config", "hooks"}
    assert data["verdict"] in ("pass", "warn", "fail")


def test_cli_doctor_reports_bad_config_instead_of_dying(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "agenthalt.toml").write_text("[halt]\ndeadline_ms = 0\n")
    code = main(["doctor"])
    out = capsys.readouterr().out
    assert code == 5
    assert "halt.deadline_ms" in out and "verdict: fail" in out


def test_cli_doctor_migrate_and_verbose(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    main(["doctor", "--migrate", "--verbose"])
    out = capsys.readouterr().out
    assert "no migrations" in out
    assert "halt.deadline_ms = 1000 (default)" in out


def test_cgroup_probe_without_cgroup_v2(tmp_path: Path) -> None:
    from agenthalt import doctor

    if Path("/sys/fs/cgroup/cgroup.controllers").exists():
        pytest.skip("host has cgroup v2")
    assert doctor._cgroup_real() == (False, False)


def test_home_deep_missing_path(tmp_path: Path) -> None:
    config = load_config(flags={"home": str(tmp_path / "a" / "b" / "c")}, env={}, cwd=tmp_path)
    check = by_name(run_checks(config, probes()))["home"]
    assert check.result == "pass" and "will be created" in check.detail


def test_home_not_writable(tmp_path: Path) -> None:
    home = tmp_path / ".agenthalt"
    home.mkdir()
    os.chmod(home, 0o500)
    try:
        check = by_name(run_checks(cfg(tmp_path), probes()))["home"]
        if os.geteuid() != 0:
            assert check.result == "fail" and "not writable" in check.detail
    finally:
        os.chmod(home, 0o700)


def test_unreadable_journal(tmp_path: Path) -> None:
    j = Journal(tmp_path / ".agenthalt")
    j.append("finding", actor="t")
    (j.dir / "seg-000001.jsonl").write_bytes(b"\xff\xfe not utf-8\n")
    check = by_name(run_checks(cfg(tmp_path), probes()))["journal"]
    assert (
        check.result == "fail" and "not UTF-8" in check.detail and "line None" not in check.detail
    )


# --- the store check (M1, #418) -------------------------------------------------------------


def _armed_store(tmp_path: Path) -> Store:
    from agenthalt.coordinator import Coordinator
    from agenthalt.scopes import Mode, Scope
    from agenthalt.store import Store

    store = Store(tmp_path / ".agenthalt")
    store.ensure()
    Coordinator(store).raise_halt(Scope.parse("agent:bot"), Mode.KILL, actor="m", reason="r")
    return store


def test_store_check_healthy(tmp_path: Path) -> None:
    _armed_store(tmp_path)
    check = by_name(run_checks(cfg(tmp_path), probes()))["store"]
    assert check.result == "pass" and "1 active halt" in check.detail


def test_store_check_integrity_signal_fails(tmp_path: Path) -> None:
    store = _armed_store(tmp_path)
    store.path.unlink()
    check = by_name(run_checks(cfg(tmp_path), probes()))["store"]
    assert (
        check.result == "fail" and "unreachable" in check.detail and "agenthalt status" in check.fix
    )


def test_store_check_recovering_warns(tmp_path: Path) -> None:
    from agenthalt.scopes import Mode, Scope
    from agenthalt.store import HaltState

    store = _armed_store(tmp_path)
    gen = store.load().generation
    halt = HaltState.new(
        halt_id="hlt_c", scope=Scope.parse("all"), mode=Mode.PAUSE, actor="m", reason="r"
    )
    store.journal.append(
        "raise",
        actor="m",
        payload={
            "store": {
                "op": "upsert",
                "generation": gen + 1,
                "halt": halt.to_dict(),
            }
        },
    )
    check = by_name(run_checks(cfg(tmp_path), probes()))["store"]
    assert check.result == "warn" and "recover" in check.fix


def test_store_check_na_without_config(tmp_path: Path) -> None:
    err = ConfigError("bad", key="home", source="flag")
    assert by_name(run_checks(err, probes()))["store"].result == "n/a"


def test_permission_denied_journal_segment(tmp_path: Path) -> None:
    j = Journal(tmp_path / ".agenthalt")
    j.append("finding", actor="t")
    seg = j.dir / "seg-000001.jsonl"
    os.chmod(seg, 0o000)
    try:
        check = by_name(run_checks(cfg(tmp_path), probes()))["journal"]
        if os.geteuid() != 0:
            assert check.result == "fail" and "unreadable" in check.detail
    finally:
        os.chmod(seg, 0o600)


def test_hooks_detected_in_codex_toml(tmp_path: Path) -> None:
    home = tmp_path / "user"
    (home / ".codex").mkdir(parents=True)
    (home / ".codex" / "config.toml").write_text('[hooks]\npre_tool = "agenthalt hook"\n')
    check = by_name(run_checks(cfg(tmp_path), probes(user_home=home)))["hooks"]
    assert check.result == "pass" and "codex-cli" in check.detail
