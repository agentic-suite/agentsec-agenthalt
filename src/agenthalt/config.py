"""Configuration model (M0 design §4).

Precedence is **flags > ``AGENTHALT_*`` env > config file > defaults**. The file is TOML
(``agenthalt.toml``, DD-41). Loading is fail-closed (DD-03, DD-42): a malformed file, a wrong
type, an out-of-range value or an **unknown key** refuses to load, and the error names the exact
key and where it came from. Unknown ``AGENTHALT_*`` environment names are *not* errors — secret
references share the prefix — but they are reported so ``doctor`` can warn about likely typos.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - exercised on Python 3.10 only
    import tomli as tomllib

__all__ = ["DEFAULTS", "ENV_NAMES", "Config", "ConfigError", "load_config"]

CONFIG_FILENAME = "agenthalt.toml"
CONFIG_ENV = "AGENTHALT_CONFIG"
ENV_PREFIX = "AGENTHALT_"

# Reserved sections: accepted empty, rejected with content until their milestone lands.
RESERVED = {"store": "M1", "adapters": "M3", "triggers": "M7"}


class ConfigError(Exception):
    """The configuration refused to load. The CLI exits 5 and nothing else runs."""

    def __init__(self, message: str, *, key: str, source: str) -> None:
        self.key = key
        self.source = source
        self.message = message
        super().__init__(f"config key '{key}' ({source}): {message}")


Validator = Callable[[Any, bool], Any]  # (value, from_text) -> validated value


def _int_range(low: int, high: int | None) -> Validator:
    def check(value: Any, from_text: bool) -> int:
        if from_text:
            try:
                value = int(value)
            except (TypeError, ValueError):
                raise ValueError(f"expected an integer, got {value!r}") from None
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"expected an integer, got {value!r}")
        if value < low or (high is not None and value > high):
            bound = f"{low}..{high}" if high is not None else f">= {low}"
            raise ValueError(f"must be {bound}, got {value}")
        return value

    return check


def _choice(*options: str) -> Validator:
    def check(value: Any, from_text: bool) -> str:
        if not isinstance(value, str) or value not in options:
            raise ValueError(f"must be one of {', '.join(options)}; got {value!r}")
        return value

    return check


def _path(value: Any, from_text: bool) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"expected a non-empty path, got {value!r}")
    return value


@dataclass(frozen=True)
class _Key:
    default: Any
    validate: Validator
    env: str


KEYS: dict[str, _Key] = {
    "home": _Key(".agenthalt", _path, "AGENTHALT_HOME"),
    "log.level": _Key("info", _choice("debug", "info", "warning", "error"), "AGENTHALT_LOG_LEVEL"),
    "log.format": _Key("json", _choice("json", "text"), "AGENTHALT_LOG_FORMAT"),
    "halt.deadline_ms": _Key(1000, _int_range(1, 60_000), "AGENTHALT_DEADLINE_MS"),
    # The choke cache TTL is seconds, never minutes (PRD 13):
    # a minutes-long cache in front of a kill state is not a kill switch.
    "choke.cache_ttl_s": _Key(2, _int_range(0, 59), "AGENTHALT_CACHE_TTL_S"),
    "pause.max_ttl_s": _Key(86_400, _int_range(60, 604_800), "AGENTHALT_PAUSE_MAX_TTL_S"),
    "journal.segment_max_entries": _Key(
        10_000, _int_range(2, None), "AGENTHALT_JOURNAL_SEGMENT_MAX_ENTRIES"
    ),
}

DEFAULTS: dict[str, Any] = {name: key.default for name, key in KEYS.items()}
ENV_NAMES: dict[str, str] = {key.env: name for name, key in KEYS.items()}
_TABLES = {name.split(".")[0] for name in KEYS if "." in name}


@dataclass(frozen=True)
class Config:
    """The loaded configuration. ``sources`` records where every value came from."""

    home: Path
    log_level: str
    log_format: str
    deadline_ms: int
    cache_ttl_s: int
    pause_max_ttl_s: int
    segment_max_entries: int
    sources: Mapping[str, str]
    config_file: Path | None
    unknown_env: tuple[str, ...]

    def values(self) -> dict[str, Any]:
        """Every config key with its effective value, in key order."""
        return {
            "home": str(self.home),
            "log.level": self.log_level,
            "log.format": self.log_format,
            "halt.deadline_ms": self.deadline_ms,
            "choke.cache_ttl_s": self.cache_ttl_s,
            "pause.max_ttl_s": self.pause_max_ttl_s,
            "journal.segment_max_entries": self.segment_max_entries,
        }


def _flatten_file(data: dict[str, Any], source: str) -> dict[str, Any]:
    flat: dict[str, Any] = {}
    for top, value in data.items():
        if top in RESERVED:
            empty = value == {} or value == []
            if not empty:
                raise ConfigError(
                    f"section is reserved and lands in {RESERVED[top]}; "
                    "it must be empty in this build",
                    key=top,
                    source=source,
                )
            continue
        if top in _TABLES:
            if not isinstance(value, dict):
                raise ConfigError(f"unknown key (expected a [{top}] table)", key=top, source=source)
            for sub, subvalue in value.items():
                name = f"{top}.{sub}"
                if name not in KEYS:
                    raise ConfigError("unknown key", key=name, source=source)
                flat[name] = subvalue
            continue
        if top in KEYS:
            flat[top] = value
            continue
        raise ConfigError("unknown key", key=top, source=source)
    return flat


def _read_file(path: Path, source: str) -> dict[str, Any]:
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        raise ConfigError(f"config file not found: {path}", key="config", source=source) from None
    except OSError as exc:
        raise ConfigError(f"cannot read config file: {exc}", key="config", source=source) from None
    try:
        data = tomllib.loads(raw.decode("utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
        raise ConfigError(f"invalid TOML: {exc}", key="config", source=f"file:{path}") from None
    return _flatten_file(data, f"file:{path}")


def load_config(
    *,
    flags: Mapping[str, Any] | None = None,
    env: Mapping[str, str] | None = None,
    config_path: Path | str | None = None,
    cwd: Path | None = None,
) -> Config:
    """Load the configuration with full precedence. Raises ``ConfigError`` (fail-closed)."""
    env = dict(os.environ if env is None else env)
    cwd = Path.cwd() if cwd is None else cwd
    flags = dict(flags or {})

    file_path: Path | None = None
    file_source = ""
    if config_path is not None:
        file_path, file_source = Path(config_path), "flag:--config"
    elif env.get(CONFIG_ENV):
        file_path, file_source = Path(env[CONFIG_ENV]), f"env:{CONFIG_ENV}"
    elif (cwd / CONFIG_FILENAME).is_file():
        file_path, file_source = cwd / CONFIG_FILENAME, "cwd"
    if file_path is not None and not file_path.is_absolute():
        file_path = cwd / file_path

    file_values = _read_file(file_path, file_source) if file_path is not None else {}

    values: dict[str, Any] = {}
    sources: dict[str, str] = {}
    for name, key in KEYS.items():
        if name in flags and flags[name] is not None:
            raw, source, from_text = flags[name], "flag", isinstance(flags[name], str)
        elif key.env in env:
            raw, source, from_text = env[key.env], f"env:{key.env}", True
        elif name in file_values:
            raw, source, from_text = file_values[name], f"file:{file_path}", False
        else:
            raw, source, from_text = key.default, "default", False
        try:
            values[name] = key.validate(raw, from_text)
        except ValueError as exc:
            raise ConfigError(str(exc), key=name, source=source) from None
        sources[name] = source

    unknown_env = tuple(
        sorted(
            n for n in env if n.startswith(ENV_PREFIX) and n not in ENV_NAMES and n != CONFIG_ENV
        )
    )
    home = Path(values["home"])
    return Config(
        home=home if home.is_absolute() else cwd / home,
        log_level=values["log.level"],
        log_format=values["log.format"],
        deadline_ms=values["halt.deadline_ms"],
        cache_ttl_s=values["choke.cache_ttl_s"],
        pause_max_ttl_s=values["pause.max_ttl_s"],
        segment_max_entries=values["journal.segment_max_entries"],
        sources=sources,
        config_file=file_path,
        unknown_env=unknown_env,
    )
