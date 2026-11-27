"""0.3 Configuration model (#402): precedence and fail-closed loading (DD-41, DD-42)."""

from __future__ import annotations

from pathlib import Path

import pytest

from agenthalt.cli import main
from agenthalt.config import DEFAULTS, Config, ConfigError, load_config


def write(tmp_path: Path, text: str, name: str = "agenthalt.toml") -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_defaults_with_no_file(tmp_path: Path) -> None:
    cfg = load_config(env={}, cwd=tmp_path)
    assert isinstance(cfg, Config)
    assert cfg.home == tmp_path / ".agenthalt"
    assert cfg.log_level == "info"
    assert cfg.log_format == "json"
    assert cfg.deadline_ms == 1000
    assert cfg.cache_ttl_s == 2
    assert cfg.pause_max_ttl_s == 86400  # DD-37
    assert cfg.segment_max_entries == 10000
    assert set(cfg.sources.values()) == {"default"}
    assert cfg.config_file is None
    assert set(DEFAULTS) == set(cfg.sources)


def test_cwd_file_is_picked_up(tmp_path: Path) -> None:
    write(tmp_path, '[log]\nlevel = "debug"\n')
    cfg = load_config(env={}, cwd=tmp_path)
    assert cfg.log_level == "debug"
    assert cfg.sources["log.level"] == f"file:{tmp_path / 'agenthalt.toml'}"


def test_precedence_flag_over_env_over_file_over_default(tmp_path: Path) -> None:
    path = write(tmp_path, '[halt]\ndeadline_ms = 300\n[log]\nlevel = "warning"\nformat = "text"\n')
    env = {"AGENTHALT_DEADLINE_MS": "400", "AGENTHALT_LOG_LEVEL": "error"}
    cfg = load_config(flags={"halt.deadline_ms": 500}, env=env, config_path=path, cwd=tmp_path)
    assert cfg.deadline_ms == 500
    assert cfg.sources["halt.deadline_ms"] == "flag"
    assert cfg.log_level == "error"
    assert cfg.sources["log.level"] == "env:AGENTHALT_LOG_LEVEL"
    assert cfg.log_format == "text"
    assert cfg.sources["log.format"].startswith("file:")
    assert cfg.cache_ttl_s == 2
    assert cfg.sources["choke.cache_ttl_s"] == "default"


def test_env_config_path(tmp_path: Path) -> None:
    path = write(tmp_path, "[pause]\nmax_ttl_s = 3600\n", name="custom.toml")
    cfg = load_config(env={"AGENTHALT_CONFIG": str(path)}, cwd=tmp_path)
    assert cfg.pause_max_ttl_s == 3600
    assert cfg.config_file == path


def test_flag_config_path_beats_env(tmp_path: Path) -> None:
    a = write(tmp_path, "[pause]\nmax_ttl_s = 600\n", name="a.toml")
    b = write(tmp_path, "[pause]\nmax_ttl_s = 900\n", name="b.toml")
    cfg = load_config(config_path=a, env={"AGENTHALT_CONFIG": str(b)}, cwd=tmp_path)
    assert cfg.pause_max_ttl_s == 600


def test_home_relative_to_config_cwd(tmp_path: Path) -> None:
    cfg = load_config(flags={"home": "state"}, env={}, cwd=tmp_path)
    assert cfg.home == tmp_path / "state"
    absolute = tmp_path / "abs"
    cfg = load_config(env={"AGENTHALT_HOME": str(absolute)}, cwd=tmp_path)
    assert cfg.home == absolute


@pytest.mark.parametrize(
    ("toml", "key"),
    [
        ("[halt]\ndeadline_ms = 0\n", "halt.deadline_ms"),
        ("[halt]\ndeadline_ms = 60001\n", "halt.deadline_ms"),
        ('[halt]\ndeadline_ms = "fast"\n', "halt.deadline_ms"),
        ("[halt]\ndeadline_ms = true\n", "halt.deadline_ms"),
        ("[choke]\ncache_ttl_s = 60\n", "choke.cache_ttl_s"),  # seconds, never minutes
        ("[choke]\ncache_ttl_s = -1\n", "choke.cache_ttl_s"),
        ("[pause]\nmax_ttl_s = 59\n", "pause.max_ttl_s"),
        ("[pause]\nmax_ttl_s = 604801\n", "pause.max_ttl_s"),
        ('[log]\nlevel = "loud"\n', "log.level"),
        ('[log]\nformat = "xml"\n', "log.format"),
        ("[journal]\nsegment_max_entries = 1\n", "journal.segment_max_entries"),
        ("home = 3\n", "home"),
        ('home = ""\n', "home"),
    ],
)
def test_invalid_values_fail_closed(tmp_path: Path, toml: str, key: str) -> None:
    path = write(tmp_path, toml)
    with pytest.raises(ConfigError) as exc:
        load_config(config_path=path, env={}, cwd=tmp_path)
    assert exc.value.key == key
    assert exc.value.source == f"file:{path}"
    assert key in str(exc.value)


@pytest.mark.parametrize(
    ("toml", "key"),
    [
        ("deadline_ms = 5\n", "deadline_ms"),
        ("[halt]\ndeadline = 5\n", "halt.deadline"),
        ("[unknown]\nx = 1\n", "unknown"),
        ('[log]\nlevel = "info"\ncolour = true\n', "log.colour"),
        ('log = "info"\n', "log"),
    ],
)
def test_unknown_keys_are_rejected(tmp_path: Path, toml: str, key: str) -> None:
    # DD-42: an ignored key is a fail-open path.
    path = write(tmp_path, toml)
    with pytest.raises(ConfigError) as exc:
        load_config(config_path=path, env={}, cwd=tmp_path)
    assert exc.value.key == key
    assert "unknown" in str(exc.value)


def test_reserved_sections_accepted_empty(tmp_path: Path) -> None:
    path = write(tmp_path, "triggers = []\n[store]\n[adapters]\n")
    cfg = load_config(config_path=path, env={}, cwd=tmp_path)
    assert cfg.deadline_ms == 1000


@pytest.mark.parametrize(
    ("toml", "key", "milestone"),
    [
        ('[store]\npath = "x"\n', "store", "M1"),
        ('[[triggers]]\nname = "siem"\n', "triggers", "M7"),
        ('[adapters]\nprocess = "x"\n', "adapters", "M3"),
    ],
)
def test_reserved_sections_with_content_rejected(
    tmp_path: Path, toml: str, key: str, milestone: str
) -> None:
    path = write(tmp_path, toml)
    with pytest.raises(ConfigError) as exc:
        load_config(config_path=path, env={}, cwd=tmp_path)
    assert exc.value.key == key
    assert milestone in str(exc.value)


def test_malformed_toml(tmp_path: Path) -> None:
    path = write(tmp_path, "[halt\n")
    with pytest.raises(ConfigError) as exc:
        load_config(config_path=path, env={}, cwd=tmp_path)
    assert exc.value.source == f"file:{path}"
    assert "TOML" in str(exc.value)


def test_missing_explicit_config_file(tmp_path: Path) -> None:
    with pytest.raises(ConfigError) as exc:
        load_config(config_path=tmp_path / "nope.toml", env={}, cwd=tmp_path)
    assert "not found" in str(exc.value)
    with pytest.raises(ConfigError) as exc:
        load_config(env={"AGENTHALT_CONFIG": str(tmp_path / "nope.toml")}, cwd=tmp_path)
    assert exc.value.source == "env:AGENTHALT_CONFIG"


def test_invalid_env_value_names_env_var(tmp_path: Path) -> None:
    with pytest.raises(ConfigError) as exc:
        load_config(env={"AGENTHALT_DEADLINE_MS": "soon"}, cwd=tmp_path)
    assert exc.value.key == "halt.deadline_ms"
    assert exc.value.source == "env:AGENTHALT_DEADLINE_MS"


def test_invalid_flag_value(tmp_path: Path) -> None:
    with pytest.raises(ConfigError) as exc:
        load_config(flags={"log.level": "loud"}, env={}, cwd=tmp_path)
    assert exc.value.source == "flag"


def test_unknown_env_names_are_not_errors(tmp_path: Path) -> None:
    cfg = load_config(env={"AGENTHALT_HMAC_KEY": "x", "AGENTHALT_DEADLNE_MS": "5"}, cwd=tmp_path)
    assert cfg.deadline_ms == 1000
    assert cfg.unknown_env == ("AGENTHALT_DEADLNE_MS", "AGENTHALT_HMAC_KEY")


def test_config_is_frozen(tmp_path: Path) -> None:
    cfg = load_config(env={}, cwd=tmp_path)
    with pytest.raises(AttributeError):
        cfg.deadline_ms = 5  # type: ignore[misc]


# --- CLI wiring: invalid config exits 5 before anything executes -------------------------


def test_cli_invalid_config_exits_usage(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    write(tmp_path, "[halt]\ndeadline_ms = 0\n")
    code = main(["kill", "--agent", "bot", "--reason", "r"])
    err = capsys.readouterr().err
    assert code == 5
    assert "halt.deadline_ms" in err
    assert "agenthalt.toml" in err
    assert "not available" not in err  # nothing else ran


def test_cli_global_flags_reach_config(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    code = main(["--log-level", "loud", "status"])
    assert code == 5
    assert "log.level" in capsys.readouterr().err
    code = main(["--config", str(tmp_path / "missing.toml"), "status"])
    assert code == 5
    assert "not found" in capsys.readouterr().err


def test_relative_config_path_resolves_from_cwd(tmp_path: Path) -> None:
    write(tmp_path, '[log]\nformat = "text"\n', name="rel.toml")
    cfg = load_config(config_path="rel.toml", env={}, cwd=tmp_path)
    assert cfg.log_format == "text" and cfg.config_file == tmp_path / "rel.toml"


def test_unreadable_config_path(tmp_path: Path) -> None:
    (tmp_path / "dir.toml").mkdir()
    with pytest.raises(ConfigError) as exc:
        load_config(config_path=tmp_path / "dir.toml", env={}, cwd=tmp_path)
    assert "cannot read" in str(exc.value)
