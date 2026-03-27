"""Tests for structured logging."""

# pyright: reportMissingImports=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownArgumentType=false

from __future__ import annotations

import json
import logging
from typing import cast

from fastapi.testclient import TestClient

from backend.logging_config import JSONFormatter


def test_json_formatter_basic() -> None:
    """JSONFormatter outputs valid JSON with required fields."""
    formatter = JSONFormatter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="hello %s",
        args=("world",),
        exc_info=None,
    )

    output = formatter.format(record)
    data = cast(dict[str, object], json.loads(output))

    assert data["level"] == "INFO"
    assert data["message"] == "hello world"
    assert "timestamp" in data


def test_json_formatter_with_extras() -> None:
    """JSONFormatter includes extra fields like request_id."""
    formatter = JSONFormatter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="request",
        args=(),
        exc_info=None,
    )
    record.request_id = "abc-123"
    record.method = "GET"
    record.path = "/api/test"
    record.status_code = 200
    record.duration_ms = 42.5

    output = formatter.format(record)
    data = cast(dict[str, object], json.loads(output))

    assert data["request_id"] == "abc-123"
    assert data["method"] == "GET"
    assert data["status_code"] == 200


def test_access_log_middleware(client: TestClient) -> None:
    """Access log middleware logs requests (verify no crash)."""
    response = client.get("/health")

    assert response.status_code == 200
