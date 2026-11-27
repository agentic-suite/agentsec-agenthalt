"""The ``agenthalt`` command surface (M0 design §2, PRD 37).

Every command is reserved from M0 so ``--help`` and scripts see the final surface. Commands whose
behaviour lands in a later milestone validate their arguments and then exit 5 ("not available in
this build"); the halt family also points at the manual fallback, because the person typing
``kill`` needs a way to stop the agent today.
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import NoReturn

from agenthalt import __version__
from agenthalt.config import Config, ConfigError, load_config
from agenthalt.coordinator import Coordinator
from agenthalt.doctor import Probes, format_checks, run_checks, verdict
from agenthalt.exit_codes import ExitCode, ReceiptStatus, exit_code_for
from agenthalt.ids import validate_id
from agenthalt.journal import Journal, JournalError
from agenthalt.logs import configure_logging, get_logger
from agenthalt.scopes import Mode, Scope
from agenthalt.store import Store, StoreError

__all__ = ["COMMANDS", "main"]

MANUAL_FALLBACK = "docs/prd/28-failure-mode-runbook.md §7"
FLEET_CONFIRMATION = "halt all"
HALT_MODES = ("pause", "quarantine", "kill")

EXIT_CODE_HELP = """\
Exit codes (stable contract):
  0  halt complete — all members confirmed, zero survivors
  1  halt incomplete — survivors or unconfirmed members
  2  halt partial-layer — a composed layer was unsupported
  3  halt failed — blocking never established (manual fallback)
  4  trigger rejected — auth, replay, scope ceiling, unconfirmed fleet halt
  5  usage or config error — nothing executed
When several apply, the worst wins: 3 > 1 > 2 > 0.
"""


@dataclass(frozen=True)
class Command:
    help: str
    lands_in: str


COMMANDS: dict[str, Command] = {
    "run": Command("launch an agent under the enrollment supervisor", "M2"),
    "attach": Command("enroll an already-running agent (best-effort)", "M2"),
    "halt": Command("raise a halt against a target", "M1 (choke); layers M3-M4"),
    "pause": Command("halt in pause mode (freeze, resumable)", "M9"),
    "quarantine": Command("halt in quarantine mode (freeze + cut network)", "M9"),
    "kill": Command("halt in kill mode (terminate + revoke)", "M3-M4"),
    "resume": Command("resume a paused run", "M9"),
    "escalate": Command("move a halt one rung up the ladder", "M9"),
    "lift": Command("lift a halt (journaled)", "M1"),
    "status": Command("live halt state and the 09:01 readout", "M1, M6"),
    "prove": Command("verify a receipt, online or offline", "M6"),
    "drill": Command("run the halt rehearsal catalogue", "M10"),
    "journal": Command("show or verify the tamper-evident halt journal", "M0"),
    "evidence": Command("collect, export or verify evidence snapshots", "M5"),
    "doctor": Command("preflight sanity checks", "M0"),
    "runbook": Command("print an operator runbook section", "M11"),
}


class UsageError(Exception):
    """A usage problem; the CLI exits 5 and nothing is executed."""


class RejectedError(Exception):
    """A trigger the CLI must refuse; the CLI exits 4."""


class _Parser(argparse.ArgumentParser):
    """ArgumentParser whose errors exit 5, not argparse's 2 (2 is ``partial-layer``)."""

    def error(self, message: str) -> NoReturn:
        raise UsageError(f"{self.prog}: {message}")


# --------------------------------------------------------------------------- argument types


def _positive_int(value: str) -> int:
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not an integer: {value!r}") from None
    if number <= 0:
        raise argparse.ArgumentTypeError(f"must be a positive integer: {value!r}")
    return number


def _identifier(what: str) -> Callable[[str], str]:
    def check(value: str) -> str:
        try:
            return validate_id(value, what=what)
        except ValueError as exc:
            raise argparse.ArgumentTypeError(str(exc)) from None

    return check


# --------------------------------------------------------------------------- parser


def _add_halt_arguments(parser: argparse.ArgumentParser, *, with_mode: bool) -> None:
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--agent", type=_identifier("--agent"), help="an agent and its subtree")
    target.add_argument("--session", type=_identifier("--session"), help="one session")
    target.add_argument("--run", type=_identifier("--run"), help="one run and its subtree")
    target.add_argument("--all", action="store_true", help="every agent the ecosystem can see")
    if with_mode:
        parser.add_argument("--mode", choices=HALT_MODES, default="pause", help="stop mode")
    parser.add_argument("--reason", help="why (required for kill and --all; journaled)")
    parser.add_argument("--deadline-ms", type=_positive_int, help="confirmation deadline")
    parser.add_argument("--yes", action="store_true", help="skip the typed fleet confirmation")
    parser.add_argument("--json", action="store_true", help="emit the receipt as JSON")


def build_parser() -> _Parser:
    parser = _Parser(
        prog="agenthalt",
        description="The universal agent kill-switch.",
        epilog=EXIT_CODE_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"agenthalt {__version__}")
    parser.add_argument("--config", help="config file (default: ./agenthalt.toml if present)")
    parser.add_argument("--home", help="state directory (default: .agenthalt)")
    parser.add_argument("--log-level", help="debug, info, warning or error")
    parser.add_argument("--log-format", help="json or text")
    sub = parser.add_subparsers(dest="command", metavar="<command>", parser_class=_Parser)

    def add(name: str, **kwargs: object) -> argparse.ArgumentParser:
        p: argparse.ArgumentParser = sub.add_parser(
            name,
            help=COMMANDS[name].help,
            description=COMMANDS[name].help,
            **kwargs,  # type: ignore[arg-type]
        )
        return p

    p = add("run", usage="agenthalt run [--name NAME] -- <cmd> [args...]")
    p.add_argument("--name", type=_identifier("--name"), help="name for the enrolled run")

    p = add("attach")
    p.add_argument("--pid", type=_positive_int, required=True, help="process id to enroll")
    p.add_argument("--name", type=_identifier("--name"), help="name for the enrolled run")

    _add_halt_arguments(add("halt"), with_mode=True)
    for mode in HALT_MODES:
        _add_halt_arguments(add(mode), with_mode=False)

    p = add("resume")
    p.add_argument("--halt", type=_identifier("--halt"), required=True)
    p = add("escalate")
    p.add_argument("--halt", type=_identifier("--halt"), required=True)
    p.add_argument("--to", choices=HALT_MODES, required=True)
    p = add("lift")
    p.add_argument("--halt", type=_identifier("--halt"), required=True)
    p.add_argument("--reason", required=True)

    p = add("status")
    p.add_argument("--halt", type=_identifier("--halt"))
    p.add_argument("--watch", action="store_true")
    p.add_argument("--json", action="store_true")
    p = add("prove")
    p.add_argument("--receipt", required=True)
    p.add_argument("--evidence")
    p = add("drill")
    p.add_argument("--case")
    p.add_argument("--platform", choices=("macos", "linux"))
    p.add_argument("--all", action="store_true")
    p.add_argument("--json", action="store_true")

    p = add("journal")
    journal = p.add_subparsers(
        dest="journal_command", metavar="{show,verify}", required=True, parser_class=_Parser
    )
    show = journal.add_parser("show", help="print journal entries")
    show.add_argument("--halt", type=_identifier("--halt"))
    show.add_argument("--json", action="store_true")
    journal.add_parser("verify", help="verify the hash chain")

    p = add("evidence")
    evidence = p.add_subparsers(
        dest="evidence_command",
        metavar="{collect,export,verify}",
        required=True,
        parser_class=_Parser,
    )
    for name in ("collect", "export", "verify"):
        e = evidence.add_parser(name)
        e.add_argument("--halt", type=_identifier("--halt"), required=True)
        e.add_argument("--out")

    p = add("doctor")
    p.add_argument("--migrate", action="store_true")
    p.add_argument("--verbose", action="store_true")
    p.add_argument("--json", action="store_true")

    p = add("runbook")
    p.add_argument("--section", type=_positive_int)
    return parser


# --------------------------------------------------------------------------- handlers


def _unavailable(command: str) -> int:
    print(
        f"agenthalt {command}: not available in this build "
        f"(lands in {COMMANDS[command].lands_in}).",
        file=sys.stderr,
    )
    return int(ExitCode.USAGE)


def _check_halt(args: argparse.Namespace) -> None:
    mode = args.command if args.command in HALT_MODES else args.mode
    if (mode == "kill" or args.all) and not args.reason:
        raise UsageError(f"agenthalt {args.command}: --reason is required for kill and --all")
    if args.all and not args.yes:
        if not sys.stdin.isatty():
            raise RejectedError(
                f"agenthalt {args.command} --all: a fleet halt needs a typed confirmation "
                "or --yes; refusing in a non-interactive context"
            )
        answer = input(f"This halts every agent. Type '{FLEET_CONFIRMATION}' to confirm: ")
        if answer.strip() != FLEET_CONFIRMATION:
            raise RejectedError(f"agenthalt {args.command} --all: confirmation did not match")


def _check_attach(pid: int) -> None:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        raise UsageError(f"agenthalt attach: no such process: {pid}") from None
    except PermissionError:
        raise UsageError(
            f"agenthalt attach: process {pid} belongs to another user; nothing enrolled"
        ) from None


def _journal(args: argparse.Namespace, config: Config) -> int:
    journal = Journal(config.home, segment_max_entries=config.segment_max_entries)
    if args.journal_command == "verify":
        result = journal.verify()
        if result.ok:
            print(result.describe())
            return int(ExitCode.COMPLETE)
        print(result.describe(), file=sys.stderr)
        print(
            f"  The broken record is incident evidence: do not edit it. See {MANUAL_FALLBACK}.",
            file=sys.stderr,
        )
        return int(ExitCode.INCOMPLETE)
    # show
    try:
        for entry in journal.entries(halt_id=args.halt):
            if args.json:
                print(json.dumps(entry, sort_keys=True))
            else:
                print(
                    f"{entry['seq']:>6}  {entry['timestamp']}  {entry['action']:<16} "
                    f"halt={entry['halt_id'] or '-'}  actor={entry['actor']}  "
                    f"scope={entry['scope'] or '-'}  mode={entry['mode'] or '-'}  "
                    f"reason={entry['reason'] or '-'}"
                )
    except JournalError as exc:
        print(f"agenthalt journal show: {exc}", file=sys.stderr)
        return int(ExitCode.INCOMPLETE)
    return int(ExitCode.COMPLETE)


def _doctor(args: argparse.Namespace, config: Config | ConfigError) -> int:
    if args.migrate:
        print("doctor --migrate: no migrations in this version")
    checks = run_checks(config, Probes.real())
    print(format_checks(checks, as_json=args.json))
    if args.verbose and isinstance(config, Config) and not args.json:
        print("config:")
        for key, value in config.values().items():
            print(f"  {key} = {value} ({config.sources[key]})")
    return int(ExitCode.USAGE) if verdict(checks) == "fail" else int(ExitCode.COMPLETE)


def _actor() -> str:
    try:
        return getpass.getuser()
    except (KeyError, OSError):  # pragma: no cover - no passwd entry
        return f"uid:{os.getuid()}"


def _scope(args: argparse.Namespace) -> Scope:
    if args.all:
        return Scope("all")
    if args.agent:
        return Scope("agent", args.agent)
    if args.session:
        return Scope("session", args.session)
    return Scope("subtree", args.run)  # --run means "one run and its subtree"


def _store(config: Config) -> Store:
    store = Store(
        config.home, journal=Journal(config.home, segment_max_entries=config.segment_max_entries)
    )
    store.ensure()
    return store


def _halt(args: argparse.Namespace, config: Config) -> int:
    mode = Mode.parse(args.command if args.command in HALT_MODES else args.mode)
    scope = _scope(args)
    result = Coordinator(_store(config)).raise_halt(scope, mode, actor=_actor(), reason=args.reason)
    # An idempotent re-raise returns the halt already in force;
    # in M1 its outcome is still incomplete.
    outcome = result.outcome or ReceiptStatus.INCOMPLETE
    if args.json:
        print(
            json.dumps(
                {
                    "halt_id": result.halt.halt_id,
                    "created": result.created,
                    "scope": str(result.halt.scope),
                    "mode": result.halt.mode.label,
                    "status": result.halt.status.value,
                    "outcome": outcome.value,
                    "layers": result.layers or None,
                },
                sort_keys=True,
            )
        )
        return int(exit_code_for(outcome))
    if result.created:
        print(
            f"halt {result.halt.halt_id} recorded — {scope} · {mode.label}: "
            "enforced at the runtime choke."
        )
    else:
        print(
            f"halt {result.halt.halt_id} is already active for {scope} · {mode.label} (idempotent)."
        )
    print(
        "  NOT done in this build: process suspend/kill, credential revoke, gateway, "
        "sandbox (M3-M4)."
    )
    print(
        f"  outcome: {outcome.value} (exit {int(exit_code_for(outcome))}). To stop the agent now, "
        f"use the manual fallback: {MANUAL_FALLBACK}."
    )
    return int(exit_code_for(outcome))


def _status(args: argparse.Namespace, config: Config) -> int:
    store = _store(config)
    health = store.health()
    recovered = False
    if health.status == "recovering":
        store.rebuild()
        store.journal.append(
            "finding",
            actor=_actor(),
            payload={"finding": "store_recovered", "detail": health.detail},
        )
        recovered, health = True, store.health()
    try:
        halts = list(store.load().halts) if health.status == "ok" else list(store.replay().halts)
    except (StoreError, JournalError):  # status still reports what it can
        halts = []
    if args.halt:
        halts = [h for h in halts if h.halt_id == args.halt]
        if not halts:
            raise UsageError(f"agenthalt status: no active halt {args.halt}")
    healthy = health.status == "ok" and health.signal is None
    if args.json:
        print(
            json.dumps(
                {
                    "health": {
                        "status": health.status,
                        "signal": health.signal,
                        "armed": health.armed,
                        "detail": health.detail,
                        "recovered": recovered,
                    },
                    "halts": [h.to_dict() for h in halts],
                },
                sort_keys=True,
            )
        )
        return int(ExitCode.COMPLETE if healthy else ExitCode.INCOMPLETE)
    if recovered:
        print("store: recovered from the journal after an interrupted write")
    line = f"store: {health.status}" + (
        f" · integrity signal: {health.signal}" if health.signal else ""
    )
    print(f"{line} — {health.detail}")
    if not halts:
        print("no active halts")
    for h in halts:
        print(
            f"  {h.halt_id}  {h.scope!s:<24} {h.mode.label:<10} {h.status.value:<9} "
            f"set {h.set_at} by {h.actor} — {h.reason or '-'}"
        )
    if not healthy:
        print(
            f"  The store does not match the journal. Do not edit either; see {MANUAL_FALLBACK}.",
            file=sys.stderr,
        )
        return int(ExitCode.INCOMPLETE)
    return int(ExitCode.COMPLETE)


def _lift(args: argparse.Namespace, config: Config) -> int:
    try:
        Coordinator(_store(config)).lift(args.halt, actor=_actor(), reason=args.reason)
    except (LookupError, ValueError) as exc:
        raise UsageError(f"agenthalt lift: {exc}") from None
    print(f"halt {args.halt} lifted (journaled).")
    return int(ExitCode.COMPLETE)


def _dispatch(args: argparse.Namespace, run_command: list[str] | None, config: Config) -> int:
    command: str = args.command
    if command == "journal":
        return _journal(args, config)
    if command in ("halt", *HALT_MODES):
        _check_halt(args)
        return _halt(args, config)
    if command == "status":
        return _status(args, config)
    if command == "lift":
        return _lift(args, config)
    if command == "run":
        if not run_command:
            raise UsageError(
                "agenthalt run: give the agent command after '--': run -- <cmd> [args...]"
            )
        return _unavailable(command)
    if command == "attach":
        _check_attach(args.pid)
        return _unavailable(command)
    return _unavailable(command)


def _split_run(argv: list[str]) -> tuple[list[str], list[str] | None]:
    """Split ``run ... -- <cmd>`` by hand.

    argparse's REMAINDER handling of ``--`` differs across Python versions.
    """
    if argv and argv[0] == "run":
        if "--" in argv:
            i = argv.index("--")
            return argv[:i], argv[i + 1 :]
        return argv, None
    return argv, None


def main(argv: Sequence[str] | None = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    own, run_command = _split_run(raw)
    parser = build_parser()
    try:
        args = parser.parse_args(own)
        if args.command is None:
            parser.print_help(sys.stderr)
            return int(ExitCode.USAGE)
        flags = {
            "home": args.home,
            "log.level": args.log_level,
            "log.format": args.log_format,
            "halt.deadline_ms": getattr(args, "deadline_ms", None),
        }
        if args.command == "doctor":
            # doctor reports a broken configuration instead of refusing to run.
            try:
                loaded: Config | ConfigError = load_config(flags=flags, config_path=args.config)
            except ConfigError as exc:
                loaded = exc
            return _doctor(args, loaded)
        # Fail closed: a configuration that does not load stops everything (DD-03, DD-42).
        config = load_config(flags=flags, config_path=args.config)
        configure_logging(config.log_level, config.log_format)
        get_logger().debug("command", extra={"fields": {"command": args.command}})
        return _dispatch(args, run_command, config)
    except ConfigError as exc:
        print(f"agenthalt: config error: {exc}", file=sys.stderr)
        return int(ExitCode.USAGE)
    except UsageError as exc:
        print(f"agenthalt: error: {exc}", file=sys.stderr)
        return int(ExitCode.USAGE)
    except RejectedError as exc:
        print(f"agenthalt: rejected: {exc}", file=sys.stderr)
        return int(ExitCode.TRIGGER_REJECTED)
