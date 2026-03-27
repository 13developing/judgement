from __future__ import annotations

from fastapi.testclient import TestClient


def test_get_root_returns_200(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == 200


def test_get_questions_returns_empty_list(client: TestClient) -> None:
    response = client.get("/api/questions")

    assert response.status_code == 200
    assert response.json() == []
