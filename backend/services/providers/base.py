"""Base LLM provider with OpenAI-compatible Chat Completions implementation."""

from __future__ import annotations

from abc import ABC, abstractmethod

import httpx


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

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                self._completions_url(),
                headers=self._headers(),
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
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

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                self._completions_url(),
                headers=self._headers(),
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
