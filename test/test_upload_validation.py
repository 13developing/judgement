from __future__ import annotations

from io import BytesIO

from fastapi.testclient import TestClient
from pytest import MonkeyPatch


_MAX_IMAGE_SIZE = 10 * 1024 * 1024
_MAX_DOC_SIZE = 20 * 1024 * 1024


def _mock_judge_dependencies(monkeypatch: MonkeyPatch) -> None:
    async def _fake_grade_image(*_args: object, **_kwargs: object) -> dict[str, object]:
        return {
            "question_type": "short_answer",
            "recognized_content": "mock",
            "judgment": "correct",
            "score": 1,
            "total_score": 1,
            "explanation": "mock",
        }

    def _fake_compress_and_encode(_path: str) -> str:
        return "mock-b64"

    monkeypatch.setattr("backend.routers.judge.compress_and_encode", _fake_compress_and_encode)
    monkeypatch.setattr("backend.routers.judge.grade_image", _fake_grade_image)


def _mock_upload_dependencies(monkeypatch: MonkeyPatch) -> None:
    async def _fake_build_import_bundles(
        *_args: object,
        **_kwargs: object,
    ) -> tuple[str, list[object], list[object]]:
        return "summary", [], []

    monkeypatch.setattr(
        "backend.routers.upload.build_import_bundles",
        _fake_build_import_bundles,
    )


def test_judge_rejects_oversized_image(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    _mock_judge_dependencies(monkeypatch)

    response = client.post(
        "/api/judge",
        files={
            "image": (
                "too-large.jpg",
                BytesIO(b"x" * (_MAX_IMAGE_SIZE + 1)),
                "image/jpeg",
            ),
        },
    )

    assert response.status_code == 400
    assert "图片大小超过限制" in response.json()["detail"]


def test_judge_rejects_invalid_content_type(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    _mock_judge_dependencies(monkeypatch)

    response = client.post(
        "/api/judge",
        files={
            "image": (
                "invalid-content-type.jpg",
                BytesIO(b"not-image"),
                "application/pdf",
            ),
        },
    )

    assert response.status_code == 400
    assert "不支持的图片格式" in response.json()["detail"]


def test_upload_rejects_invalid_extension(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    _mock_upload_dependencies(monkeypatch)

    response = client.post(
        "/api/upload/document",
        files={
            "files": (
                "invalid.txt",
                BytesIO(b"hello"),
                "text/plain",
            ),
        },
    )

    assert response.status_code == 400
    assert "不支持的文件类型" in response.json()["detail"]


def test_upload_rejects_oversized_doc(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    _mock_upload_dependencies(monkeypatch)

    response = client.post(
        "/api/upload/document",
        files={
            "files": (
                "too-large.pdf",
                BytesIO(b"x" * (_MAX_DOC_SIZE + 1)),
                "application/pdf",
            ),
        },
    )

    assert response.status_code == 400
    assert "文档大小超过限制" in response.json()["detail"]
