"""LLM provider factory.

Usage::

    from backend.services.providers import get_provider

    provider = get_provider()
    answer = await provider.chat_with_image(system, user, img_b64)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from backend.config import LLM_PROVIDER

if TYPE_CHECKING:
    from backend.services.providers.base import LLMProvider

log = logging.getLogger(__name__)

_REGISTRY: dict[str, type[LLMProvider]] = {}
_instance: LLMProvider | None = None


def _ensure_registry() -> dict[str, type[LLMProvider]]:
    """Lazy-import concrete providers to avoid circular imports."""
    if not _REGISTRY:
        from backend.services.providers.ark import ArkProvider
        from backend.services.providers.openai_compat import OpenAICompatProvider

        _REGISTRY["ark"] = ArkProvider
        _REGISTRY["openai"] = OpenAICompatProvider
    return _REGISTRY


def get_provider() -> LLMProvider:
    """Return the singleton ``LLMProvider`` determined by ``LLM_PROVIDER``."""
    global _instance  # noqa: PLW0603
    if _instance is not None:
        return _instance

    registry = _ensure_registry()
    provider_cls = registry.get(LLM_PROVIDER)
    if provider_cls is None:
        log.warning(
            "Unknown LLM_PROVIDER=%r, falling back to 'ark'",
            LLM_PROVIDER,
        )
        provider_cls = registry["ark"]

    _instance = provider_cls()
    log.info(
        "LLM provider initialised: %s (model=%s)",
        type(_instance).__name__,
        _instance.model,
    )
    return _instance
