"""M4: the composed stop. Credentials and gateway beside process and sandbox, and the degradation
matrix: an absent layer is ``unsupported`` (``partial-layer``), a failing one ``incomplete``, and
``complete`` only when every layer confirmed. Fake process table: nothing real is signalled."""

from __future__ import annotations

import signal
import subprocess
import sys
import time
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from agenthalt.containment import Containment
from agenthalt.coordinator import Coordinator
from agenthalt.executors import Context, ExecutorSigner, Result, confirmation, seal
from agenthalt.exit_codes import ReceiptStatus
from agenthalt.process_exec import ProcessExecutor
from agenthalt.scopes import Mode, Scope
from agenthalt.store import Store
from agenthalt.supervisor import EnrollmentError, Supervisor
from tests.lineage_helpers import adapters, edge, make_registry, proc, root
from tests.test_review_m3 import Wall, World

GRANTS = ["agentkeys:agent:bot", "static:GH_PAT@2026-12-01"]


class Layer:
    """A composed enforcement point that answers as told."""

    attestation = "self"

    def __init__(self, layer: str, answer: str = "confirmed") -> None:
        self.layer, self.answer = layer, answer
        self.calls: list[tuple[str, list[Any]]] = []
        self.released: list[Any] = []

    def _answer(self, phase: str, targets: Sequence[Any], ctx: Context) -> list[Result]:
        self.calls.append((phase, list(targets)))
        names = [getattr(t, "ref", t) for t in targets]
        if self.layer == "gateway":
            for run in names:
                ctx.record("gateway", {"halt": ctx.halt_id, "run": run})
        return [Result(n, self.answer, f"{phase} {self.answer}") for n in names]

    def disconnect(self, targets: Sequence[Any], ctx: Context) -> list[Result]:
        return self._answer("disconnect", targets, ctx)

    def revoke(self, targets: Sequence[Any], ctx: Context) -> list[Result]:
        return self._answer("revoke", targets, ctx)

    def freeze(self, targets: Sequence[Any], ctx: Context) -> list[Result]:
        return self._answer("freeze", targets, ctx)

    def release(self, record: Sequence[Any], ctx: Context) -> list[Result]:
        self.released.extend(record)
        return [Result(str(i["run"]), "confirmed", "reconnected") for i in record]


def seed(home: Path, grants: Sequence[str] = ("agentkeys:agent:bot",)) -> None:
    reg = make_registry(home)
    cred = adapters(reg)["process"]
    meta: dict[str, Any] = {"pid": 10, "start": "100", "uid": 501, "containment": "observed"}
    if grants:
        meta["grants"] = list(grants)
    reg.append_edges(cred, [root("run_a", **meta)])
    reg.append_edges(cred, [edge("run_a", "proc_11_110", pid=11, start="110", uid=501)])


def build(home: Path, **layers: Any) -> tuple[Coordinator, World]:
    table = World(proc(10, 1), proc(11, 10))
    found: dict[str, Any] = {"process": ProcessExecutor(table, kill=table.kill)}
    found.update({k: v for k, v in layers.items() if v is not None})
    containment = Containment(
        make_registry(home), table, found, signer=ExecutorSigner(home), invoking_uid=501
    )
    store = Store(home)
    store.ensure()
    return Coordinator(store, containment), table


def halt(c: Coordinator, mode: Mode) -> Any:
    return c.raise_halt(Scope.parse("agent:bot"), mode, actor="op", reason="r")


def full(**overrides: Any) -> dict[str, Any]:
    layers: dict[str, Any] = {
        "sandbox": Wall(),
        "credentials": Layer("credentials"),
        "gateway": Layer("gateway"),
    }
    layers.update(overrides)
    return layers


def test_every_layer_confirmed_is_complete(tmp_path: Path) -> None:
    seed(tmp_path)
    layers = full()
    c, table = build(tmp_path, **layers)
    result = halt(c, Mode.KILL)
    assert result.outcome is ReceiptStatus.COMPLETE, result.layers
    assert set(result.layers.values()) == {"enforced", "confirmed"}
    assert layers["credentials"].calls == [("revoke", [layers["credentials"].calls[0][1][0]])]
    assert layers["credentials"].calls[0][1][0].ref == "agentkeys:agent:bot"
    assert layers["gateway"].calls == [("disconnect", ["run_a"])]
    assert not table.procs
    signer = ExecutorSigner(tmp_path)
    assert all(signer.verify(result.halt.halt_id, item) for item in result.cut.confirmations)


@pytest.mark.parametrize("layer", ["sandbox", "credentials", "gateway"])
def test_an_absent_layer_is_partial_layer_never_a_silent_skip(tmp_path: Path, layer: str) -> None:
    seed(tmp_path)
    result = halt(build(tmp_path, **full(**{layer: None}))[0], Mode.KILL)
    assert result.layers[layer] == "unsupported"
    assert result.outcome is ReceiptStatus.PARTIAL_LAYER


@pytest.mark.parametrize("layer", ["credentials", "gateway"])
@pytest.mark.parametrize("answer", ["failed", "requested"])
def test_a_layer_that_does_not_confirm_is_incomplete(
    tmp_path: Path, layer: str, answer: str
) -> None:
    seed(tmp_path)
    result = halt(build(tmp_path, **full(**{layer: Layer(layer, answer)}))[0], Mode.KILL)
    assert result.layers[layer] == answer and result.outcome is ReceiptStatus.INCOMPLETE


def test_pause_leaves_credentials_alone_but_disconnects(tmp_path: Path) -> None:
    seed(tmp_path)
    layers = full()
    result = halt(build(tmp_path, **layers)[0], Mode.PAUSE)
    assert layers["credentials"].calls == [] and "credentials" not in result.layers
    assert layers["gateway"].calls == [("disconnect", ["run_a"])]
    assert result.outcome is ReceiptStatus.COMPLETE


def test_quarantine_freezes_issuance(tmp_path: Path) -> None:
    seed(tmp_path)
    layers = full()
    halt(build(tmp_path, **layers)[0], Mode.QUARANTINE)
    assert [phase for phase, _ in layers["credentials"].calls] == ["freeze"]


def test_no_declared_credentials_is_not_a_clean_bill(tmp_path: Path) -> None:
    seed(tmp_path, grants=())
    result = halt(build(tmp_path, **full())[0], Mode.KILL)
    assert result.layers["credentials"] == "unsupported"
    assert result.outcome is ReceiptStatus.PARTIAL_LAYER
    note = next(c.note for c in result.cut.confirmations if c.layer == "credentials")
    assert "--grant" in note


def test_unrevocable_keys_are_listed_with_their_window(tmp_path: Path) -> None:
    seed(tmp_path, grants=GRANTS)
    from agenthalt.credentials import AgentkeysExecutor

    result = halt(build(tmp_path, **full(credentials=AgentkeysExecutor("")))[0], Mode.KILL)
    assert result.cut.unrevocable == [
        {"ref": "static:GH_PAT", "expires": "2026-12-01", "window_note": "usable until 2026-12-01"}
    ]
    assert result.layers["credentials"] == "unsupported"
    assert result.cut.to_dict()["unrevocable_grants"] == result.cut.unrevocable


def test_no_credential_executor_is_reported_per_grant(tmp_path: Path) -> None:
    seed(tmp_path, grants=GRANTS)
    layers = full()
    del layers["credentials"]
    result = halt(build(tmp_path, **layers)[0], Mode.KILL)
    targets = sorted(c.target for c in result.cut.confirmations if c.layer == "credentials")
    assert targets == sorted(GRANTS) and result.layers["credentials"] == "unsupported"


def test_lift_reconnects_the_gateway(tmp_path: Path) -> None:
    seed(tmp_path)
    layers = full()
    c, _ = build(tmp_path, **layers)
    result = halt(c, Mode.PAUSE)
    released = c.lift(result.halt.halt_id, actor="op", reason="r").released
    assert layers["gateway"].released == [{"halt": result.halt.halt_id, "run": "run_a"}]
    assert "reconnected" in [r.note for r in released]


def test_a_scope_with_no_process_reports_every_layer(tmp_path: Path) -> None:
    seed(tmp_path)
    c, _ = build(tmp_path, **full())
    result = c.raise_halt(Scope.parse("tool:deploy"), Mode.KILL, actor="op", reason="r")
    assert {result.layers[k] for k in ("gateway", "process", "credentials")} == {"unsupported"}


# the M4 review findings -------------------------------------------------------


def test_a_hung_composed_layer_does_not_delay_the_kill(tmp_path: Path) -> None:
    seed(tmp_path)
    killed_at: list[float] = []
    started = time.monotonic()

    class Hung(Layer):
        def revoke(self, targets: Sequence[Any], ctx: Context) -> list[Result]:
            time.sleep(1.5)
            return self._answer("revoke", targets, ctx)

    c, table = build(tmp_path, **full(credentials=Hung("credentials")))
    real = table.kill

    def kill(pid: int, signum: int) -> None:
        if signum == signal.SIGKILL:
            killed_at.append(time.monotonic() - started)
        real(pid, signum)

    c.containment.adapters["process"]._kill = kill  # type: ignore[union-attr]
    result = halt(c, Mode.KILL)
    assert killed_at and max(killed_at) < 1.0, killed_at
    assert result.layers["process"] == "confirmed" and "credentials" in result.layers


def test_one_bad_answer_does_not_lose_the_other_revokes() -> None:
    from agenthalt.credentials import AgentkeysExecutor, Grant

    def runner(command: Sequence[str], timeout: float, ids: Any) -> tuple[int, str]:
        if command[3] == "b":
            return 0, '{"ok": true, "data": null}'
        if command[3] == "c":
            raise UnicodeDecodeError("utf-8", b"", 0, 1, "bad")
        return 0, '{"ok": true, "data": {"revocations": [{"session_id": "s", "epoch_after": 1}]}}'

    grants = [Grant(f"agentkeys:agent:{name}", "r") for name in "abc"]
    context = Context("hlt_1", time.monotonic() + 5)
    results = AgentkeysExecutor("/x", runner=runner).revoke(grants, context)
    assert [r.status for r in results] == ["confirmed", "failed", "failed"]


def test_grants_for_an_enrolled_process_are_refused_not_dropped(tmp_path: Path) -> None:
    sleeper = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(20)"])
    try:
        supervisor = Supervisor(tmp_path, containment="pgroup")
        supervisor.attach(sleeper.pid, name="x")
        with pytest.raises(EnrollmentError, match="none were recorded"):
            supervisor.attach(sleeper.pid, grants=["static:K"])
    finally:
        sleeper.kill()
        sleeper.wait()


def test_our_own_signature_cannot_pose_as_a_third_partys(tmp_path: Path) -> None:
    signer = ExecutorSigner(tmp_path)
    made = confirmation("h", "process", "suspend", Result("a", "confirmed"), attestation="self")
    (mine,) = seal("h", [made], signer)
    assert signer.verify("h", mine)
    assert not signer.verify("h", replace(mine, attestation="third_party"))


def test_a_third_party_signs_only_under_its_own_name(tmp_path: Path) -> None:
    seed(tmp_path)

    class Impostor(Layer):
        attestation = "third_party"
        name = "agentgate"

        def disconnect(self, targets: Sequence[Any], ctx: Context) -> list[Result]:
            return [
                Result(t, "confirmed", "ok", signed_by="agentkeys", signature="s") for t in targets
            ]

    result = halt(build(tmp_path, **full(gateway=Impostor("gateway")))[0], Mode.KILL)
    assert result.layers["gateway"] == "requested"


def test_lifting_one_halt_keeps_the_gateway_cut_for_the_other(tmp_path: Path) -> None:
    seed(tmp_path)
    layers = full()
    c, _ = build(tmp_path, **layers)
    first = halt(c, Mode.PAUSE)
    second = c.raise_halt(Scope.parse("run:run_a"), Mode.PAUSE, actor="op", reason="r")
    released = c.lift(first.halt.halt_id, actor="op", reason="r").released
    assert layers["gateway"].released == []
    assert any("stays disconnected" in r.note for r in released)
    c.lift(second.halt.halt_id, actor="op", reason="r")
    undone = {(i["halt"], i["run"]) for i in layers["gateway"].released}
    assert undone == {(first.halt.halt_id, "run_a"), (second.halt.halt_id, "run_a")}


def test_a_missing_public_half_is_rebuilt(tmp_path: Path) -> None:
    signer = ExecutorSigner(tmp_path)
    signer.ensure()
    Path(f"{signer.signer.key}.pub").unlink()
    made = confirmation("h", "process", "suspend", Result("a", "confirmed"), attestation="self")
    (item,) = seal("h", [made], signer)
    assert item.status == "confirmed" and signer.verify("h", item)


def test_under_sudo_agentkeys_is_looked_for_where_the_operator_installs_it(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import os
    import pwd
    import types

    import agenthalt.credentials as credentials

    tool = tmp_path / ".local" / "bin" / "agentkeys"
    tool.parent.mkdir(parents=True)
    tool.write_text("#!/bin/sh\n")
    tool.chmod(0o755)
    entry = types.SimpleNamespace(pw_dir=str(tmp_path), pw_gid=20, pw_name="op")
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    monkeypatch.setattr(os, "getuid", lambda: 0)
    monkeypatch.setattr(os, "geteuid", lambda: 0)
    monkeypatch.setattr(pwd, "getpwuid", lambda uid: entry)
    monkeypatch.setattr(os, "getgrouplist", lambda name, gid: [gid])
    assert credentials._find(501) == str(tool)
    ids = credentials._as_user(501)
    assert (ids["user"], ids["extra_groups"], ids["env"]["HOME"]) == (501, [20], str(tmp_path))
    assert credentials._as_user(0) == {}
