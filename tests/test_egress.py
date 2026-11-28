"""3.6: the egress fallback's decisions, with a fake iptables."""

from __future__ import annotations

import time
from collections.abc import Sequence
from pathlib import Path

import pytest

from agenthalt.egress import EgressExecutor, _run, unsupported_reason
from agenthalt.executors import Context, Member
from tests.lineage_helpers import FakeObserver, proc

CG = "/user/agenthalt-run_a"


class Tables:
    def __init__(self) -> None:
        self.rules: dict[str, list[list[str]]] = {"iptables": [], "ip6tables": []}
        self.fail: str | None = None
        self.forget = False

    def __call__(self, command: Sequence[str]) -> tuple[int, str]:
        tool, _, op, _, *rest = command
        if op == self.fail:
            return 1, "nope"
        rules = self.rules[tool]
        if op == "-C":
            return (0, "") if rest in rules else (1, "no rule")
        if op == "-I":
            if not self.forget:
                rules.insert(0, rest[1:])
            return 0, ""
        if op == "-S":
            return 0, "-P OUTPUT ACCEPT\n" + "".join(f"-A OUTPUT {' '.join(r)}\n" for r in rules)
        rules.remove(rest)
        return 0, ""


def build(tmp_path: Path, tables: Tables, why: str | None = None) -> EgressExecutor:
    (tmp_path / CG.strip("/")).mkdir(parents=True, exist_ok=True)
    seen = FakeObserver(cgroups={10: CG, 11: CG + "/nested"})
    seen.add(proc(10, 1), proc(11, 10))
    return EgressExecutor(seen, runner=tables, cgroup_root=tmp_path, unsupported=lambda: why)


def member(pid: int, cgroup: str | None = CG) -> Member:
    return Member(f"n{pid}", pid, str(pid * 10), "run_a", cgroup=cgroup)


def ctx(halt: str = "hlt_1", ms: int = 5000) -> Context:
    return Context(halt, time.monotonic() + ms / 1000)


def test_block_inserts_reset_then_reject_for_both_families(tmp_path: Path) -> None:
    tables = Tables()
    run = build(tmp_path, tables)
    (result,) = run.block([member(10), member(11)], ctx())
    assert result.status == "confirmed" and result.undo == {"halt": "hlt_1", "run": "run_a"}
    for tool in ("iptables", "ip6tables"):
        first, second = tables.rules[tool]
        assert first[:2] == ["-p", "tcp"] and "tcp-reset" in first and second[-1] == "REJECT"
        for rule in (first, second):
            assert rule[rule.index("--path") + 1] == CG.strip("/")
            assert "owner" not in rule and "--uid-owner" not in rule  # never by user
    run.block([member(10)], ctx())
    assert len(tables.rules["iptables"]) == 2, "idempotent"


def test_release_removes_only_that_halts_rules(tmp_path: Path) -> None:
    tables = Tables()
    run = build(tmp_path, tables)
    run.block([member(10)], ctx("hlt_1"))
    run.block([member(10)], ctx("hlt_12"))
    tables.rules["iptables"].append(["-j", "ACCEPT"])
    (result,) = run.release([{"halt": "hlt_1", "run": "run_a"}], ctx())
    assert result.status == "confirmed"
    left = tables.rules["iptables"]
    assert len(left) == 3 and all("agenthalt:hlt_1:run_a" not in rule for rule in left)


@pytest.mark.parametrize(
    "cgroup", [None, "/user", "/user/agenthalt-run_b", "/agenthalt-run_a/../.."]
)
def test_no_own_cgroup_is_unsupported(tmp_path: Path, cgroup: str | None) -> None:
    tables = Tables()
    (result,) = build(tmp_path, tables).block([member(10, cgroup)], ctx())
    assert result.status == "unsupported" and tables.rules["iptables"] == []


def test_a_host_that_cannot_cut_is_unsupported(tmp_path: Path) -> None:
    tables = Tables()
    (result,) = build(tmp_path, tables, why="needs root").block([member(10)], ctx())
    assert (result.status, result.note) == ("unsupported", "needs root")


@pytest.mark.parametrize(("fail", "forget"), [("-I", False), (None, True)])
def test_rules_that_are_not_in_place_are_failed(
    tmp_path: Path, fail: str | None, forget: bool
) -> None:
    tables = Tables()
    tables.fail, tables.forget = fail, forget
    (result,) = build(tmp_path, tables).block([member(10)], ctx())
    assert result.status == "failed"


def test_a_member_outside_the_cgroup_is_not_claimed_cut(tmp_path: Path) -> None:
    run = build(tmp_path, Tables())
    run.observer.procs[12] = proc(12, 10)  # type: ignore[attr-defined]
    (result,) = run.block([member(10), member(12), member(99)], ctx())
    assert result.status == "failed" and "pid 12" in result.note and "99" not in result.note
    run.observer.fail = True  # type: ignore[attr-defined]
    assert run.block([member(10)], ctx())[0].status == "failed"


def test_late_rules_are_only_requested(tmp_path: Path) -> None:
    (result,) = build(tmp_path, Tables()).block([member(10)], ctx(ms=-1))
    assert result.status == "requested"


@pytest.mark.parametrize("fail", ["-S", "-D"])
def test_a_failed_release_is_reported(tmp_path: Path, fail: str) -> None:
    tables = Tables()
    run = build(tmp_path, tables)
    run.block([member(10)], ctx())
    tables.fail = fail
    assert run.release([{"halt": "hlt_1", "run": "run_a"}], ctx())[0].status == "failed"


@pytest.mark.parametrize(
    ("platform", "euid", "which", "expected"),
    [
        ("darwin", 0, "/x", "0.3.0"),
        ("win32", 0, "/x", "win32"),
        ("linux", 501, "/x", "needs root"),
        ("linux", 0, None, "not found"),
        ("linux", 0, "/x", None),
    ],
)
def test_why_a_host_cannot_cut(
    platform: str, euid: int, which: str | None, expected: str | None
) -> None:
    why = unsupported_reason(platform=platform, euid=euid, which=lambda _: which)
    assert why is None if expected is None else expected in str(why)


def test_the_runner_reports_output_and_failure() -> None:
    assert _run(["/bin/echo", "hi"]) == (0, "hi\n")
    assert _run(["/usr/bin/false"])[0] != 0
    assert _run(["/no/such/tool"])[0] == 127
