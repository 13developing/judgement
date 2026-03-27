"""Structured logging configuration using stdlib logging."""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone

from typing_extensions import override


class JSONFormatter(logging.Formatter):
    """Emit log records as single-line JSON objects."""

    @override
    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, object] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)

        for key in ("request_id", "method", "path", "status_code", "duration_ms"):
            value = getattr(record, key, None)
            if value is not None:
                log_entry[key] = value

        return json.dumps(log_entry, ensure_ascii=False)


def setup_logging(*, level: str = "INFO") -> None:
    """Configure root logger with JSON formatter on stderr."""
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(JSONFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
