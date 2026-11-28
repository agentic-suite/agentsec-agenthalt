"""Demo 1, the Replit stop, on the process and sandbox layers (PRD 22).

A "release-bot" enrolled with ``agenthalt run`` deletes records from a fake production store, with a
detached helper doing the same. One command stops both. Run it from the repository root:

    python examples/demo1_replit_stop.py            # macOS: freeze and kill
    systemd-run --user --scope -p Delegate=yes python examples/demo1_replit_stop.py   # Linux
    sudo python examples/demo1_replit_stop.py       # Linux, as root: also cuts the run's network

On Linux, ``agenthalt run`` refuses without a delegated cgroup; the demo then says why and exits 5.

Everything lives in a temporary directory; nothing outside it is touched. The expected outcome in
this version is ``partial-layer`` (exit 2): credentials and the gateway are not covered yet.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

RECORDS = 2000
AGENT = """
import os, sys, time
store = sys.argv[1]
def delete_forever():
    while True:
        for name in sorted(os.listdir(store))[:1]:
            try:
                os.unlink(os.path.join(store, name))
            except FileNotFoundError:
                pass
        time.sleep(0.05)
if os.fork() == 0:
    os.setsid()  # a helper that leaves the process group
    delete_forever()
delete_forever()
"""


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        home, store, script = root / "state", root / "fake-prod", root / "release_bot.py"
        store.mkdir()
        for number in range(RECORDS):
            (store / f"record-{number:05d}").touch()
        script.write_text(AGENT)
        source = str(Path(__file__).resolve().parents[1] / "src")
        env = {**os.environ, "PYTHONPATH": source}
        agenthalt = [sys.executable, "-m", "agenthalt", "--home", str(home)]

        def left() -> int:
            return len(list(store.iterdir()))

        errors = root / "run.err"
        agent = subprocess.Popen(  # noqa: S603 - this interpreter, our own script
            [
                *agenthalt,
                "run",
                "--name",
                "release-bot",
                "--",
                sys.executable,
                str(script),
                str(store),
            ],
            env=env,
            stderr=errors.open("wb"),
        )
        try:
            end = time.monotonic() + 20
            while left() > RECORDS - 20:
                if time.monotonic() > end or agent.poll() is not None:
                    print(f"the demo agent did not start:\n{errors.read_text(errors='replace')}")
                    return 5 if agent.poll() == 5 else 1
                time.sleep(0.05)
            print(f"release-bot is deleting: {left()} of {RECORDS} records left. Halting it.")
            started = time.monotonic()
            done = subprocess.run(  # noqa: S603 - fixed arguments
                [
                    *agenthalt,
                    "kill",
                    "--agent",
                    "release-bot",
                    "--reason",
                    "prod mutation",
                    "--deadline-ms",
                    "5000",
                    "--json",
                ],
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            took = time.monotonic() - started
            after = left()
            time.sleep(1)
            stopped = left() == after
            result = json.loads(done.stdout)
            print(f"halt returned in {took:.2f}s: {result['outcome']} (exit {done.returncode})")
            for layer, status in sorted(result["layers"].items()):
                print(f"  {layer}: {status}")
            print(f"  processes: {len(result['members'])}, survivors: {len(result['survivors'])}")
            print(f"records left: {left()} ({'no longer falling' if stopped else 'STILL FALLING'})")
            good = stopped and not result["survivors"] and done.returncode == 2
            print("demo passed" if good else "demo FAILED")
            return 0 if good else 1
        finally:
            subprocess.run(  # noqa: S603 - fixed arguments
                [*agenthalt, "kill", "--all", "--reason", "demo teardown", "--yes"],
                env=env,
                capture_output=True,
                check=False,
            )
            agent.kill()
            agent.wait()


if __name__ == "__main__":
    raise SystemExit(main())
