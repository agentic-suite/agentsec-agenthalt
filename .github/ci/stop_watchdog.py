"""CI guard: nothing outside a test's own sandbox may stay stopped (the M3 macOS hang).

Runs beside pytest, not above it, so a stray SIGSTOP aimed at pytest's ancestors cannot freeze it.
Every second it lists stopped processes. One that is not a test agent and stays stopped for more
than GRACE_S is logged with the test that was running, then continued, so the job (and its log)
survive. After LIMIT_S it dumps the process table and kills pytest.

Usage: stop_watchdog.py <log> <current-test file> <limit seconds>
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time

GRACE_S = 5.0
EXPECTED = ("pytest-of-", "release_bot", "agent.py")  # test agents may be stopped on purpose


def table() -> list[tuple[int, int, str, str]]:
    try:
        out = subprocess.run(
            ["ps", "-A", "-o", "pid=,ppid=,stat=,command="],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    rows = []
    for line in out.splitlines():
        parts = line.split(None, 3)
        if len(parts) == 4 and parts[0].isdigit() and parts[1].isdigit():
            rows.append((int(parts[0]), int(parts[1]), parts[2], parts[3]))
    return rows


def main() -> int:
    log_path, stamp, limit = sys.argv[1], sys.argv[2], float(sys.argv[3])
    log = open(log_path, "a", buffering=1)  # noqa: SIM115 - lives as long as we do

    def say(text: str) -> None:
        line = f"[watchdog {time.strftime('%H:%M:%S')}] {text}"
        log.write(line + "\n")
        print(line, flush=True)

    def current() -> str:
        try:
            with open(stamp) as handle:
                return handle.read().strip() or "?"
        except OSError:
            return "(before the first test)"

    began, since = time.monotonic(), {}
    say(f"watching (pid {os.getpid()}), limit {limit:.0f}s")
    while True:
        rows = table()
        stopped = {pid: (stat, cmd) for pid, _, stat, cmd in rows if stat.startswith("T")}
        for pid in list(since):
            if pid not in stopped:
                del since[pid]
        for pid, (stat, cmd) in stopped.items():
            if pid == os.getpid() or any(mark in cmd for mark in EXPECTED):
                continue
            first = since.setdefault(pid, time.monotonic())
            if time.monotonic() - first >= GRACE_S:
                say(f"WRONGLY STOPPED pid {pid} [{stat}] {cmd[:200]}")
                say(f"  during test: {current()}")
                for row in rows:
                    say(f"  ps: {row[0]:>6} {row[1]:>6} {row[2]:<5} {row[3][:160]}")
                try:
                    os.kill(pid, signal.SIGCONT)
                    say(f"  continued pid {pid}")
                except OSError as exc:
                    say(f"  could not continue pid {pid}: {exc}")
                since.pop(pid, None)
        if time.monotonic() - began > limit:
            say(f"HARD LIMIT reached during test: {current()}")
            for row in rows:
                say(f"  ps: {row[0]:>6} {row[1]:>6} {row[2]:<5} {row[3][:160]}")
            for pid, _, _, cmd in rows:
                if "pytest" in cmd and pid != os.getpid():
                    try:
                        os.kill(pid, signal.SIGKILL)
                        say(f"  killed pytest pid {pid}")
                    except OSError:
                        pass
            return 1
        time.sleep(1.0)


if __name__ == "__main__":
    raise SystemExit(main())
