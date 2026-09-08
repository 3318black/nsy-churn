"""Structured logging, one JSON object per event on standard output.

The standard library is enough here. Adding a logging package would require an
entry in ``docs/decisions.md``, and decision D9 froze the dependency list.

Every timestamp is timezone aware and expressed in UTC, as the ``DTZ`` rules of
``ruff`` demand and as the data contract expects for any date handled by the
project.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from typing import IO, Any

__all__ = [
    "HANDLER_NAME",
    "JsonFormatter",
    "configure_logging",
    "get_logger",
    "reset_logging",
]

#: Name carried by the handler this module installs, which makes the setup idempotent.
HANDLER_NAME = "churn-json"

# Attributes every LogRecord carries. Anything else comes from an ``extra``
# argument and is reported under the ``context`` key.
_RESERVED_RECORD_ATTRS = frozenset(
    {
        "args",
        "asctime",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "getMessage",
        "levelname",
        "levelno",
        "lineno",
        "message",
        "module",
        "msecs",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "taskName",
        "thread",
        "threadName",
    }
)


class JsonFormatter(logging.Formatter):
    """Render a log record as a single JSON line."""

    def format(self, record: logging.LogRecord) -> str:
        """Return the JSON representation of ``record``."""
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        context = {
            key: value
            for key, value in record.__dict__.items()
            if key not in _RESERVED_RECORD_ATTRS and not key.startswith("_")
        }
        if context:
            payload["context"] = context
        if record.exc_info is not None:
            payload["exception"] = self.formatException(record.exc_info)
        if record.stack_info is not None:
            payload["stack"] = self.formatStack(record.stack_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def _find_handler(root: logging.Logger) -> logging.Handler | None:
    """Return the handler installed by this module, if any."""
    for handler in root.handlers:
        if handler.get_name() == HANDLER_NAME:
            return handler
    return None


def configure_logging(level: int | str = logging.INFO, stream: IO[str] | None = None) -> None:
    """Install the JSON handler on the root logger.

    Calling this function twice never duplicates the handler: the second call
    only refreshes the level.

    Args:
        level: threshold applied to the root logger and to the handler.
        stream: destination of the log lines. Defaults to standard output.
    """
    root = logging.getLogger()
    existing = _find_handler(root)
    if existing is not None:
        existing.setLevel(level)
        root.setLevel(level)
        return
    handler = logging.StreamHandler(sys.stdout if stream is None else stream)
    handler.set_name(HANDLER_NAME)
    handler.setLevel(level)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    root.setLevel(level)


def reset_logging() -> None:
    """Remove the handler installed by :func:`configure_logging`.

    Mainly useful to isolate tests from one another.
    """
    root = logging.getLogger()
    handler = _find_handler(root)
    if handler is not None:
        root.removeHandler(handler)
        handler.close()


def get_logger(name: str) -> logging.Logger:
    """Return the logger of a module, without configuring anything."""
    return logging.getLogger(name)
