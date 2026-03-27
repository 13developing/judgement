from __future__ import annotations

from typing import cast

from fastapi.testclient import TestClient

from backend.main import app

_ERROR_TEST_PATH = "/__middleware_error_test__"


def test_request_id_generated(client: TestClient) -> None:
    response = client.get("/api/questions")

    assert response.status_code == 200
    request_id = cast(str, response.headers.get("X-Request-ID", ""))
    assert request_id != ""


def test_request_id_passthrough(client: TestClient) -> None:
    response = client.get("/api/questions", headers={"X-Request-ID": "test-123"})

    assert response.status_code == 200
    response_request_id = cast(str | None, response.headers.get("X-Request-ID"))
    assert response_request_id == "test-123"


def test_cors_headers(client: TestClient) -> None:
    response = client.options(
        "/api/questions",
        headers={
            "Origin": "http://example.com",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code in {200, 204}
    assert "access-control-allow-origin" in response.headers
    assert "access-control-allow-methods" in response.headers
    allow_methods = cast(str, response.headers.get("access-control-allow-methods", ""))
    assert "GET" in allow_methods


def _raise_unhandled_error() -> None:
    raise RuntimeError("middleware error test")


def test_error_handler_returns_json() -> None:
    app.add_api_route(_ERROR_TEST_PATH, _raise_unhandled_error, methods=["GET"])

    try:
        with TestClient(app, raise_server_exceptions=False) as local_client:
            response = local_client.get(_ERROR_TEST_PATH)

        assert response.status_code == 500
        content_type = cast(str, response.headers.get("content-type", ""))
        assert content_type.startswith("application/json")
        assert response.json() == {"detail": "服务器内部错误，请稍后重试。"}
    finally:
        app.router.routes[:] = [
            route for route in app.router.routes if getattr(route, "path", None) != _ERROR_TEST_PATH
        ]
