"""2.7 (#569): enrollment through the supervisor, with real processes."""

from __future__ import annotations

import os
import pwd
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from agenthalt.coordinator import Coordinator
from agenthalt.journal import Journal
from agenthalt.observe import SystemObserver
from agenthalt.scopes import Mode, Scope
from agenthalt.store import Store
from agenthalt.subtree import Graph, Resolver
from agenthalt.supervisor import (
    EnrollmentError,
    SpawnRefusedError,
    Supervisor,
    prepare_cgroup,
    resolve_user,
)
from tests.lineage_helpers import FakeObserver, adapters, make_registry, proc, root

PY = sys.executable


def supervisor(home: Path, **kwargs: object) -> Supervisor:
    kwargs.setdefault("containment", "pgroup")
    return Supervisor(home, poll_s=0.05, **kwargs)  # type: ignore[arg-type]


def script(tmp_path: Path, body: str) -> list[str]:
    path = tmp_path / "agent.py"
    path.write_text("import os, sys, time, subprocess, signal\n" + body)
    return [PY, str(path)]


def findings(home: Path, kind: str) -> list[dict]:  # type: ignore[type-arg]
    return [e["payload"] for e in Journal(home).entries() if e["payload"].get("finding") == kind]


def graph(home: Path) -> Graph:
    return Graph(make_registry(home).read().edges)


def halt(home: Path, scope: str) -> None:
    store = Store(home)
    store.ensure()
    Coordinator(store).raise_halt(Scope.parse(scope), Mode.KILL, actor="op", reason="r")


def test_run_root_before_exec(tmp_path: Path) -> None:
    home = tmp_path / "h"
    body = (
        f"segment = open({str(home / 'lineage' / 'seg-000001.jsonl')!r}).read()\n"
        "sys.exit(0 if os.environ['AGENTHALT_RUN_ID'] in segment else 3)\n"
    )
    result = supervisor(home).run(script(tmp_path, body), name="bot")
    assert result.exit_code == 0
    g = graph(home)
    assert g.enrolled() == (result.run_id,)
    assert g.meta[result.run_id]["enrollment"] == "run"
    assert g.agent_of(result.run_id) == "bot"
    assert not make_registry(home).read().findings


@pytest.mark.parametrize(
    ("body", "code"),
    [("sys.exit(7)\n", 7), ("os.kill(os.getpid(), signal.SIGKILL)\n", 137)],
)
def test_run_returns_the_agents_exit_status(tmp_path: Path, body: str, code: int) -> None:
    assert supervisor(tmp_path / "h").run(script(tmp_path, body)).exit_code == code


def test_a_missing_command_enrolls_nothing(tmp_path: Path) -> None:
    with pytest.raises(EnrollmentError):
        supervisor(tmp_path / "h").run(["definitely-not-a-command"])
    assert not (tmp_path / "h" / "lineage").exists()


def test_a_command_that_cannot_exec_is_reported(tmp_path: Path) -> None:
    bad = tmp_path / "bad"
    bad.write_text("\x00not a program")
    bad.chmod(0o755)
    with pytest.raises(EnrollmentError, match="cannot execute"):
        supervisor(tmp_path / "h").run([str(bad)])


@pytest.mark.parametrize("scope", ["all", "agent:bot"])
def test_a_halted_scope_cannot_spawn(tmp_path: Path, scope: str) -> None:
    home, marker = tmp_path / "h", tmp_path / "ran"
    halt(home, scope)
    with pytest.raises(SpawnRefusedError):
        supervisor(home).run(script(tmp_path, f"open({str(marker)!r}, 'w')\n"), name="bot")
    assert not marker.exists(), "the command must never run"
    assert findings(home, "post_halt_spawn")
    assert graph(home).enrolled(), "the refused spawn is still on record"


def test_a_spawn_from_inside_a_halted_run_is_refused(tmp_path: Path) -> None:
    """The parent is found by process ancestry, not by an environment variable it can unset."""
    home = tmp_path / "h"
    reg = make_registry(home)
    me = SystemObserver().snapshot()[os.getpid()]
    reg.append_edges(
        adapters(reg)["process"], [root("run_outer", "outer", pid=me.pid, start=me.start)]
    )
    halt(home, "run:run_outer")
    with pytest.raises(SpawnRefusedError):
        supervisor(home).run([PY, "-c", "pass"], name="inner")


def test_an_unknown_parent_hint_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AGENTHALT_RUN_ID", "run_unknown")
    with pytest.raises(SpawnRefusedError, match="lineage_gap"):
        supervisor(tmp_path / "h").run([PY, "-c", "pass"])


def test_nested_enrollment_links_to_its_parent_without_false_gaps(tmp_path: Path) -> None:
    home = tmp_path / "h"
    src = str(Path(__file__).resolve().parents[1] / "src")
    inner = (
        f"import sys; sys.path.insert(0, {src!r})\n"
        "from agenthalt.supervisor import Supervisor\n"
        f"Supervisor({str(home)!r}, containment='pgroup', poll_s=0.05)"
        ".run([sys.executable, '-c', 'import time; time.sleep(0.8)'], name='inner')\n"
    )
    body = f"subprocess.run([sys.executable, '-c', {inner!r}], check=True)\n"
    outer = supervisor(home).run(script(tmp_path, body), name="outer")
    g = graph(home)
    child = next(r for r in g.enrolled() if r != outer.run_id)
    assert outer.run_id in g.ancestors(child)
    assert not [
        f for f in findings(home, "lineage_gap") if f["run"] == outer.run_id and f["node"] == child
    ]


def test_descendants_are_recorded(tmp_path: Path) -> None:
    home = tmp_path / "h"
    body = "subprocess.run([sys.executable, '-c', 'import time; time.sleep(1)'])\n"
    result = supervisor(home).run(script(tmp_path, body))
    assert len(graph(home).walk([result.run_id])[0]) == 2
    assert not result.gaps and not result.survivors


def test_setsid_escape_reported(tmp_path: Path) -> None:
    home = tmp_path / "h"
    body = (
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(1.5)'],"
        " start_new_session=True)\n"
        "time.sleep(1)\n"
    )
    result = supervisor(home).run(script(tmp_path, body))
    assert result.gaps
    assert any("process group" in f["why"] for f in findings(home, "lineage_gap"))
    assert len(graph(home).walk([result.run_id])[0]) == 2, "the escaped child stays tracked"
    assert (
        not Resolver(make_registry(home), SystemObserver())
        .resolve("run", result.run_id)
        .lineage_verified
    )


def double_fork(clear_env: bool) -> str:
    env = "{}" if clear_env else "dict(os.environ)"
    return (
        "if os.fork() == 0:\n"
        "    os.setsid()\n"
        "    if os.fork() == 0:\n"
        "        os.execve(sys.executable, [sys.executable, '-c', 'import time; time.sleep(2)'], "
        f"{env})\n"
        "    os._exit(0)\n"
        "os.wait()\n"
        "time.sleep(0.6)\n"
    )


def test_double_fork_stays(tmp_path: Path) -> None:
    """A daemonized grandchild is contained or reported, never silent."""
    home = tmp_path / "h"
    result = supervisor(home).run(script(tmp_path, double_fork(clear_env=False)))
    assert result.gaps and findings(home, "lineage_gap")
    assert result.survivors, "the daemon outlives the agent and is reported"


def test_a_daemon_with_a_clean_environment_is_still_noticed(tmp_path: Path) -> None:
    home = tmp_path / "h"
    result = supervisor(home).run(script(tmp_path, double_fork(clear_env=True)))
    assert any("liveness" in why for why in result.gaps)
    assert findings(home, "lineage_gap")


def test_supervisor_crash(tmp_path: Path) -> None:
    home, pidfile = tmp_path / "h", tmp_path / "pid"
    src = str(Path(__file__).resolve().parents[1] / "src")
    agent = script(
        tmp_path, f"open({str(pidfile)!r}, 'w').write(str(os.getpid()))\ntime.sleep(20)\n"
    )
    code = (
        f"import sys; sys.path.insert(0, {src!r})\n"
        "from agenthalt.supervisor import Supervisor\n"
        f"Supervisor({str(home)!r}, containment='pgroup', poll_s=0.05).run({agent!r}, name='bot')\n"
    )
    sup = subprocess.Popen([PY, "-c", code])
    try:
        deadline = time.monotonic() + 10
        while not (pidfile.exists() and pidfile.read_text()):
            assert time.monotonic() < deadline
            time.sleep(0.05)
        agent_pid = int(pidfile.read_text())
        sup.kill()
        sup.wait()
        os.kill(agent_pid, 0)  # the agent is still running...
        tree = Resolver(make_registry(home), SystemObserver()).resolve("agent", "bot")
        assert tree.complete and tree.members, "...and still resolvable"
        assert findings(home, "supervisor_lost")
    finally:
        sup.kill()
        if pidfile.exists() and pidfile.read_text():
            os.kill(int(pidfile.read_text()), signal.SIGKILL)


def test_run_in_a_terminal_keeps_stdin_with_the_agent(tmp_path: Path) -> None:
    import pty

    home = tmp_path / "h"
    src = str(Path(__file__).resolve().parents[1] / "src")
    code = (
        f"import sys; sys.path.insert(0, {src!r})\n"
        "from agenthalt.supervisor import Supervisor\n"
        f"r = Supervisor({str(home)!r}, containment='pgroup', poll_s=0.05)"
        ".run([sys.executable, '-c', 'print(\"got:\" + input())'])\n"
        "sys.exit(r.exit_code)\n"
    )
    pid, fd = pty.fork()
    if pid == 0:  # pragma: no cover - the child becomes the supervisor
        os.execv(PY, [PY, "-c", code])  # noqa: S606
    os.write(fd, b"hello\n")
    out, deadline = b"", time.monotonic() + 15
    while b"got:hello" not in out and time.monotonic() < deadline:
        try:
            out += os.read(fd, 1024)
        except OSError:
            break
    if b"got:hello" not in out:
        os.kill(pid, signal.SIGKILL)
    _, status = os.waitpid(pid, 0)
    assert b"got:hello" in out and os.waitstatus_to_exitcode(status) == 0


def test_sigterm_is_forwarded_to_the_agent(tmp_path: Path) -> None:
    body = "os.kill(os.getppid(), signal.SIGTERM)\ntime.sleep(10)\n"
    assert supervisor(tmp_path / "h").run(script(tmp_path, body)).exit_code == 128 + signal.SIGTERM


# --------------------------------------------------------------------------- attach


@pytest.fixture
def sleeper():
    code = (
        "import subprocess, sys, time\n"
        "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(20)'])\n"
        "time.sleep(20)\n"
    )
    process = subprocess.Popen([PY, "-c", code], start_new_session=True)
    time.sleep(0.8)
    yield process
    os.killpg(process.pid, signal.SIGKILL)
    process.wait()


def test_attach_walks_then_verifies_and_is_idempotent(
    tmp_path: Path, sleeper: subprocess.Popen[bytes]
) -> None:
    home = tmp_path / "h"
    first = supervisor(home).attach(sleeper.pid, name="late")
    assert first.created and first.verified
    assert len(first.members) == 2
    again = supervisor(home).attach(sleeper.pid)
    assert not again.created and again.run_id == first.run_id
    assert graph(home).meta[first.run_id]["enrollment"] == "attach"
    child = first.members[1]
    pid = graph(home).meta[child]["pid"]
    assert supervisor(home).attach(pid).run_id == child, "already in the lineage"


def test_attach_unverified(tmp_path: Path) -> None:
    class Flaky(FakeObserver):
        calls = 0

        def snapshot(self, timeout_s: float = 5.0):  # type: ignore[no-untyped-def]
            self.calls += 1
            self.fail = self.calls > 1
            return super().snapshot(timeout_s)

    home, seen = tmp_path / "h", Flaky()
    seen.add(proc(4242, 1, uid=os.getuid()))
    result = supervisor(home, observer=seen).attach(4242)
    assert result.created and not result.verified
    tree = Resolver(make_registry(home), FakeObserver()).resolve("run", result.run_id)
    assert not tree.lineage_verified


@pytest.mark.parametrize("pid", [1, 99_999_999])
def test_attach_refuses_foreign_and_missing_processes(tmp_path: Path, pid: int) -> None:
    if pid == 1 and os.getuid() == 0:
        pytest.skip("running as root")
    with pytest.raises(EnrollmentError):
        supervisor(tmp_path / "h").attach(pid)
    assert not (tmp_path / "h" / "lineage").exists()


# --------------------------------------------------------------------------- cgroup and user


def fake_cgroup(tmp_path: Path, mounted: bool = True) -> tuple[Path, Path]:
    base = tmp_path / "cg"
    (base / "user.slice").mkdir(parents=True)
    if mounted:
        (base / "cgroup.controllers").write_text("")
    own = tmp_path / "self"
    own.write_text("0::/user.slice\n")
    return base, own


def test_prepare_cgroup_creates_a_child_group(tmp_path: Path) -> None:
    base, own = fake_cgroup(tmp_path)
    group, name = prepare_cgroup("run_a", root=base, self_cgroup=own)
    assert group == base / "user.slice" / "agenthalt-run_a" and group.is_dir()
    assert name == "/user.slice/agenthalt-run_a"


@pytest.mark.parametrize("problem", ["unmounted", "no_entry", "undelegated"])
def test_enrollment_refuses_without_cgroup_delegation(tmp_path: Path, problem: str) -> None:
    base, own = fake_cgroup(tmp_path, mounted=problem != "unmounted")
    if problem == "no_entry":
        own.write_text("1:name=systemd:/\n")
    if problem == "undelegated":
        (base / "user.slice").rmdir()
    with pytest.raises(EnrollmentError, match="cgroup"):
        prepare_cgroup("run_a", root=base, self_cgroup=own)


def pw(uid: int, name: str = "agentbot") -> pwd.struct_passwd:
    return pwd.struct_passwd((name, "x", uid, uid, "", f"/home/{name}", "/bin/sh"))


def test_resolve_user(tmp_path: Path) -> None:
    spec = resolve_user(
        "agentbot",
        tmp_path / "h",
        euid=0,
        invoking_uid=1,
        lookup=lambda _: pw(777),
        groups=lambda *_: [777],
    )
    assert (spec.uid, spec.gid, spec.groups) == (777, 777, (777,))


@pytest.mark.parametrize(
    ("euid", "target", "message"),
    [(501, 777, "root"), (0, 0, "root"), (0, 1, "yourself"), (0, None, "no such user")],
)
def test_resolve_user_refusals(tmp_path: Path, euid: int, target: int | None, message: str) -> None:
    def lookup(_: str) -> pwd.struct_passwd:
        if target is None:
            raise KeyError
        return pw(target)

    with pytest.raises(EnrollmentError, match=message):
        resolve_user("agentbot", tmp_path / "h", euid=euid, invoking_uid=1, lookup=lookup)


def test_resolve_user_refuses_a_state_dir_the_agent_could_replace(tmp_path: Path) -> None:
    def call(target_uid: int) -> None:
        resolve_user(
            "agentbot",
            tmp_path / "h",
            euid=0,
            invoking_uid=1,
            lookup=lambda _: pw(target_uid),
            groups=lambda *_: [],
        )

    if os.getuid() == 0:
        os.chown(tmp_path, 888, 888)
    with pytest.raises(EnrollmentError, match="state directory"):
        call(tmp_path.stat().st_uid)  # the agent user owns the parent
    tmp_path.chmod(0o777)
    try:
        with pytest.raises(EnrollmentError, match="state directory"):
            call(777)
    finally:
        tmp_path.chmod(0o700)


# --------------------------------------------------------------------------- real Linux (root)

linux_root = pytest.mark.skipif(
    sys.platform != "linux" or os.geteuid() != 0 or not os.access("/sys/fs/cgroup", os.W_OK),
    reason="needs Linux, root and a writable cgroup v2 mount",
)


@linux_root
def test_cgroup_double_fork_contained(tmp_path: Path) -> None:
    home = tmp_path / "h"
    result = supervisor(home, containment="cgroup").run(
        script(tmp_path, double_fork(clear_env=True))
    )
    members = graph(home).walk([result.run_id])[0]
    assert len(members) >= 2 and result.survivors, "the daemon stays in the cgroup"
    assert graph(home).meta[result.run_id]["cgroup"].endswith(result.run_id)


@linux_root
def test_real_user_drop(tmp_path: Path) -> None:
    home = tmp_path / "h"
    target = pwd.getpwnam("nobody")
    body = (
        f"assert os.getuid() == os.geteuid() == {target.pw_uid}\n"
        f"assert not os.access({str(home / 'store')!r}, os.R_OK)\n"
        "assert os.environ['USER'] == 'nobody'\n"
    )
    code = script(tmp_path, body)
    for path in (tmp_path, *tmp_path.parents):
        path.chmod(path.stat().st_mode | 0o005)  # the agent user must be able to read its script
        if path.parent == Path("/tmp"):
            break
    result = supervisor(home, containment="cgroup").run(code, user="nobody")
    assert result.exit_code == 0
    assert os.geteuid() == 0, "privileges are restored afterwards"
    assert graph(home).meta[result.run_id]["user"] == "nobody"
