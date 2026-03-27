"""Tests for grading history export."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_export_json_empty(client: TestClient) -> None:
    """Export JSON with no results returns empty list."""
    resp = client.get("/api/export/results?format=json")
    assert resp.status_code == 200
    assert resp.json() == []


def test_export_csv_empty(client: TestClient) -> None:
    """Export CSV with no results returns header-only CSV."""
    resp = client.get("/api/export/results?format=csv")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    content = resp.text
    assert "ID" in content
    assert "得分" in content


def test_export_invalid_format_rejected(client: TestClient) -> None:
    """Invalid format is rejected by validation."""
    resp = client.get("/api/export/results?format=xml")
    assert resp.status_code == 422
