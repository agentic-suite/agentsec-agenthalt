"""0.4 Halt journal (#403): append-only, hash-chained, rotation-anchored (R12)."""

from __future__ import annotations

import json
import multiprocessing
import stat
from pathlib import Path

import pytest

from agenthalt.cli import main
from agenthalt.journal import ACTIONS, GENESIS, Journal, JournalError, canonical_hash


def journal(tmp_path: Path, max_entries: int = 10_000) -> Journal:
    return Journal(tmp_path / ".agenthalt", segment_max_entries=max_entries)


def fill(j: Journal, n: int) -> None:
    for i in range(n):
        j.append(
            "raise",
            actor="maya",
            halt_id=f"hlt_{i}",
            scope="agent:bot",
            mode="kill",
            reason=f"r{i}",
        )


def lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


def segment(j: Journal, n: int) -> Path:
    return j.dir / f"seg-{n:06d}.jsonl"


def test_empty_journal_verifies(tmp_path: Path) -> None:
    result = journal(tmp_path).verify()
    assert result.ok
    assert result.entries == 0
    assert result.head == GENESIS


def test_append_returns_chained_entries(tmp_path: Path) -> None:
    j = journal(tmp_path)
    first = j.append(
        "raise", actor="maya", halt_id="hlt_1", scope="agent:bot", mode="kill", reason="prod"
    )
    second = j.append("complete", actor="haltd", halt_id="hlt_1", payload={"status": "failed"})
    assert first["schema"] == "agenthalt.journal.v1"
    assert first["seq"] == 1 and second["seq"] == 2
    assert first["prev_hash"] == GENESIS
    assert second["prev_hash"] == first["entry_hash"]
    assert first["entry_hash"] == canonical_hash(
        {k: v for k, v in first.items() if k != "entry_hash"}
    )
    assert first["timestamp"].endswith("Z")
    assert j.head() == second["entry_hash"]
    result = j.verify()
    assert result.ok and result.entries == 2 and result.head == second["entry_hash"]


def test_entry_fields(tmp_path: Path) -> None:
    entry = journal(tmp_path).append("finding", actor="haltd")
    assert set(entry) == {
        "schema",
        "seq",
        "timestamp",
        "action",
        "halt_id",
        "actor",
        "scope",
        "mode",
        "reason",
        "payload",
        "prev_hash",
        "entry_hash",
    }
    assert entry["halt_id"] is None and entry["payload"] == {}


def test_actions_vocabulary() -> None:
    assert (
        frozenset(
            {
                "raise",
                "execute",
                "complete",
                "lift",
                "resume",
                "escalate",
                "trigger_rejected",
                "finding",
                "anchor",
            }
        )
        == ACTIONS
    )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"action": "explode", "actor": "maya"},
        {"action": "anchor", "actor": "maya"},  # anchors are written by rotation only
        {"action": "raise", "actor": ""},
        {"action": "raise", "actor": "maya", "halt_id": "../x"},
        {"action": "raise", "actor": "maya", "mode": "nuke"},
    ],
)
def test_invalid_entries_are_refused(tmp_path: Path, kwargs: dict[str, str]) -> None:
    j = journal(tmp_path)
    with pytest.raises(JournalError):
        j.append(**kwargs)  # type: ignore[arg-type]
    assert j.verify().entries == 0


def test_reason_and_payload_are_redacted(tmp_path: Path) -> None:
    canary = "AKIAIOSFODNN7EXAMPLE"
    j = journal(tmp_path)
    entry = j.append(
        "raise",
        actor="maya",
        reason=f"leaked key {canary}",
        payload={"note": f"token=sk-live-{'a' * 24}", "nested": [f"Bearer {'b' * 30}"]},
    )
    raw = segment(j, 1).read_text(encoding="utf-8")
    assert canary not in raw and "sk-live" not in raw and "b" * 30 not in raw
    assert "secret:aws_access_key[redacted]" in entry["reason"]
    assert j.verify().ok


def test_permissions(tmp_path: Path) -> None:
    j = journal(tmp_path)
    fill(j, 1)
    assert stat.S_IMODE(j.dir.stat().st_mode) == 0o700
    assert stat.S_IMODE(j.home.stat().st_mode) == 0o700
    assert stat.S_IMODE(segment(j, 1).stat().st_mode) == 0o600


def test_rotation_keeps_the_chain(tmp_path: Path) -> None:
    j = journal(tmp_path, max_entries=3)
    fill(j, 7)
    # seg1: 3 entries; seg2: anchor + 2; seg3: anchor + 2 ... seq is global
    segs = sorted(j.dir.glob("seg-*.jsonl"))
    assert len(segs) == 3
    first_of_2 = json.loads(lines(segs[1])[0])
    last_of_1 = json.loads(lines(segs[0])[-1])
    assert first_of_2["action"] == "anchor"
    assert first_of_2["prev_hash"] == last_of_1["entry_hash"]
    assert first_of_2["payload"]["prior_segment"] == "seg-000001.jsonl"
    assert first_of_2["payload"]["prior_head"] == last_of_1["entry_hash"]
    assert first_of_2["payload"]["prior_entries"] == 3
    result = j.verify()
    assert result.ok
    assert result.entries == 9  # 7 entries + 2 anchors
    assert [e["seq"] for e in j.entries()] == list(range(1, 10))


def test_entries_filter_by_halt(tmp_path: Path) -> None:
    j = journal(tmp_path, max_entries=2)
    fill(j, 4)
    assert [e["halt_id"] for e in j.entries(halt_id="hlt_2")] == ["hlt_2"]


def _edit(path: Path, index: int, field: str, value: object) -> None:
    rows = lines(path)
    entry = json.loads(rows[index])
    entry[field] = value
    rows[index] = json.dumps(entry)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def test_seeded_edit_is_detected(tmp_path: Path) -> None:
    j = journal(tmp_path)
    fill(j, 5)
    _edit(segment(j, 1), 2, "reason", "nothing to see")
    result = j.verify()
    assert not result.ok
    assert result.segment == "seg-000001.jsonl" and result.line == 3
    assert "entry_hash" in (result.error or "")


def test_rehashed_edit_breaks_the_next_link(tmp_path: Path) -> None:
    j = journal(tmp_path)
    fill(j, 5)
    path = segment(j, 1)
    rows = lines(path)
    entry = json.loads(rows[1])
    entry["reason"] = "rewritten"
    entry["entry_hash"] = canonical_hash({k: v for k, v in entry.items() if k != "entry_hash"})
    rows[1] = json.dumps(entry)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    result = j.verify()
    assert not result.ok and result.line == 3
    assert "prev_hash" in (result.error or "")


def test_reorder_is_detected(tmp_path: Path) -> None:
    j = journal(tmp_path)
    fill(j, 4)
    path = segment(j, 1)
    rows = lines(path)
    rows[1], rows[2] = rows[2], rows[1]
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    assert not j.verify().ok


def test_deleted_line_is_detected(tmp_path: Path) -> None:
    j = journal(tmp_path)
    fill(j, 4)
    path = segment(j, 1)
    rows = lines(path)
    del rows[1]
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    result = j.verify()
    assert not result.ok and "seq" in (result.error or "")


def test_deleted_middle_segment_is_detected(tmp_path: Path) -> None:
    j = journal(tmp_path, max_entries=2)
    fill(j, 6)
    segment(j, 2).unlink()
    result = j.verify()
    assert not result.ok and "missing segment" in (result.error or "")


def test_edited_prior_segment_breaks_the_anchor(tmp_path: Path) -> None:
    j = journal(tmp_path, max_entries=3)
    fill(j, 5)
    path = segment(j, 1)
    rows = lines(path)
    rows[0] = json.dumps(
        json.loads(rows[0]), indent=None
    )  # same entry, different bytes: hashes still match
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    assert j._check_line(rows[0], 0, GENESIS, 1, None) is None  # the entry alone still verifies
    result = j.verify()
    assert not result.ok
    assert result.segment == "seg-000002.jsonl" and "prior_file_sha256" in (result.error or "")


def test_truncated_last_line_is_detected(tmp_path: Path) -> None:
    j = journal(tmp_path)
    fill(j, 2)
    path = segment(j, 1)
    path.write_text(path.read_text(encoding="utf-8")[:-20], encoding="utf-8")
    result = j.verify()
    assert not result.ok and "parse" in (result.error or "")


def test_append_refuses_a_broken_chain(tmp_path: Path) -> None:
    j = journal(tmp_path)
    fill(j, 2)
    path = segment(j, 1)
    path.write_text(path.read_text(encoding="utf-8")[:-20], encoding="utf-8")
    with pytest.raises(JournalError):
        fill(j, 1)


def test_unknown_schema_is_detected(tmp_path: Path) -> None:
    j = journal(tmp_path)
    fill(j, 1)
    _edit(segment(j, 1), 0, "schema", "agenthalt.journal.v9")
    result = j.verify()
    assert not result.ok and "schema" in (result.error or "")


def _worker(home: str, n: int) -> None:
    j = Journal(Path(home), segment_max_entries=7)
    for i in range(n):
        j.append("finding", actor=f"w{i}")


def test_concurrent_writers_never_fork_the_chain(tmp_path: Path) -> None:
    home = tmp_path / ".agenthalt"
    ctx = multiprocessing.get_context("spawn")
    procs = [ctx.Process(target=_worker, args=(str(home), 15)) for _ in range(4)]
    for p in procs:
        p.start()
    for p in procs:
        p.join(60)
        assert p.exitcode == 0
    j = Journal(home, segment_max_entries=7)
    result = j.verify()
    assert result.ok
    assert sum(1 for e in j.entries() if e["action"] == "finding") == 60


# --- CLI ----------------------------------------------------------------------------------


def test_cli_journal_verify_and_show(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    j = Journal(tmp_path / ".agenthalt")
    fill(j, 3)
    assert main(["journal", "verify"]) == 0
    out = capsys.readouterr().out
    assert "intact" in out and "3 entries" in out and j.head() in out

    assert main(["journal", "show", "--halt", "hlt_1"]) == 0
    out = capsys.readouterr().out
    assert "hlt_1" in out and "hlt_2" not in out

    assert main(["journal", "show", "--json"]) == 0
    rows = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert [r["seq"] for r in rows] == [1, 2, 3]


def test_cli_journal_verify_broken_exits_1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    j = Journal(tmp_path / ".agenthalt")
    fill(j, 3)
    _edit(segment(j, 1), 1, "actor", "mallory")
    assert main(["journal", "verify"]) == 1
    err = capsys.readouterr().err
    assert "seg-000001.jsonl" in err and "line 2" in err


def test_cli_journal_show_broken_still_exits_1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    j = Journal(tmp_path / ".agenthalt")
    fill(j, 1)
    path = segment(j, 1)
    path.write_text("not json\n", encoding="utf-8")
    assert main(["journal", "show"]) == 1


# --- the remaining tamper paths (0.C: no untested path) -----------------------------------


def _forge(j: Journal, seg: int, **overrides: object) -> None:
    """Append a correctly hashed, correctly linked entry with chosen fields."""
    path = segment(j, seg)
    last = json.loads(lines(path)[-1])
    body = {k: v for k, v in last.items() if k != "entry_hash"}
    body.update(seq=last["seq"] + 1, prev_hash=last["entry_hash"], **overrides)
    body["entry_hash"] = canonical_hash(body)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(body) + "\n")


def test_segment_max_entries_floor(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        Journal(tmp_path, segment_max_entries=1)


def test_head_on_a_broken_chain_raises(tmp_path: Path) -> None:
    j = journal(tmp_path)
    fill(j, 2)
    _edit(segment(j, 1), 0, "actor", "mallory")
    with pytest.raises(JournalError):
        j.head()


def test_non_object_line(tmp_path: Path) -> None:
    j = journal(tmp_path)
    fill(j, 1)
    with segment(j, 1).open("a", encoding="utf-8") as handle:
        handle.write("[1, 2]\n")
    result = j.verify()
    assert not result.ok and "not an object" in (result.error or "")
    with pytest.raises(JournalError, match="not an object"):
        list(j.entries())


def test_extra_field_is_detected(tmp_path: Path) -> None:
    j = journal(tmp_path)
    fill(j, 1)
    _forge(j, 1, injected="x")
    result = j.verify()
    assert not result.ok and "unexpected fields" in (result.error or "")


def test_forged_anchor_mid_segment_is_detected(tmp_path: Path) -> None:
    j = journal(tmp_path)
    fill(j, 2)
    _forge(j, 1, action="anchor")
    result = j.verify()
    assert not result.ok and "outside a segment boundary" in (result.error or "")


def test_segment_without_opening_anchor_is_detected(tmp_path: Path) -> None:
    j = journal(tmp_path, max_entries=2)
    fill(j, 3)  # seg2 = anchor + 1 entry
    path = segment(j, 2)
    rows = lines(path)
    anchor = json.loads(rows[0])
    anchor["action"] = "finding"  # demote the anchor, keep the hash valid
    body = {k: v for k, v in anchor.items() if k != "entry_hash"}
    anchor["entry_hash"] = canonical_hash(body)
    following = json.loads(rows[1])
    following["prev_hash"] = anchor["entry_hash"]
    following["entry_hash"] = canonical_hash(
        {k: v for k, v in following.items() if k != "entry_hash"}
    )
    path.write_text(json.dumps(anchor) + "\n" + json.dumps(following) + "\n", encoding="utf-8")
    result = j.verify()
    assert not result.ok and "does not open with a rotation anchor" in (result.error or "")


def test_empty_segment_is_detected(tmp_path: Path) -> None:
    j = journal(tmp_path)
    fill(j, 1)
    segment(j, 2).write_text("", encoding="utf-8")
    result = j.verify()
    assert not result.ok and "empty segment" in (result.error or "")


def test_append_cost_does_not_grow_with_history(tmp_path: Path) -> None:
    # PRD 39: trigger auth + journal write <= 50 ms. append() must not re-walk the whole history.
    import time

    j = journal(tmp_path)
    fill(j, 5000)
    start = time.perf_counter()
    for _ in range(20):
        j.append("finding", actor="perf")
    per_append_ms = (time.perf_counter() - start) * 1000 / 20
    assert per_append_ms < 50, per_append_ms
    assert j.verify().ok


def test_append_refuses_a_tampered_tail(tmp_path: Path) -> None:
    j = journal(tmp_path)
    fill(j, 3)
    _edit(segment(j, 1), 2, "reason", "rewritten")
    with pytest.raises(JournalError, match="does not verify"):
        j.append("finding", actor="t")


def test_append_refuses_a_segment_gap(tmp_path: Path) -> None:
    j = journal(tmp_path, max_entries=2)
    fill(j, 5)
    segment(j, 1).unlink()
    with pytest.raises(JournalError, match="gap"):
        j.append("finding", actor="t")


def test_append_refuses_an_empty_segment(tmp_path: Path) -> None:
    j = journal(tmp_path)
    fill(j, 1)
    segment(j, 2).write_text("", encoding="utf-8")
    with pytest.raises(JournalError, match="empty or unterminated"):
        j.append("finding", actor="t")


def test_append_refuses_a_non_object_tail(tmp_path: Path) -> None:
    j = journal(tmp_path)
    fill(j, 1)
    with segment(j, 1).open("a", encoding="utf-8") as handle:
        handle.write("[1]\n")
    with pytest.raises(JournalError, match="non-object"):
        j.append("finding", actor="t")


def test_append_refuses_an_unparsable_tail(tmp_path: Path) -> None:
    j = journal(tmp_path)
    fill(j, 1)
    with segment(j, 1).open("a", encoding="utf-8") as handle:
        handle.write("{not json\n")
    with pytest.raises(JournalError, match="unparsable"):
        j.append("finding", actor="t")


def test_last_line_of_a_single_long_line(tmp_path: Path) -> None:
    from agenthalt.journal import _last_line

    path = tmp_path / "one.jsonl"
    path.write_text("x" * 10_000 + "\n", encoding="utf-8")
    assert _last_line(path, chunk=512) == "x" * 10_000


def test_non_utf8_segment_is_reported_not_raised(tmp_path: Path) -> None:
    j = journal(tmp_path)
    fill(j, 1)
    segment(j, 1).write_bytes(b"\xff\xfe garbage\n")
    result = j.verify()  # must not raise
    assert not result.ok and "UTF-8" in (result.error or "")


def test_unreadable_segment_is_reported_not_raised(tmp_path: Path) -> None:
    import os

    j = journal(tmp_path)
    fill(j, 1)
    os.chmod(segment(j, 1), 0o000)
    try:
        result = j.verify()
        if os.geteuid() != 0:
            assert not result.ok and "unreadable" in (result.error or "")
    finally:
        os.chmod(segment(j, 1), 0o600)


def test_unlistable_journal_directory_is_reported_not_raised(tmp_path: Path) -> None:
    import os

    j = journal(tmp_path)
    fill(j, 1)
    os.chmod(j.dir, 0o000)
    try:
        result = j.verify()
        if os.geteuid() != 0:
            assert not result.ok and "directory unreadable" in (result.error or "")
    finally:
        os.chmod(j.dir, 0o700)
