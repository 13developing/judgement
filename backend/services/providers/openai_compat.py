"""OpenAI-compatible fallback provider."""

from __future__ import annotations

from backend.config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL
from backend.services.providers.base import LLMProvider

_DEFAULT_BASE_URL = "https://api.openai.com/v1"
_DEFAULT_MODEL = "gpt-4o-mini"


class OpenAICompatProvider(LLMProvider):
    """Fallback provider — any OpenAI-compatible service.

    Works out-of-the-box with OpenAI, Azure OpenAI, or third-party
    proxies that expose the ``/chat/completions`` endpoint.
    """

    @property
    def api_key(self) -> str:
        return LLM_API_KEY

    @property
    def base_url(self) -> str:
        return LLM_BASE_URL or _DEFAULT_BASE_URL

    @property
    def model(self) -> str:
        return LLM_MODEL or _DEFAULT_MODEL
