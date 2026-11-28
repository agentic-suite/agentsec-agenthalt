"""``agenthalt doctor`` — preflight checks before you need them at 3 a.m. (M0 design §7).

Each check returns ``pass``, ``warn``, ``fail`` or ``n/a`` with a one-line fix. The verdict is the
worst result; ``fail`` makes the CLI exit 5. Platform probes are injectable so every path is
testable on any OS. Platform checks are ``warn`` in M0 because nothing in M0 depends on them;
enrollment (M2) and the panic key (M7) promote them for the features that need them.
"""

from __future__ import annotations

import difflib
import json
import os
import stat
import sys
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path

from agenthalt.config import CONFIG_ENV, ENV_NAMES, Config, ConfigError
from agenthalt.egress import EgressExecutor, unsupported_reason
from agenthalt.executors import load_adapters
from agenthalt.journal import Journal
from agenthalt.lineage import LineageError, LineageRegistry
from agenthalt.observe import SystemObserver
from agenthalt.process_exec import ProcessExecutor

__all__ = ["Check", "Probes", "format_checks", "run_checks", "verdict"]

_RANK = {"n/a": 0, "pass": 0, "warn": 1, "fail": 2}
RUNBOOK = "docs/prd/28-failure-mode-runbook.md"


@dataclass(frozen=True)
class Check:
    name: str
    result: str  # pass | warn | fail | n/a
    detail: str
    fix: str


def verdict(checks: list[Check]) -> str:
    worst = max((_RANK[c.result] for c in checks), default=0)
    return {0: "pass", 1: "warn", 2: "fail"}[worst]


# --------------------------------------------------------------------------- probes


def _ax_trusted_real() -> bool | None:
    """macOS: is this process trusted for Accessibility (needed for a global hotkey)?"""
    try:
        import ctypes

        lib = ctypes.cdll.LoadLibrary(
            "/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices"
        )
        lib.AXIsProcessTrusted.restype = ctypes.c_bool
        return bool(lib.AXIsProcessTrusted())
    except (OSError, AttributeError):  # pragma: no cover - depends on the host
        return None


def _cgroup_real() -> tuple[bool, bool]:
    """Linux: (cgroup v2 mounted, the user's cgroup is delegated/writable)."""
    root = Path("/sys/fs/cgroup")
    if not (root / "cgroup.controllers").exists():
        return False, False
    try:  # pragma: no cover - depends on the host
        own = next(
            line.split("::", 1)[1].strip()
            for line in Path("/proc/self/cgroup").read_text().splitlines()
            if line.startswith("0::")
        )
    except (OSError, StopIteration):  # pragma: no cover
        return True, False
    group = root / own.lstrip("/")  # pragma: no cover
    return True, os.access(group, os.W_OK) and os.access(
        group / "cgroup.procs", os.W_OK
    )  # pragma: no cover


@dataclass(frozen=True)
class Probes:
    python: tuple[int, int]
    platform: str
    ax_trusted: Callable[[], bool | None]
    cgroup: Callable[[], tuple[bool, bool]]
    user_home: Path

    @classmethod
    def real(cls) -> Probes:
        return cls(
            python=(sys.version_info.major, sys.version_info.minor),
            platform=sys.platform,
            ax_trusted=_ax_trusted_real,
            cgroup=_cgroup_real,
            user_home=Path.home(),
        )


# --------------------------------------------------------------------------- checks


def _python(p: Probes) -> Check:
    version = f"{p.python[0]}.{p.python[1]}"
    if p.python < (3, 10):
        return Check("python", "fail", f"Python {version}", "install Python >= 3.10")
    return Check("python", "pass", f"Python {version}", "")


def _platform(p: Probes) -> Check:
    if p.platform in ("darwin", "linux"):
        return Check("platform", "pass", {"darwin": "macOS", "linux": "Linux"}[p.platform], "")
    return Check(
        "platform",
        "fail",
        f"{p.platform} is not supported (DD-17)",
        "use macOS or Linux; the Windows plan is dated in PRD 40",
    )


def _config(cfg: Config | ConfigError) -> Check:
    if isinstance(cfg, ConfigError):
        return Check("config", "fail", str(cfg), f"fix '{cfg.key}' in {cfg.source}")
    where = str(cfg.config_file) if cfg.config_file else "defaults (no agenthalt.toml)"
    return Check("config", "pass", f"loaded from {where}", "")


def _env(cfg: Config | ConfigError) -> Check:
    if isinstance(cfg, ConfigError):
        return Check("env", "n/a", "config did not load", "")
    # Compare only what follows the shared prefix, or every name looks alike.
    prefix = len("AGENTHALT_")
    known = {name[prefix:]: name for name in (*ENV_NAMES, CONFIG_ENV)}
    typos = []
    for name in cfg.unknown_env:
        match = difflib.get_close_matches(name[prefix:], list(known), n=1, cutoff=0.8)
        if match:
            typos.append(f"{name} (did you mean {known[match[0]]}?)")
    if typos:
        return Check("env", "warn", "possible misspelt config variables", "; ".join(typos))
    others = len(cfg.unknown_env)
    return Check(
        "env", "pass", f"{others} other AGENTHALT_* name(s), none look like config keys", ""
    )


def _nearest_existing(path: Path) -> Path:
    while not path.exists() and path != path.parent:
        path = path.parent
    return path


def _home(cfg: Config | ConfigError) -> Check:
    if isinstance(cfg, ConfigError):
        return Check("home", "n/a", "config did not load", "")
    home = cfg.home
    if home.exists():
        if not home.is_dir():
            return Check("home", "fail", f"{home} is not a directory", "remove it or set --home")
        mode = stat.S_IMODE(home.stat().st_mode)
        if mode & 0o077:
            return Check(
                "home", "fail", f"{home} is mode {mode:o} (readable by others)", f"chmod 700 {home}"
            )
        if not os.access(home, os.W_OK | os.X_OK):
            return Check("home", "fail", f"{home} is not writable", f"chown/chmod {home}")
        return Check("home", "pass", f"{home} (0700)", "")
    parent = _nearest_existing(home.parent)
    if not os.access(parent, os.W_OK | os.X_OK):
        return Check(
            "home",
            "fail",
            f"{home} cannot be created ({parent} is not writable)",
            "make the parent writable or set --home / AGENTHALT_HOME",
        )
    return Check("home", "pass", f"{home} (will be created 0700)", "")


def _journal(cfg: Config | ConfigError) -> Check:
    if isinstance(cfg, ConfigError):
        return Check("journal", "n/a", "config did not load", "")
    journal = Journal(cfg.home, segment_max_entries=cfg.segment_max_entries)
    if not journal.dir.is_dir():
        return Check("journal", "pass", "no journal yet", "")
    result = (
        journal.verify()
    )  # reports unreadable/undecodable segments as a broken chain; never raises
    if not result.ok:
        return Check(
            "journal",
            "fail",
            result.describe(),
            f"run `agenthalt journal verify`; do not edit the journal — it is evidence ({RUNBOOK})",
        )
    return Check("journal", "pass", f"intact: {result.entries} entries; head {result.head}", "")


def _store(cfg: Config | ConfigError) -> Check:
    if isinstance(cfg, ConfigError):
        return Check("store", "n/a", "config did not load", "")
    from agenthalt.store import Store

    store = Store(cfg.home, journal=Journal(cfg.home, segment_max_entries=cfg.segment_max_entries))
    if not store.path.exists() and not store.journal.dir.exists():
        return Check(
            "store",
            "warn",
            "halt store not created yet — until it exists the choke denies high-impact actions",
            "run `agenthalt status` to create it",
        )
    health = store.health()
    if health.signal is not None:
        return Check(
            "store",
            "fail",
            f"integrity signal {health.signal}: {health.detail}",
            f"run `agenthalt status`; do not edit the store or journal ({RUNBOOK})",
        )
    if health.status == "recovering":
        return Check(
            "store", "warn", health.detail, "run `agenthalt status` to recover from the journal"
        )
    if health.status != "ok":
        return Check("store", "warn", health.detail, "run `agenthalt status` to create it")
    count = len(store.load().halts)
    return Check("store", "pass", f"ok · {count} active halt(s) · {health.detail}", "")


def _lineage(cfg: Config | ConfigError) -> Check:
    if isinstance(cfg, ConfigError):
        return Check("lineage", "n/a", "config did not load", "")
    journal = Journal(cfg.home, segment_max_entries=cfg.segment_max_entries)
    registry = LineageRegistry(cfg.home, journal=journal)
    fix = f"run `agenthalt status`; do not edit the lineage or journal ({RUNBOOK})"
    try:
        read = registry.read()
    except (LineageError, OSError) as exc:
        return Check("lineage", "fail", str(exc), fix)
    if read.findings:
        first = read.findings[0]
        return Check(
            "lineage",
            "fail",
            f"{len(read.findings)} tamper finding(s), first: {first.problem} at seq {first.seq}",
            fix,
        )
    if not read.edges:
        return Check("lineage", "pass", "no runs enrolled yet", "")
    return Check("lineage", "pass", f"intact: {len(read.edges)} edge(s)", "")


def _adapters() -> Check:
    observer = SystemObserver()
    try:
        found = load_adapters(
            {
                "process-tree": lambda: ProcessExecutor(observer),
                "egress-fallback": lambda: EgressExecutor(observer),
            }
        )
    except ConfigError as exc:
        return Check("adapters", "fail", str(exc), "remove or fix the broken executor package")
    listed = ", ".join(f"{layer}: {a.name}" for layer, a in sorted(found.items()))
    return Check("adapters", "pass", listed, "")


def _egress(p: Probes) -> Check:
    why = unsupported_reason(platform=p.platform)
    if why is None:
        return Check("egress", "pass", "network cut available for runs with their own cgroup", "")
    if p.platform != "linux":
        return Check("egress", "n/a", why, "")
    return Check(
        "egress",
        "warn",
        f"{why}; quarantine and kill will report the network as uncut",
        "run halts with sudo and install iptables",
    )


def _panic_key(p: Probes) -> Check:
    if p.platform != "darwin":
        return Check("panic_key", "n/a", "macOS-only check", "")
    trusted = p.ax_trusted()
    fix = (
        "System Settings → Privacy & Security → Accessibility: allow your terminal "
        "(needed by the panic key, M7)"
    )
    if trusted is True:
        return Check("panic_key", "pass", "Accessibility permission granted", "")
    if trusted is False:
        return Check("panic_key", "warn", "Accessibility permission not granted", fix)
    return Check("panic_key", "warn", "could not determine the Accessibility permission", fix)


def _cgroup(p: Probes) -> Check:
    if p.platform != "linux":
        return Check("cgroup", "n/a", "Linux-only check", "")
    v2, delegated = p.cgroup()
    if not v2:
        return Check(
            "cgroup",
            "warn",
            "cgroup v2 not mounted",
            "enable the unified cgroup v2 hierarchy (enrollment needs it, M2)",
        )
    if not delegated:
        return Check(
            "cgroup",
            "warn",
            "cgroup v2 present but your cgroup is not delegated (`agenthalt run` will refuse)",
            "run agents under `systemd-run --user --scope` or enable user delegation (M2)",
        )
    return Check("cgroup", "pass", "cgroup v2 with user delegation", "")


_HOOK_FILES = {
    "claude-code": ".claude/settings.json",
    "codex-cli": ".codex/config.toml",
    "gemini-cli": ".gemini/settings.json",
}


def _hooks(p: Probes) -> Check:
    present = []
    for harness, rel in _HOOK_FILES.items():
        path = p.user_home / rel
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if rel.endswith(".json"):
            try:
                hooks = json.loads(text).get("hooks", {})
            except (json.JSONDecodeError, AttributeError):
                continue
            text = json.dumps(hooks)
        if "agenthalt" in text:
            present.append(harness)
    if present:
        detail = f"agenthalt hooks present for: {', '.join(present)} (accelerants only, ADR-0005)"
    else:
        detail = "agenthalt hooks: none — containment does not depend on them (ADR-0005)"
    return Check("hooks", "pass", detail, "")


def run_checks(cfg: Config | ConfigError, probes: Probes) -> list[Check]:
    return [
        _python(probes),
        _platform(probes),
        _config(cfg),
        _env(cfg),
        _home(cfg),
        _journal(cfg),
        _store(cfg),
        _lineage(cfg),
        _adapters(),
        _egress(probes),
        _panic_key(probes),
        _cgroup(probes),
        _hooks(probes),
    ]


def format_checks(checks: list[Check], *, as_json: bool = False) -> str:
    result = verdict(checks)
    if as_json:
        return json.dumps({"verdict": result, "checks": [asdict(c) for c in checks]}, indent=2)
    width = max(len(c.name) for c in checks)
    lines = []
    for c in checks:
        lines.append(f"  [{c.result:<4}] {c.name:<{width}}  {c.detail}")
        if c.fix and c.result in ("warn", "fail"):
            lines.append(f"  {'':<6} {'':<{width}}  fix: {c.fix}")
    lines.append(f"verdict: {result}")
    return "\n".join(lines)
