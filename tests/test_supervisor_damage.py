"""2.CR: damage that happens while the agent is already running must not abort supervision."""

from __future__ import annotations

from pathlib import Path

from tests.test_supervisor import script, supervisor


def test_a_registry_that_breaks_mid_run_does_not_abort_supervision(tmp_path: Path) -> None:
    home, done = tmp_path / "h", tmp_path / "done"
    body = (
        f"open({str(home / 'journal' / 'seg-000001.jsonl')!r}, 'a').write('garbage\\n')\n"
        "subprocess.run([sys.executable, '-c', 'import time; time.sleep(0.6)'])\n"
        f"open({str(done)!r}, 'w')\n"
        "sys.exit(5)\n"
    )
    result = supervisor(home).run(script(tmp_path, body))
    assert result.exit_code == 5 and done.exists()
    assert any("supervision degraded" in why for why in result.gaps)
