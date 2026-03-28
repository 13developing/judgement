"""Base LLM provider with OpenAI-compatible Chat Completions implementation."""

from __future__ import annotations

import asyncio
import logging
import random
from abc import ABC, abstractmethod
from typing import Any

import httpx

from backend.config import LLM_MAX_CONCURRENT, LLM_MAX_RETRIES, LLM_RETRY_BASE_DELAY
from backend.services.http_client import get_http_client
from backend.services.llm_metrics import record_usage  # pyright: ignore[reportMissingImports]

log = logging.getLogger(__name__)
_semaphore: asyncio.Semaphore | None = None


def _get_semaphore() -> asyncio.Semaphore:
    global _semaphore  # noqa: PLW0603
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(LLM_MAX_CONCURRENT)
    return _semaphore


class LLMProvider(ABC):
    """Abstract base for LLM service providers.

    Concrete subclasses only need to supply default config via properties.
    The HTTP transport uses the OpenAI-compatible Chat Completions format,
    which is shared by most major providers (OpenAI, Volcengine Ark, etc.).
    Override ``chat_with_image`` / ``chat_text`` if a provider requires a
    non-standard request format.

    Subclasses may be instantiated with explicit ``api_key``, ``base_url``,
    and ``model`` keyword arguments.  When given, those values take priority
    over environment-variable defaults so that DB-managed configurations can
    override ``.env`` settings at runtime.
    """

    def __init__(
        self,
        *,
        api_key: str = "",
        base_url: str = "",
        model: str = "",
    ) -> None:
        self._override_api_key = api_key
        self._override_base_url = base_url
        self._override_model = model

    # -- Subclasses MUST implement these properties --------------------------

    @property
    @abstractmethod
    def api_key(self) -> str: ...

    @property
    @abstractmethod
    def base_url(self) -> str: ...

    @property
    @abstractmethod
    def model(self) -> str: ...

    # -- Shared OpenAI-compatible implementation -----------------------------

    def _headers(self) -> dict[str, str]:
        key = self.api_key
        if not key:
            raise ValueError(
                "LLM API key 未配置。请设置环境变量 LLM_API_KEY（或 OPENAI_API_KEY）后重试。"
            )
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
        }

    def _completions_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/chat/completions"

    async def _request_with_retry(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Send request with exponential backoff retry and concurrency limit."""
        client = get_http_client()
        sem = _get_semaphore()
        last_exc: Exception | None = None

        for attempt in range(LLM_MAX_RETRIES):
            async with sem:
                try:
                    resp = await client.post(
                        self._completions_url(),
                        headers=self._headers(),
                        json=payload,
                    )
                    resp.raise_for_status()
                    data = resp.json()

                    usage = data.get("usage", {})
                    if usage:
                        record_usage(
                            prompt_tokens=int(usage.get("prompt_tokens", 0) or 0),
                            completion_tokens=int(usage.get("completion_tokens", 0) or 0),
                            total_tokens=int(usage.get("total_tokens", 0) or 0),
                        )

                    return data
                except (httpx.HTTPStatusError, httpx.RequestError, httpx.TimeoutException) as exc:
                    last_exc = exc
                    if attempt < LLM_MAX_RETRIES - 1:
                        delay = LLM_RETRY_BASE_DELAY * (2**attempt) + random.uniform(0, 0.5)
                        log.warning(
                            "LLM request failed (attempt %d/%d): %s. Retrying in %.1fs...",
                            attempt + 1,
                            LLM_MAX_RETRIES,
                            exc,
                            delay,
                        )
                        await asyncio.sleep(delay)

        if last_exc is not None:
            raise last_exc

        raise RuntimeError("LLM request failed without a captured exception")

    async def chat_with_image(
        self,
        system_prompt: str,
        user_prompt: str,
        image_base64: str,
        *,
        temperature: float = 0.1,
        max_tokens: int = 4000,
    ) -> str:
        """Send a multimodal (text + image) request and return the assistant reply."""
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_base64}",
                                "detail": "auto",
                            },
                        },
                    ],
                },
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        data = await self._request_with_retry(payload)
        return data["choices"][0]["message"]["content"]

    async def chat_with_images(
        self,
        system_prompt: str,
        user_prompt: str,
        image_base64_list: list[str],
        *,
        temperature: float = 0.1,
        max_tokens: int = 4000,
    ) -> str:
        """Send a multimodal request containing multiple images."""
        content: list[dict[str, Any]] = [{"type": "text", "text": user_prompt}]
        for image_base64 in image_base64_list:
            content.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{image_base64}",
                        "detail": "auto",
                    },
                }
            )

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": content},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        data = await self._request_with_retry(payload)
        return data["choices"][0]["message"]["content"]

    async def chat_text(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float = 0.1,
        max_tokens: int = 4000,
    ) -> str:
        """Send a text-only request and return the assistant reply."""
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        data = await self._request_with_retry(payload)
        return data["choices"][0]["message"]["content"]
