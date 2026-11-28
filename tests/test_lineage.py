"""2.1 / 2.2 / 2.6 (#425, #426, #430): the append-only, authenticated, tamper-evident registry."""

from __future__ import annotations

import json
import stat
import time
from pathlib import Path

import pytest

from agenthalt.journal import Journal
from agenthalt.lineage import AdapterCredential, ForgedEdgeError, LineageError
from tests.lineage_helpers import adapters, edge, make_registry, root


def lines(home: Path, name: str = "seg-000001.jsonl") -> list[str]:
    return (home / "lineage" / name).read_text().splitlines()


def rewrite(home: Path, rows: list[str], name: str = "seg-000001.jsonl") -> None:
    (home / "lineage" / name).write_text("".join(row + "\n" for row in rows))


def seeded(home: Path, n: int = 3, **kwargs: int):  # type: ignore[no-untyped-def]
    reg = make_registry(home, **kwargs)
    cred = adapters(reg)["process"]
    reg.append_edges(cred, [root("run_a")])
    for i in range(n - 1):
        reg.append_edges(cred, [edge("run_a", f"proc_{i}_1")])
    return reg, cred


def problems(reg) -> set[str]:  # type: ignore[no-untyped-def]
    return {f.problem for f in reg.read().findings}


def test_edges_verify_and_carry_the_prd15_fields(tmp_path: Path) -> None:
    reg, _ = seeded(tmp_path)
    read = reg.read()
    assert not read.findings
    assert [e.child_run for e in read.edges] == ["run_a", "proc_0_1", "proc_1_1"]
    first = read.edges[0]
    assert first.spawn_source == "process"
    assert first.recorded_at
    assert first.chain_hash.startswith("sha256:")
    assert stat.S_IMODE((tmp_path / "lineage" / "seg-000001.jsonl").stat().st_mode) == 0o600
    key = tmp_path / "keys" / "lineage" / "process-adapter.key"
    assert stat.S_IMODE(key.stat().st_mode) == 0o600


def test_every_batch_is_checkpointed_in_the_journal(tmp_path: Path) -> None:
    reg, _ = seeded(tmp_path)
    marks = [e for e in Journal(tmp_path).entries() if e["action"] == "lineage"]
    assert marks[-1]["payload"] == {"lineage_seq": 3, "lineage_head": reg.read().head}


@pytest.mark.parametrize("drop", [1, 2])  # a middle record, then the newest one
def test_edges_append_only(tmp_path: Path, drop: int) -> None:
    reg, _ = seeded(tmp_path)
    rows = lines(tmp_path)
    del rows[drop]
    rewrite(tmp_path, rows)
    found = reg.read().findings
    assert found, "a deleted edge must be detectable"
    assert len(reg.read().edges) == 2  # the surviving edges are still used


def test_reordering_and_editing_are_detected(tmp_path: Path) -> None:
    reg, _ = seeded(tmp_path)
    rows = lines(tmp_path)
    rewrite(tmp_path, [rows[0], rows[2], rows[1]])
    assert "chain_broken" in problems(reg)
    record = json.loads(rows[1])
    record["data"]["parent_run"] = "run_other"
    rewrite(tmp_path, [rows[0], json.dumps(record), rows[2]])
    assert "forged_record" in problems(reg)


def test_unparsable_and_unterminated_records_are_findings(tmp_path: Path) -> None:
    reg, cred = seeded(tmp_path)
    rows = lines(tmp_path)
    rewrite(tmp_path, [rows[0], "{nope", rows[2]])
    assert "unreadable_record" in problems(reg)
    (tmp_path / "lineage" / "seg-000001.jsonl").write_text(rows[0] + "\n" + rows[1])
    with pytest.raises(LineageError):
        reg.append_edges(cred, [edge("run_a", "proc_9_1")])


def test_removing_the_whole_registry_is_detected(tmp_path: Path) -> None:
    reg, _ = seeded(tmp_path)
    (tmp_path / "lineage" / "seg-000001.jsonl").unlink()
    assert "records_missing" in problems(reg)


def test_rotation_is_not_tampering_and_a_deleted_segment_is(tmp_path: Path) -> None:
    reg, _ = seeded(tmp_path, n=5, segment_max_entries=2)
    assert len(list((tmp_path / "lineage").glob("seg-*.jsonl"))) > 1
    assert not reg.read().findings
    assert len(reg.read().edges) == 5
    (tmp_path / "lineage" / "seg-000001.jsonl").unlink()
    assert "segment_missing" in problems(reg)


def test_a_rewritten_prior_segment_fails_its_anchor(tmp_path: Path) -> None:
    reg, _ = seeded(tmp_path, n=5, segment_max_entries=2)
    rows = lines(tmp_path)
    rewrite(tmp_path, rows[:1])
    assert "anchor_mismatch" in problems(reg)


def test_forged_edge_rejected(tmp_path: Path) -> None:
    reg, cred = seeded(tmp_path)
    impostor = AdapterCredential(name=cred.name, source=cred.source, key=b"x" * 32)
    with pytest.raises(ForgedEdgeError):
        reg.append_edges(impostor, [edge("run_a", "proc_evil_1")])
    assert len(reg.read().edges) == 3
    journaled = [e["payload"].get("finding") for e in Journal(tmp_path).entries()]
    assert "forged_edge_refused" in journaled


def test_an_unregistered_adapter_is_refused(tmp_path: Path) -> None:
    reg, _ = seeded(tmp_path)
    with pytest.raises(ForgedEdgeError):
        reg.append_edges(AdapterCredential("ghost", "process", b"k" * 32), [root("run_g")])


def test_a_hand_appended_edge_is_never_used(tmp_path: Path) -> None:
    reg, _ = seeded(tmp_path)
    record = json.loads(lines(tmp_path)[-1])
    record["seq"] += 1
    record["data"]["child_run"] = "run_victim"
    rewrite(tmp_path, [*lines(tmp_path), json.dumps(record)])
    assert "run_victim" not in [e.child_run for e in reg.read().edges]
    assert "forged_record" in problems(reg)


def test_an_adapter_cannot_change_its_source(tmp_path: Path) -> None:
    reg = make_registry(tmp_path)
    reg.register_adapter("a", "hook")
    assert reg.register_adapter("a", "hook").source == "hook"
    with pytest.raises(LineageError):
        reg.register_adapter("a", "process")


@pytest.mark.parametrize(
    "bad",
    [
        {"parent_run": "../x", "child_run": "run_b"},
        {"parent_run": "run_a", "child_run": ""},
        {"parent_run": "run_a", "child_run": "run_a"},
    ],
)
def test_invalid_edges_are_refused(tmp_path: Path, bad: dict[str, str]) -> None:
    reg, cred = seeded(tmp_path)
    with pytest.raises(LineageError):
        reg.append_edges(cred, [{**bad, "child": {}}])


def test_unknown_source_is_refused(tmp_path: Path) -> None:
    with pytest.raises(LineageError):
        make_registry(tmp_path).register_adapter("a", "rumour")


def test_tamper_finding_is_journaled_once_with_the_8_2_interface(tmp_path: Path) -> None:
    reg, _ = seeded(tmp_path)
    rewrite(tmp_path, lines(tmp_path)[:-1])
    first = reg.check_tamper(actor="tester")
    reg.check_tamper(actor="tester")
    assert first[0].detected_at and first[0].segment and first[0].seq
    entries = [
        e for e in Journal(tmp_path).entries() if e["payload"].get("finding") == "tamper_lineage"
    ]
    assert len(entries) == len(first)
    assert {"problem", "segment", "lineage_seq", "detail", "detected_at"} <= set(
        entries[0]["payload"]
    )


def test_re_adding_a_deleted_edge_does_not_clear_the_finding(tmp_path: Path) -> None:
    reg, cred = seeded(tmp_path)
    rewrite(tmp_path, lines(tmp_path)[:-1])
    time.sleep(0.005)  # an identical record in the same millisecond is the original, restored
    reg.append_edges(cred, [edge("run_a", "proc_1_1")])
    assert "checkpoint_mismatch" in problems(reg)


def test_a_broken_journal_is_a_finding(tmp_path: Path) -> None:
    reg, _ = seeded(tmp_path)
    (tmp_path / "journal" / "seg-000001.jsonl").write_text("garbage\n")
    assert "journal_unreadable" in problems(reg)


def test_verified_records(tmp_path: Path) -> None:
    reg, cred = seeded(tmp_path)
    reg.mark_verified(cred, "run_a")
    assert reg.read().verified == {"run_a"}


def test_an_empty_home_has_no_findings_and_nothing_is_created(tmp_path: Path) -> None:
    read = make_registry(tmp_path / "h").read()
    assert not read.edges and not read.findings
    assert not (tmp_path / "h").exists()


def test_read_honours_its_deadline(tmp_path: Path) -> None:
    reg, _ = seeded(tmp_path)
    assert reg.read(expired=lambda: True).complete is False
