"""Confirmation signing (M4 design §5, DD-40, DD-54): who vouches for each cut.

Signatures are Ed25519 in OpenSSH's SSHSIG format, made and checked with ``ssh-keygen`` so that the
runtime stays free of dependencies. A verifier needs only the public key.

* agenthalt's own executors sign with a separate executor key; those confirmations say
  ``attestation: self``. It proves who wrote the line, not that the writer was honest.
* A third-party enforcement point signs with its own key. Its public key, published under
  ``<home>/keys/published/``, is what makes its ``confirmed`` count.
"""

from __future__ import annotations

import contextlib
import hashlib
import hmac
import json
import os
import secrets
import shutil
import subprocess
import tempfile
from pathlib import Path

from agenthalt.ids import validate_id
from agenthalt.logs import get_logger

__all__ = ["NAMESPACE", "OWN_SIGNERS", "Signer", "TrustStore", "enforcement_payload"]

NAMESPACE = "agenthalt-confirmation"
SELF = "agenthalt-executor"
SELF_HMAC = "agenthalt-executor-hmac"
OWN_SIGNERS = (SELF, SELF_HMAC)
_log = get_logger("signing")


def enforcement_payload(halt_id: str, layer: str, phase: str, target: str, status: str) -> bytes:
    """What an enforcement point signs: only what it knows itself."""
    body = {"halt_id": halt_id, "layer": layer, "phase": phase, "target": target, "status": status}
    return json.dumps(body, sort_keys=True, separators=(",", ":")).encode()


def _ssh_keygen() -> str | None:
    return shutil.which("ssh-keygen")


def _run(arguments: list[str], data: bytes) -> bytes:
    tool = _ssh_keygen()
    if tool is None:
        raise OSError("ssh-keygen not found")
    done = subprocess.run(  # noqa: S603 - resolved binary, arguments are ours
        [tool, *arguments], input=data, capture_output=True, timeout=10, check=True
    )
    return done.stdout


def _verify(public_key: str, signer: str, payload: bytes, signature: str) -> bool:
    with tempfile.TemporaryDirectory() as tmp:
        allowed, sig = Path(tmp) / "allowed", Path(tmp) / "sig"
        kind_and_key = " ".join(public_key.split()[:2])
        allowed.write_text(f'{signer} namespaces="{NAMESPACE}" {kind_and_key}\n')
        sig.write_text(signature)
        try:
            _run(
                ["-Y", "verify", "-f", str(allowed), "-I", signer, "-n", NAMESPACE, "-s", str(sig)],
                payload,
            )
        except (OSError, subprocess.SubprocessError):
            return False
    return True


class TrustStore:
    """Published verification keys: ``<home>/keys/published/<signer>.pub`` (DD-55).

    More than one line per file is allowed, so a rotated-out key keeps verifying old records.
    """

    def __init__(self, home: Path) -> None:
        self.dir = Path(home) / "keys" / "published"

    def keys(self, signer: str) -> list[str]:
        try:
            validate_id(signer, what="signer")
            text = (self.dir / f"{signer}.pub").read_text()
        except (OSError, ValueError):
            return []
        return [line for line in text.splitlines() if line.startswith("ssh-")]

    def verify(self, signer: str, payload: bytes, signature: str) -> bool:
        return any(_verify(key, signer, payload, signature) for key in self.keys(signer))


class Signer:
    """agenthalt's own executor key (self-attestation).

    Without ``ssh-keygen`` it falls back to HMAC, which only the key holder can check; ``doctor``
    warns and the confirmations name it (``agenthalt-executor-hmac``).
    """

    def __init__(self, home: Path) -> None:
        keys = Path(home) / "keys"
        self.key = keys / "executor_ed25519"
        self.secret = keys / "executor.key"
        self.trust = TrustStore(home)

    @property
    def asymmetric(self) -> bool:
        return _ssh_keygen() is not None

    def ensure(self) -> None:
        """Create the key and publish its public half. Call before elevating privileges."""
        if not self.asymmetric:
            self._hmac_key(create=True)
            return
        self.key.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if not self.key.exists():
            with tempfile.TemporaryDirectory(dir=self.key.parent) as tmp:
                draft = Path(tmp) / "key"
                _run(["-q", "-t", "ed25519", "-N", "", "-C", SELF, "-f", str(draft)], b"")
                with contextlib.suppress(FileExistsError):  # the first writer wins
                    os.link(draft, self.key)
                    os.replace(f"{draft}.pub", f"{self.key}.pub")
        published = self.trust.dir / f"{SELF}.pub"
        half = Path(f"{self.key}.pub")
        if not half.exists():  # a race or a crash between the two files: derive it again
            draft = half.with_name(f"{half.name}.{secrets.token_hex(4)}")
            draft.write_bytes(_run(["-y", "-f", str(self.key)], b""))
            os.replace(draft, half)
        public = half.read_text().strip()
        if public not in (published.read_text() if published.exists() else ""):
            self.trust.dir.mkdir(mode=0o700, parents=True, exist_ok=True)
            with published.open("a") as handle:  # append: old keys stay verifiable
                handle.write(public + "\n")

    def _hmac_key(self, *, create: bool) -> bytes:
        if create and not self.secret.exists():
            self.secret.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            draft = self.secret.with_name(f"{self.secret.name}.{secrets.token_hex(4)}")
            fd = os.open(draft, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w") as handle:
                handle.write(secrets.token_hex(32))
            try:
                with contextlib.suppress(FileExistsError):
                    os.link(draft, self.secret)
            finally:
                os.unlink(draft)
        key = bytes.fromhex(self.secret.read_text().strip())
        if len(key) < 32:
            raise ValueError("executor key is too short")
        return key

    def sign(self, payload: bytes) -> tuple[str, str] | None:
        """``(signed_by, signature)``, or ``None`` when nothing can vouch."""
        return self.sign_many([payload])[0]

    def sign_many(self, payloads: list[bytes]) -> list[tuple[str, str] | None]:
        """Sign several payloads with one ``ssh-keygen`` call (a halt signs all at once)."""
        if not payloads:
            return []
        try:
            self.ensure()
            if not self.asymmetric:
                key = self._hmac_key(create=False)
                return [
                    (SELF_HMAC, hmac.new(key, payload, hashlib.sha256).hexdigest())
                    for payload in payloads
                ]
            with tempfile.TemporaryDirectory() as tmp:
                files = []
                for index, payload in enumerate(payloads):
                    path = Path(tmp) / f"c{index}"
                    path.write_bytes(payload)
                    files.append(str(path))
                _run(["-q", "-Y", "sign", "-f", str(self.key), "-n", NAMESPACE, *files], b"")
                return [(SELF, Path(f"{path}.sig").read_text()) for path in files]
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            _log.error("sign.unavailable", extra={"fields": {"error": str(exc)}})
            return [None for _ in payloads]

    def verify(self, signed_by: str, payload: bytes, signature: str) -> bool:
        if signed_by == SELF:
            return self.trust.verify(SELF, payload, signature)
        if signed_by == SELF_HMAC:
            try:
                key = self._hmac_key(create=False)
            except (OSError, ValueError):
                return False
            good = hmac.new(key, payload, hashlib.sha256).hexdigest()
            return hmac.compare_digest(good, signature)
        return False
