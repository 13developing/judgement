"""Tests for batch grading endpoint."""

from __future__ import annotations

from io import BytesIO

from fastapi.testclient import TestClient


def test_batch_judge_rejects_too_many(client: TestClient) -> None:
    """Batch endpoint rejects > 10 images."""
    files = [("images", (f"img{i}.jpg", BytesIO(b"x" * 100), "image/jpeg")) for i in range(11)]
    resp = client.post("/api/judge/batch", files=files)
    assert resp.status_code == 400


def test_batch_judge_validates_images(client: TestClient) -> None:
    """Batch endpoint validates image format."""
    files = [("images", ("bad.txt", BytesIO(b"not an image"), "text/plain"))]
    resp = client.post("/api/judge/batch", files=files)
    assert resp.status_code == 400
