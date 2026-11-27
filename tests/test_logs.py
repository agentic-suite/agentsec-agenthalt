"""0.5 structured logging (#404): JSON lines, halt_id correlation, no secrets at any level."""

from __future__ import annotations

import io
import json
import logging

import pytest

from agenthalt.logs import bind_halt, configure_logging, get_logger

CANARY = "AKIAIOSFODNN7EXAMPLE"


@pytest.fixture
def stream() -> io.StringIO:
    buf = io.StringIO()
    configure_logging("debug", "json", stream=buf)
    return buf


def records(buf: io.StringIO) -> list[dict[str, object]]:
    return [json.loads(line) for line in buf.getvalue().splitlines()]


def test_json_lines_parse(stream: io.StringIO) -> None:
    get_logger().info("halt.raised", extra={"fields": {"scope": "agent:bot", "mode": "kill"}})
    (rec,) = records(stream)
    assert rec["event"] == "halt.raised" and rec["level"] == "info"
    assert rec["scope"] == "agent:bot" and rec["mode"] == "kill"
    assert str(rec["ts"]).endswith("Z")
    assert rec["halt_id"] is None


def test_halt_id_correlation(stream: io.StringIO) -> None:
    log = get_logger()
    with bind_halt("hlt_01"):
        log.info("stage.resolve")
        with bind_halt("hlt_02"):
            log.info("stage.nested")
        log.info("stage.plan")
    log.info("after")
    ids = [r["halt_id"] for r in records(stream)]
    assert ids == ["hlt_01", "hlt_02", "hlt_01", None]


def test_canary_never_reaches_output(stream: io.StringIO) -> None:
    log = get_logger()
    log.warning(
        f"saw key {CANARY}",
        extra={"fields": {"token": "plain-value", "note": f"Bearer {'x' * 40}"}},
    )
    try:
        raise RuntimeError(f"boom {CANARY}")
    except RuntimeError:
        log.exception("failed")
    out = stream.getvalue()
    assert CANARY not in out and "plain-value" not in out and "x" * 40 not in out
    assert "secret:aws_access_key[redacted]" in out


def test_level_filtering() -> None:
    buf = io.StringIO()
    configure_logging("warning", "json", stream=buf)
    get_logger().info("quiet")
    get_logger().error("loud")
    assert [r["event"] for r in records(buf)] == ["loud"]


def test_text_format() -> None:
    buf = io.StringIO()
    configure_logging("info", "text", stream=buf)
    with bind_halt("hlt_9"):
        get_logger().info("stage.receipt", extra={"fields": {"status": "complete"}})
    line = buf.getvalue().strip()
    assert (
        "info" in line
        and "stage.receipt" in line
        and "halt=hlt_9" in line
        and "status=complete" in line
    )


def test_reconfigure_replaces_handler() -> None:
    a, b = io.StringIO(), io.StringIO()
    configure_logging("info", "json", stream=a)
    configure_logging("info", "json", stream=b)
    get_logger().info("once")
    assert a.getvalue() == "" and len(records(b)) == 1
    assert len(logging.getLogger("agenthalt").handlers) == 1


def test_bad_level_rejected() -> None:
    with pytest.raises(ValueError):
        configure_logging("loud", "json")


def test_redact_value_passes_non_text_through() -> None:
    from agenthalt.redact import redact_value

    assert redact_value(5) == 5 and redact_value(None) is None
    assert redact_value({"api_key": 123}) == {"api_key": "secret:api_key[redacted]"}
