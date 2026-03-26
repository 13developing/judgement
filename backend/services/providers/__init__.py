"""LLM provider factory — DB-first with .env fallback.

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

# Cache: (provider_instance, config_id_or_None)
# config_id tracks which DB row was used so we can invalidate on change.
_instance: LLMProvider | None = None
_active_config_id: int | None = None


def _ensure_registry() -> dict[str, type[LLMProvider]]:
    """Lazy-import concrete providers to avoid circular imports."""
    if not _REGISTRY:
        from backend.services.providers.ark import ArkProvider
        from backend.services.providers.openai_compat import OpenAICompatProvider

        _REGISTRY["ark"] = ArkProvider
        _REGISTRY["openai"] = OpenAICompatProvider
    return _REGISTRY


def _load_from_db() -> tuple[int, str, str, str, str] | None:
    """Try to read the active ProviderConfig from the database.

    Returns ``(id, provider_type, api_key_plain, base_url, model)``
    or *None* if no active config exists.
    """
    try:
        from sqlmodel import Session, select

        from backend.database import engine
        from backend.models import ProviderConfig
        from backend.services.encryption import decrypt

        with Session(engine) as session:
            stmt = select(ProviderConfig).where(ProviderConfig.is_active == True)  # noqa: E712
            config = session.exec(stmt).first()
            if config is None:
                return None
            api_key = decrypt(config.api_key_encrypted)
            return (
                config.id,  # type: ignore[arg-type]
                config.provider_type,
                api_key,
                config.base_url,
                config.model,
            )
    except Exception:
        # DB not ready, table missing, etc. — fall through to env.
        log.debug("无法从数据库加载 Provider 配置，将使用环境变量。", exc_info=True)
        return None


def invalidate_cache() -> None:
    """Force the next ``get_provider()`` call to re-read configuration.

    Called by the provider-management router whenever configurations change.
    """
    global _instance, _active_config_id  # noqa: PLW0603
    _instance = None
    _active_config_id = None
    log.info("Provider 缓存已清除，下次调用将重新加载配置。")


def get_provider() -> LLMProvider:
    """Return the current ``LLMProvider``.

    Resolution order:

    1. If a cached instance exists **and** the active DB row hasn't changed,
       return the cached instance.
    2. Query the DB for an active ``ProviderConfig``.  If found, decrypt the
       API key and instantiate the matching provider class with explicit
       config values.
    3. Fall back to ``.env`` / ``backend.config`` module constants.
    """
    global _instance, _active_config_id  # noqa: PLW0603

    registry = _ensure_registry()

    # ── Try DB-managed config ────────────────────────────────────────
    db_row = _load_from_db()
    if db_row is not None:
        cfg_id, provider_type, api_key, base_url, model = db_row

        # Cache hit — same config row, reuse instance.
        if _instance is not None and _active_config_id == cfg_id:
            return _instance

        provider_cls = registry.get(provider_type)
        if provider_cls is None:
            log.warning(
                "DB 中 provider_type=%r 未知，回退到 'ark'",
                provider_type,
            )
            provider_cls = registry["ark"]

        _instance = provider_cls(api_key=api_key, base_url=base_url, model=model)
        _active_config_id = cfg_id
        log.info(
            "LLM provider 从数据库加载: %s (model=%s, config_id=%s)",
            type(_instance).__name__,
            _instance.model,
            cfg_id,
        )
        return _instance

    # ── Fallback to env ──────────────────────────────────────────────
    if _instance is not None and _active_config_id is None:
        return _instance

    provider_cls = registry.get(LLM_PROVIDER)
    if provider_cls is None:
        log.warning(
            "Unknown LLM_PROVIDER=%r, falling back to 'ark'",
            LLM_PROVIDER,
        )
        provider_cls = registry["ark"]

    _instance = provider_cls()
    _active_config_id = None
    log.info(
        "LLM provider 从环境变量加载: %s (model=%s)",
        type(_instance).__name__,
        _instance.model,
    )
    return _instance
