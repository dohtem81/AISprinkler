"""Centralized structured logging setup for AISprinkler."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone

_RESERVED_KEYS = {
    "name",
    "msg",
    "args",
    "levelname",
    "levelno",
    "pathname",
    "filename",
    "module",
    "exc_info",
    "exc_text",
    "stack_info",
    "lineno",
    "funcName",
    "created",
    "msecs",
    "relativeCreated",
    "thread",
    "threadName",
    "processName",
    "process",
    "message",
    "asctime",
}


class JsonFormatter(logging.Formatter):
    """Formats log records into flat JSON payloads for Loki/Grafana."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        for key, value in record.__dict__.items():
            if key in _RESERVED_KEYS or key.startswith("_"):
                continue
            payload[key] = _json_safe(value)

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, separators=(",", ":"), ensure_ascii=True)


class PlainFormatter(logging.Formatter):
    """Readable fallback formatter for local development."""

    def __init__(self) -> None:
        super().__init__(
            fmt="%(asctime)s %(levelname)s [%(name)s] %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )


def configure_logging() -> None:
    """Configures root logging once with JSON or plain-text formatting."""
    root = logging.getLogger()
    if getattr(root, "_aisprinkler_logging_configured", False):
        return

    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    log_format = os.getenv("LOG_FORMAT", "json").strip().lower()

    handler = logging.StreamHandler()
    if log_format == "plain":
        handler.setFormatter(PlainFormatter())
    else:
        handler.setFormatter(JsonFormatter())

    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(log_level)
    setattr(root, "_aisprinkler_logging_configured", True)


def _json_safe(value: object) -> object:
    try:
        json.dumps(value)
        return value
    except TypeError:
        return str(value)
