"""
Logging setup for AUTOMIC backend.

Two formats:
  - 'json'  — production: structured single-line JSON per log record. Easy to
              ingest in Loki/Grafana/Datadog.
  - 'plain' — development: human-readable, one-line, with colors.

Selected via env LOG_FORMAT (default = 'plain'). LOG_LEVEL controls level
(default INFO).

Adds structured fields automatically when present on the LogRecord:
  request_id, tenant_id, user_id, path, method, status_code, duration_ms.

These fields are injected by the request_context middleware in
`app/core/middleware.py`.
"""
from __future__ import annotations
import json
import logging
import os
import sys
import time
from typing import Any, Dict


# Reserved attributes already present on LogRecord — don't pull them as 'extra'
_RESERVED = {
    "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
    "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
    "created", "msecs", "relativeCreated", "thread", "threadName",
    "processName", "process", "message", "asctime", "taskName",
}

# Custom fields we want to surface explicitly when set
_STRUCTURED_FIELDS = (
    "request_id", "tenant_id", "user_id",
    "path", "method", "status_code", "duration_ms",
    "tenant_slug", "task_name", "task_run_id",
)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "ts": self.formatTime(record, datefmt="%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for field in _STRUCTURED_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        # Capture any extra attributes that aren't reserved
        for key, value in record.__dict__.items():
            if key in _RESERVED or key in _STRUCTURED_FIELDS:
                continue
            if key.startswith("_"):
                continue
            try:
                json.dumps(value)
                payload[key] = value
            except TypeError:
                payload[key] = repr(value)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


class PlainFormatter(logging.Formatter):
    """One-line human format with optional structured fields appended."""

    BASE_FMT = "%(asctime)s %(levelname)-7s %(name)s — %(message)s"

    def __init__(self):
        super().__init__(self.BASE_FMT, datefmt="%H:%M:%S")

    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        extras = []
        for field in _STRUCTURED_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                extras.append(f"{field}={value}")
        if extras:
            base = f"{base}  [{' '.join(extras)}]"
        return base


def configure_logging() -> None:
    """Idempotent — safe to call from app startup. Replaces existing handlers."""
    fmt = os.environ.get("LOG_FORMAT", "plain").lower()
    level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setLevel(level)
    handler.setFormatter(JsonFormatter() if fmt == "json" else PlainFormatter())

    root = logging.getLogger()
    # Replace existing handlers to avoid duplicate logs on repeated calls
    for h in list(root.handlers):
        root.removeHandler(h)
    root.addHandler(handler)
    root.setLevel(level)

    # Quiet some loud third-party loggers in dev
    if fmt != "json":
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
        logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
