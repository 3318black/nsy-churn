"""Structured logging: one valid JSON line per event, timezone aware."""

from __future__ import annotations

import io
import json
import logging
from datetime import UTC, datetime
from typing import Any

import pytest

from churn.logging import HANDLER_NAME, configure_logging, get_logger, reset_logging


def _emit(stream: io.StringIO, level: int = logging.INFO) -> None:
    """Configure the logging on ``stream`` and emit one event."""
    configure_logging(level, stream=stream)
    get_logger("churn.test").info("configuration loaded")


def _single_payload(stream: io.StringIO) -> dict[str, Any]:
    """Return the only JSON object written to ``stream``."""
    lines = [line for line in stream.getvalue().splitlines() if line]
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert isinstance(payload, dict)
    return payload


def test_event_is_a_single_valid_json_line() -> None:
    """The expected fields are present and the record is one line of JSON."""
    stream = io.StringIO()
    _emit(stream)

    payload = _single_payload(stream)

    assert payload["level"] == "INFO"
    assert payload["logger"] == "churn.test"
    assert payload["message"] == "configuration loaded"
    assert set(payload) >= {"timestamp", "level", "logger", "message"}


def test_timestamp_is_timezone_aware_and_expressed_in_utc() -> None:
    """The ``DTZ`` rules forbid a naive datetime, and the contract expects UTC."""
    stream = io.StringIO()
    _emit(stream)

    moment = datetime.fromisoformat(_single_payload(stream)["timestamp"])

    assert moment.tzinfo is not None
    assert moment.utcoffset() == datetime.now(UTC).utcoffset()


def test_configure_logging_is_idempotent() -> None:
    """Calling the setup twice never duplicates the handler."""
    stream = io.StringIO()
    configure_logging(logging.INFO, stream=stream)
    configure_logging(logging.DEBUG, stream=io.StringIO())

    handlers = [
        handler for handler in logging.getLogger().handlers if handler.get_name() == HANDLER_NAME
    ]

    assert len(handlers) == 1
    assert handlers[0].level == logging.DEBUG

    get_logger("churn.test").info("still the first stream")
    assert _single_payload(stream)["message"] == "still the first stream"


def test_extra_fields_land_in_a_context_object() -> None:
    """Structured fields stay separate from the four base fields."""
    stream = io.StringIO()
    configure_logging(logging.INFO, stream=stream)
    get_logger("churn.test").info("rows read", extra={"rows": 12, "source": "kkbox"})

    payload = _single_payload(stream)

    assert payload["context"] == {"rows": 12, "source": "kkbox"}


def test_exception_is_serialised() -> None:
    """A traceback belongs to the record, not to a second line of output."""
    stream = io.StringIO()
    configure_logging(logging.INFO, stream=stream)
    try:
        message = "missing key"
        raise ValueError(message)
    except ValueError:
        get_logger("churn.test").exception("load failed")

    payload = _single_payload(stream)

    assert payload["level"] == "ERROR"
    assert "ValueError: missing key" in payload["exception"]


def test_default_destination_is_standard_output(capsys: pytest.CaptureFixture[str]) -> None:
    """The events go to standard output, one JSON object per line."""
    configure_logging(logging.INFO)
    get_logger("churn.test").info("written to stdout")

    captured = capsys.readouterr()

    assert captured.err == ""
    assert json.loads(captured.out.strip())["message"] == "written to stdout"


def test_reset_removes_the_handler() -> None:
    """The teardown of a test leaves the root logger clean."""
    configure_logging(logging.INFO, stream=io.StringIO())
    reset_logging()

    assert all(handler.get_name() != HANDLER_NAME for handler in logging.getLogger().handlers)
