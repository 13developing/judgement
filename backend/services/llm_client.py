"""Thin façade that delegates to the active LLM provider.

Downstream code should keep importing from here::

    from backend.services.llm_client import chat_with_image, chat_text
"""

from __future__ import annotations

from backend.services.providers import get_provider


async def chat_with_image(
    system_prompt: str,
    user_prompt: str,
    image_base64: str,
    *,
    temperature: float = 0.1,
    max_tokens: int = 4000,
) -> str:
    """Send a multimodal (text + image) request and return the assistant reply."""
    provider = get_provider()
    return await provider.chat_with_image(
        system_prompt,
        user_prompt,
        image_base64,
        temperature=temperature,
        max_tokens=max_tokens,
    )


async def chat_with_images(
    system_prompt: str,
    user_prompt: str,
    image_base64_list: list[str],
    *,
    temperature: float = 0.1,
    max_tokens: int = 4000,
) -> str:
    """Send a multimodal request with multiple images and return the reply."""
    provider = get_provider()
    return await provider.chat_with_images(
        system_prompt,
        user_prompt,
        image_base64_list,
        temperature=temperature,
        max_tokens=max_tokens,
    )


async def chat_text(
    system_prompt: str,
    user_prompt: str,
    *,
    temperature: float = 0.1,
    max_tokens: int = 4000,
) -> str:
    """Send a text-only request and return the assistant reply."""
    provider = get_provider()
    return await provider.chat_text(
        system_prompt,
        user_prompt,
        temperature=temperature,
        max_tokens=max_tokens,
    )
