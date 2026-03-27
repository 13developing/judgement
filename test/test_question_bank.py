from __future__ import annotations

from typing import cast

from fastapi.testclient import TestClient


def _create_question_payload() -> dict[str, str]:
    return {
        "content": "解释牛顿第二定律。",
        "question_type": "short_answer",
        "standard_answer": "F=ma，物体加速度与合外力成正比。",
    }


def _as_object_dict(value: object) -> dict[str, object]:
    assert isinstance(value, dict)
    return cast(dict[str, object], value)


def _as_object_dict_list(value: object) -> list[dict[str, object]]:
    assert isinstance(value, list)
    value_list = cast(list[object], value)
    for item in value_list:
        assert isinstance(item, dict)
    return cast(list[dict[str, object]], value_list)


def test_create_question_returns_201(client: TestClient) -> None:
    response = client.post("/api/questions", json=_create_question_payload())

    assert response.status_code == 201
    body = _as_object_dict(cast(object, response.json()))
    created_id = body.get("id")
    assert isinstance(created_id, int)
    assert created_id > 0
    assert body["content"] == "解释牛顿第二定律。"
    assert body["question_type"] == "short_answer"
    assert body["standard_answer"] == "F=ma，物体加速度与合外力成正比。"


def test_list_questions_returns_created_question(client: TestClient) -> None:
    _ = client.post("/api/questions", json=_create_question_payload())

    response = client.get("/api/questions")

    assert response.status_code == 200
    rows = _as_object_dict_list(cast(object, response.json()))
    assert len(rows) == 1
    assert rows[0]["content"] == "解释牛顿第二定律。"


def test_delete_question_removes_question(client: TestClient) -> None:
    create_response = client.post("/api/questions", json=_create_question_payload())
    created = _as_object_dict(cast(object, create_response.json()))
    raw_question_id = created.get("id")
    assert isinstance(raw_question_id, int)
    question_id = raw_question_id

    delete_response = client.delete(f"/api/questions/{question_id}")

    assert delete_response.status_code == 200
    assert delete_response.json() == {"detail": "已删除"}

    list_response = client.get("/api/questions")
    assert list_response.status_code == 200
    assert list_response.json() == []


def test_delete_missing_question_returns_404(client: TestClient) -> None:
    response = client.delete("/api/questions/999")

    assert response.status_code == 404
    assert response.json() == {"detail": "题目不存在"}
