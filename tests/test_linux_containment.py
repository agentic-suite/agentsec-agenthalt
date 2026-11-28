"""3.3 / 3.6 on a real kernel: cgroup freeze and kill, and the iptables cut.

Needs Linux, root, cgroup v2 and iptables. CI skips these; a privileged container runs them.
"""

from __future__ import annotations

import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

PY = sys.executable
pytestmark = pytest.mark.skipif(
    not (sys.platform == "linux" and os.geteuid() == 0 and shutil.which("iptables")),
    reason="needs Linux, root and iptables",
)

# sends a counter over one long-lived connection, tries new ones, and double-forks a daemon
AGENT = """
import os, socket, sys, time
port, out = int(sys.argv[1]), sys.argv[2]
if os.fork() == 0:
    os.setsid()
    if os.fork():
        os._exit(0)
    os.environ.clear()
    while True:
        open(out + ".daemon", "a").write("."); time.sleep(0.02)
conn = None
while True:
    try:
        conn = conn or socket.create_connection(("127.0.0.1", port), timeout=1)
        conn.sendall(b".")
    except OSError as exc:
        open(out + ".errors", "a").write(f"{type(exc).__name__}\\n"); conn = None
    try:
        socket.create_connection(("127.0.0.1", port), timeout=1).close()
        open(out + ".new", "a").write(".")
    except OSError:
        pass
    open(out + ".alive", "a").write("."); time.sleep(0.05)
"""


class Server:
    def __init__(self) -> None:
        self.received = 0
        self.sock = socket.socket()
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(64)
        self.port = self.sock.getsockname()[1]
        threading.Thread(target=self._accept, daemon=True).start()

    def _accept(self) -> None:
        while True:
            try:
                conn, _ = self.sock.accept()
            except OSError:
                return
            threading.Thread(target=self._read, args=(conn,), daemon=True).start()

    def _read(self, conn: socket.socket) -> None:
        while True:
            try:
                data = conn.recv(1024)
            except OSError:
                return
            if not data:
                return
            self.received += len(data)


def size(path: Path) -> int:
    return path.stat().st_size if path.exists() else 0


def grows(read: Any, wait: float = 0.4) -> bool:
    before = read()
    time.sleep(wait)
    return bool(read() != before)


def wait_for(check: Any, timeout: float = 20.0) -> None:
    end = time.monotonic() + timeout
    while not check():
        assert time.monotonic() < end, "timed out"
        time.sleep(0.05)


def cli(home: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}
    return subprocess.run(
        [PY, "-m", "agenthalt", "--home", str(home), *args],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def rules() -> str:
    return subprocess.run(
        ["iptables", "-S", "OUTPUT"], capture_output=True, text=True, check=True
    ).stdout


class Live:
    def __init__(self, tmp_path: Path) -> None:
        self.home, self.out, self.server = tmp_path / "h", tmp_path / "bot", Server()
        script = tmp_path / "agent.py"
        script.write_text(AGENT)
        env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}
        launch = [PY, "-m", "agenthalt", "--home", str(self.home), "run", "--name", "bot", "--"]
        self.supervisor = subprocess.Popen(
            [*launch, PY, str(script), str(self.server.port), str(self.out)],
            env=env,
            stderr=subprocess.DEVNULL,
        )
        wait_for(lambda: self.server.received > 2 and size(self.file("daemon")) > 2)

    def file(self, kind: str) -> Path:
        return self.out.with_name(f"{self.out.name}.{kind}")

    def acting(self) -> bool:
        return grows(lambda: (size(self.file("alive")), size(self.file("daemon"))))


@pytest.fixture
def live(tmp_path: Path) -> Iterator[Live]:
    agent = Live(tmp_path)
    try:
        yield agent
    finally:
        cli(agent.home, "kill", "--all", "--reason", "test teardown", "--yes")
        agent.supervisor.kill()
        agent.supervisor.wait()


def halt(agent: Live, mode: str) -> dict[str, Any]:
    done = cli(
        agent.home, mode, "--agent", "bot", "--reason", "r", "--deadline-ms", "10000", "--json"
    )
    assert done.returncode in (1, 2), done.stderr
    return dict(json.loads(done.stdout))


def test_quarantine_freezes_and_cuts_then_lift_restores(live: Live) -> None:
    data = halt(live, "quarantine")
    assert data["layers"]["process"] == "confirmed", data
    assert data["layers"]["sandbox"] == "confirmed", data
    assert data["outcome"] == "partial-layer"
    assert not live.acting() and "agenthalt:" in rules()
    assert socket.create_connection(("127.0.0.1", live.server.port), timeout=2)  # we still can

    # thaw the agent without lifting, to watch the network cut by itself
    run = data["members"][0]["run"]  # other runs may have left empty groups behind
    group = next(Path("/sys/fs/cgroup").rglob(f"agenthalt-{run}"))
    before = live.server.received
    new, errors = size(live.file("new")), size(live.file("errors"))
    (group / "cgroup.freeze").write_text("0")
    for pid in (group / "cgroup.procs").read_text().split():
        os.kill(int(pid), signal.SIGCONT)
    wait_for(lambda: size(live.file("errors")) > errors)
    time.sleep(0.5)
    assert live.server.received == before, "nothing left the cgroup"
    assert size(live.file("new")) == new, "no new connection"

    done = cli(live.home, "lift", "--halt", data["halt_id"], "--reason", "clean")
    assert done.returncode == 0, done.stdout
    assert "agenthalt:" not in rules()
    wait_for(lambda: live.server.received > before)


def test_kill_takes_the_daemon_too_and_leaves_no_rules(live: Live) -> None:
    data = halt(live, "kill")
    assert data["layers"]["process"] == "confirmed" and data["survivors"] == [], data
    assert len(data["members"]) >= 2
    assert not live.acting()
    assert "agenthalt:" not in rules()
    assert live.supervisor.wait(timeout=20) == 128 + signal.SIGKILL


def test_pause_and_lift_on_a_real_cgroup(live: Live) -> None:
    data = halt(live, "pause")
    assert data["layers"]["process"] == "confirmed" and not live.acting()
    done = cli(live.home, "lift", "--halt", data["halt_id"], "--reason", "ok")
    assert done.returncode == 0, done.stdout
    wait_for(live.acting)
