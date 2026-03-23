"""Volcengine Ark provider — 豆包 (Doubao) series models."""

from __future__ import annotations

from backend.config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL
from backend.services.providers.base import LLMProvider

# Ark OpenAI-compatible endpoint
_DEFAULT_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
_DEFAULT_MODEL = "doubao-seed-2-0-lite-260215"


class ArkProvider(LLMProvider):
    """Primary LLM provider — ByteDance Volcengine Ark (豆包).

    Uses the OpenAI-compatible Chat Completions interface provided by Ark,
    so no special request format is required.  Override methods here if a
    future Ark-specific feature (e.g. the Responses API) is needed.
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
