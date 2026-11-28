"""3.1 / 3.5: the adapter contract, the registry and signed confirmations."""

from __future__ import annotations

import time
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from agenthalt.config import ConfigError
from agenthalt.executors import (
    Context,
    ExecutorSigner,
    Result,
    confirmation,
    load_adapters,
    run_phase,
)


class Good:
    name = "good"
    layer = "process"
    version = "1"
    attestation = "self"

    def suspend(self, targets: Any, ctx: Any) -> list[Result]:
        return [Result(t, "confirmed") for t in targets]

    def release(self, record: Any, ctx: Any) -> list[Result]:
        return []


class Point:
    def __init__(self, name: str, factory: Any) -> None:
        self.name, self.factory = name, factory

    def load(self) -> Any:
        return self.factory


def ctx() -> Context:
    return Context("hlt_1", time.monotonic() + 5)


def load(**kwargs: Any) -> dict[str, Any]:
    kwargs.setdefault("entry_points", lambda: ())
    return load_adapters({"good": Good}, **kwargs)


def test_builtins_load_by_layer() -> None:
    assert load()["process"].name == "good"
    assert load_adapters({}) == {}  # the real entry-point group is empty here


def test_unknown_adapter_is_a_config_error() -> None:
    with pytest.raises(ConfigError, match="unknown adapter"):
        load(names=["nope"])


@pytest.mark.parametrize(
    ("attribute", "value"),
    [
        ("name", "other"),
        ("layer", "hooks"),
        ("version", 2),
        ("attestation", "trusted"),
        ("suspend", None),
        ("release", None),
    ],
)
def test_a_bad_adapter_fails_at_load(attribute: str, value: Any) -> None:
    bad = type("Bad", (Good,), {attribute: value})
    with pytest.raises(ConfigError, match="bad executor adapter"):
        load_adapters({"good": bad}, entry_points=lambda: ())


def test_an_adapter_that_raises_on_load_is_a_config_error() -> None:
    def boom() -> None:
        raise RuntimeError("no")

    with pytest.raises(ConfigError, match="failed to load"):
        load(entry_points=lambda: [Point("broken", boom)])


def test_a_registered_adapter_replaces_the_builtin_of_its_layer() -> None:
    other = type("Other", (Good,), {"name": "composed"})
    assert load(entry_points=lambda: [Point("composed", other)])["process"].name == "composed"


def test_results_are_held_to_the_contract() -> None:
    class Sloppy(Good):
        def suspend(self, targets: Any, ctx: Any) -> list[Result]:
            return [Result("a", "probably"), Result("zz", "confirmed"), Result("yy", "failed", "x")]

    results = {r.target: r.status for r in run_phase(Sloppy(), "suspend", [], ["a", "b"], ctx())}
    assert results == {"a": "failed", "b": "requested", "yy": "failed"}


@pytest.mark.parametrize("returned", [["nonsense"], None])
def test_a_broken_adapter_yields_failed(returned: Any) -> None:
    class Broken(Good):
        def suspend(self, targets: Any, ctx: Any) -> Any:
            return returned

    assert [r.status for r in run_phase(Broken(), "suspend", [], ["a"], ctx())] == ["failed"]


def test_confirmed_is_signed_and_verifiable(tmp_path: Path) -> None:
    signer = ExecutorSigner(tmp_path)
    item = confirmation(
        "hlt_1", "process", "suspend", Result("a", "confirmed"), attestation="self", signer=signer
    )
    assert item.status == "confirmed" and item.signed_by == "agenthalt-executor"
    assert signer.path.stat().st_mode & 0o777 == 0o600
    assert signer.verify("hlt_1", item)
    assert not signer.verify("hlt_2", item)
    assert not signer.verify("hlt_1", replace(item, target="b"))
    assert not signer.verify("hlt_1", replace(item, signature=None))
    assert not ExecutorSigner(tmp_path / "elsewhere").verify("hlt_1", item)


@pytest.mark.parametrize("signer", [None, "unreadable"])
def test_no_signature_means_not_confirmed(tmp_path: Path, signer: str | None) -> None:
    hook = None
    if signer:
        hook = ExecutorSigner(tmp_path)
        hook.path.parent.mkdir()
        hook.path.write_text("abcd")  # too short
    done = confirmation(
        "hlt_1", "process", "suspend", Result("a", "confirmed"), attestation="self", signer=hook
    )
    assert done.status == "requested" and "unsigned" in done.note and done.signature is None
    failed = confirmation(
        "hlt_1", "process", "suspend", Result("a", "failed"), attestation="self", signer=hook
    )
    assert failed.status == "failed"


def test_third_party_must_bring_its_own_signature(tmp_path: Path) -> None:
    signer = ExecutorSigner(tmp_path)
    unsigned = confirmation(
        "h", "sandbox", "block", Result("a", "confirmed"), attestation="third_party", signer=signer
    )
    assert unsigned.status == "requested"
    signed = confirmation(
        "h",
        "sandbox",
        "block",
        Result("a", "confirmed", signed_by="agentseatbelt", signature="s"),
        attestation="third_party",
        signer=signer,
    )
    assert signed.status == "confirmed" and signed.signed_by == "agentseatbelt"
