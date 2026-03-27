from __future__ import annotations

from typing import cast

from fastapi.testclient import TestClient


def test_llm_metrics_endpoint(client: TestClient) -> None:
    resp = client.get("/api/metrics/llm")
    assert resp.status_code == 200

    data = cast(dict[str, object], resp.json())
    assert "prompt_tokens" in data
    assert "request_count" in data
