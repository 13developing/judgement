from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from backend.services.llm_metrics import get_usage, reset_usage  # pyright: ignore[reportMissingImports]
from backend.services.providers import base as base_module
from backend.services.providers.base import LLMProvider


class _TestProvider(LLMProvider):
    @property
    def api_key(self) -> str:
        return "test-key"

    @property
    def base_url(self) -> str:
        return "https://test.example.com/v1"

    @property
    def model(self) -> str:
        return "test-model"


@pytest.mark.asyncio
async def test_retry_on_transient_failure() -> None:
    """Verify retry logic on transient HTTP errors."""
    reset_usage()
    provider = _TestProvider()

    fail_response = MagicMock()
    fail_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "502",
        request=httpx.Request("POST", "https://test.example.com"),
        response=httpx.Response(502),
    )

    success_data = {
        "choices": [{"message": {"content": "ok"}}],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "total_tokens": 15,
        },
    }
    ok_response = MagicMock()
    ok_response.raise_for_status.return_value = None
    ok_response.json.return_value = success_data

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=[fail_response, fail_response, ok_response])

    with patch("backend.services.providers.base.get_http_client", return_value=mock_client):
        with patch("backend.services.providers.base.asyncio.sleep", new_callable=AsyncMock):
            result = await provider.chat_text("sys", "user")

    assert result == "ok"
    assert mock_client.post.call_count == 3
    assert get_usage()["total_tokens"] == 15


@pytest.mark.asyncio
async def test_concurrency_is_limited_by_semaphore() -> None:
    """Ensure only configured number of requests run concurrently."""
    reset_usage()
    provider = _TestProvider()

    in_flight = 0
    max_in_flight = 0

    async def _post(*args: object, **kwargs: object) -> MagicMock:
        nonlocal in_flight, max_in_flight
        in_flight += 1
        max_in_flight = max(max_in_flight, in_flight)
        await asyncio.sleep(0.05)
        in_flight -= 1

        response = MagicMock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "choices": [{"message": {"content": "ok"}}],
            "usage": {
                "prompt_tokens": 1,
                "completion_tokens": 1,
                "total_tokens": 2,
            },
        }
        return response

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=_post)

    with patch("backend.services.providers.base.get_http_client", return_value=mock_client):
        with patch.object(base_module, "LLM_MAX_CONCURRENT", 1):
            with patch.object(base_module, "_semaphore", None):
                await asyncio.gather(
                    provider.chat_text("sys", "user-a"),
                    provider.chat_text("sys", "user-b"),
                )

    assert max_in_flight == 1
