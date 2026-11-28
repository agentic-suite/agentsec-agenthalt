"""4.6: Ed25519 confirmation signatures, published keys, rotation, the HMAC fallback."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from agenthalt import signing
from agenthalt.executors import ExecutorSigner, Result, confirmation, seal
from agenthalt.signing import NAMESPACE, Signer, TrustStore, enforcement_payload

needs_ssh = pytest.mark.skipif(shutil.which("ssh-keygen") is None, reason="needs ssh-keygen")


@needs_ssh
def test_the_executor_key_is_private_and_its_public_half_published(tmp_path: Path) -> None:
    signer = Signer(tmp_path)
    signed_by, signature = signer.sign(b"payload") or ("", "")
    assert signed_by == "agenthalt-executor" and "SSH SIGNATURE" in signature
    assert signer.key.stat().st_mode & 0o777 == 0o600
    assert TrustStore(tmp_path).keys("agenthalt-executor")
    assert signer.verify(signed_by, b"payload", signature)
    assert not signer.verify(signed_by, b"other", signature)
    assert not signer.verify("someone-else", b"payload", signature)


@needs_ssh
def test_a_rotated_key_still_verifies_old_confirmations(tmp_path: Path) -> None:
    signer = Signer(tmp_path)
    old = signer.sign(b"before")
    signer.key.unlink()
    Path(f"{signer.key}.pub").unlink()
    new = signer.sign(b"after")
    assert old and new and old[1] != new[1]
    assert len(TrustStore(tmp_path).keys("agenthalt-executor")) == 2
    assert signer.verify(*old[:1], b"before", old[1]) and signer.verify(*new[:1], b"after", new[1])


@needs_ssh
def test_a_third_party_confirmation_verifies_only_against_its_published_key(
    tmp_path: Path,
) -> None:
    key = tmp_path / "seatbelt"
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)], check=True)
    payload = enforcement_payload("hlt_1", "sandbox", "block", "run_a", "confirmed")
    signature = subprocess.run(
        ["ssh-keygen", "-Y", "sign", "-f", str(key), "-n", NAMESPACE],
        input=payload,
        capture_output=True,
        check=True,
    ).stdout.decode()
    item = confirmation(
        "hlt_1",
        "sandbox",
        "block",
        Result("run_a", "confirmed", signed_by="agentseatbelt", signature=signature),
        attestation="third_party",
    )
    home = tmp_path / "h"
    (unknown,) = seal("hlt_1", [item], ExecutorSigner(home))
    assert unknown.status == "requested", "its key is not published"
    published = home / "keys" / "published"
    published.mkdir(parents=True)
    (published / "agentseatbelt.pub").write_text(Path(f"{key}.pub").read_text())
    (trusted,) = seal("hlt_1", [item], ExecutorSigner(home))
    assert trusted.status == "confirmed" and trusted.signed_by == "agentseatbelt"
    assert ExecutorSigner(home).verify("hlt_1", trusted)
    (lying,) = seal(
        "hlt_1",
        [
            confirmation(
                "hlt_1",
                "sandbox",
                "block",
                Result("run_b", "confirmed", signed_by="agentseatbelt", signature=signature),
                attestation="third_party",
            )
        ],
        ExecutorSigner(home),
    )
    assert lying.status == "requested", "a signature for another target"


def test_without_ssh_keygen_it_falls_back_to_hmac(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(signing, "_ssh_keygen", lambda: None)
    signer = Signer(tmp_path)
    found = signer.sign(b"x")
    assert found is not None and found[0] == "agenthalt-executor-hmac"
    assert signer.verify(found[0], b"x", found[1])
    assert not signer.verify(found[0], b"y", found[1])
    assert not Signer(tmp_path / "other").verify(found[0], b"x", found[1])
    assert signer.sign_many([]) == []


def test_signing_that_cannot_happen_returns_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "keys").write_text("not a directory")
    assert Signer(tmp_path).sign(b"x") is None
    assert TrustStore(tmp_path).keys("../etc") == []
