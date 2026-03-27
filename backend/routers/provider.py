"""Provider configuration management — CRUD, activate, test."""

from __future__ import annotations

from datetime import datetime
from typing import Any, cast

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from backend.database import get_session
from backend.models import ProviderConfig
from backend.schemas import (
    ProviderConfigCreate,
    ProviderConfigOut,
    ProviderConfigUpdate,
    ProviderTestRequest,
)
from backend.services.encryption import decrypt, encrypt, mask_key
from backend.services.http_client import get_http_client
from backend.services.providers import invalidate_cache

router = APIRouter(prefix="/api/providers", tags=["Provider 管理"])

# Supported provider types and their defaults.
_PROVIDER_DEFAULTS: dict[str, dict[str, str]] = {
    "ark": {
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "model": "doubao-seed-2-0-lite-260215",
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
    },
}

_VALID_TYPES = set(_PROVIDER_DEFAULTS)


# ── Helpers ──────────────────────────────────────────────────────────────


def _row_to_out(row: ProviderConfig) -> ProviderConfigOut:
    """Convert a DB row to a public response object (key masked)."""
    provider_id = row.id
    if provider_id is None:
        raise HTTPException(status_code=500, detail="Provider 配置数据异常：缺少 ID")

    plain_key = decrypt(row.api_key_encrypted)
    return ProviderConfigOut(
        id=provider_id,
        name=row.name,
        provider_type=row.provider_type,
        api_key_masked=mask_key(plain_key),
        base_url=row.base_url,
        model=row.model,
        is_active=row.is_active,
        created_at=row.created_at.isoformat(),
        updated_at=row.updated_at.isoformat(),
    )


def _resolve_defaults(provider_type: str, base_url: str, model: str) -> tuple[str, str]:
    """Fill empty base_url / model with provider-specific defaults."""
    defaults = _PROVIDER_DEFAULTS.get(provider_type, {})
    return (
        base_url or defaults.get("base_url", ""),
        model or defaults.get("model", ""),
    )


async def _test_provider_connection(
    provider_type: str,
    api_key: str,
    base_url: str,
    model: str,
) -> dict[str, str]:
    """Send a lightweight chat completion to verify the credentials.

    Returns ``{"status": "ok", "model": ...}`` on success, or raises
    ``HTTPException(502)`` on failure.
    """
    base_url, model = _resolve_defaults(provider_type, base_url, model)
    url = f"{base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "Hi"}],
        "max_tokens": 8,
        "temperature": 0,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    try:
        client = get_http_client()
        resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        return {"status": "ok", "model": model}
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text[:300] if exc.response else str(exc)
        raise HTTPException(
            status_code=502,
            detail=f"连接测试失败 (HTTP {exc.response.status_code}): {detail}",
        ) from exc
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"连接测试失败: {exc}",
        ) from exc


# ── Endpoints ────────────────────────────────────────────────────────────

# Static routes MUST be defined before parametric /{provider_id} routes
# so that FastAPI matches "/test" and "/types" as literals, not as IDs.


@router.get("/types")
def list_provider_types() -> dict[str, dict[str, str]]:
    """Return supported provider types with their default base_url and model."""
    return _PROVIDER_DEFAULTS


@router.post("/test")
async def test_provider_inline(body: ProviderTestRequest) -> dict[str, str]:
    """Test provider connectivity with credentials provided inline.

    Useful for verifying credentials *before* saving them.
    """
    if body.provider_type not in _VALID_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的 provider 类型: {body.provider_type!r}",
        )
    return await _test_provider_connection(
        body.provider_type,
        body.api_key,
        body.base_url,
        body.model,
    )


@router.get("", response_model=list[ProviderConfigOut])
def list_providers(
    session: Session = Depends(get_session),
) -> list[ProviderConfigOut]:
    """List all provider configurations (API keys masked)."""
    rows = session.exec(select(ProviderConfig).order_by(cast(Any, ProviderConfig.id))).all()
    return [_row_to_out(r) for r in rows]


@router.post("", response_model=ProviderConfigOut, status_code=201)
def create_provider(
    body: ProviderConfigCreate,
    session: Session = Depends(get_session),
) -> ProviderConfigOut:
    """Create a new provider configuration."""
    if body.provider_type not in _VALID_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的 provider 类型: {body.provider_type!r}，可选: {sorted(_VALID_TYPES)}",
        )

    base_url, model = _resolve_defaults(body.provider_type, body.base_url, body.model)

    row = ProviderConfig(
        name=body.name,
        provider_type=body.provider_type,
        api_key_encrypted=encrypt(body.api_key),
        base_url=base_url,
        model=model,
        is_active=False,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return _row_to_out(row)


@router.put("/{provider_id}", response_model=ProviderConfigOut)
def update_provider(
    provider_id: int,
    body: ProviderConfigUpdate,
    session: Session = Depends(get_session),
) -> ProviderConfigOut:
    """Update an existing provider configuration."""
    row = session.get(ProviderConfig, provider_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Provider 配置不存在")

    if body.provider_type is not None:
        if body.provider_type not in _VALID_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"不支持的 provider 类型: {body.provider_type!r}",
            )
        row.provider_type = body.provider_type

    if body.name is not None:
        row.name = body.name
    if body.api_key is not None:
        row.api_key_encrypted = encrypt(body.api_key)
    if body.base_url is not None:
        row.base_url = body.base_url
    if body.model is not None:
        row.model = body.model

    row.updated_at = datetime.now()
    session.add(row)
    session.commit()
    session.refresh(row)

    # Invalidate cached provider if this row was active.
    if row.is_active:
        invalidate_cache()

    return _row_to_out(row)


@router.delete("/{provider_id}")
def delete_provider(
    provider_id: int,
    session: Session = Depends(get_session),
) -> dict[str, str]:
    """Delete a provider configuration."""
    row = session.get(ProviderConfig, provider_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Provider 配置不存在")

    was_active = row.is_active
    session.delete(row)
    session.commit()

    if was_active:
        invalidate_cache()

    return {"detail": "已删除"}


@router.post("/{provider_id}/activate", response_model=ProviderConfigOut)
def activate_provider(
    provider_id: int,
    session: Session = Depends(get_session),
) -> ProviderConfigOut:
    """Set this provider as the active one (deactivates all others)."""
    row = session.get(ProviderConfig, provider_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Provider 配置不存在")

    # Deactivate all.
    all_rows = session.exec(select(ProviderConfig)).all()
    for r in all_rows:
        r.is_active = False
        session.add(r)

    row.is_active = True
    row.updated_at = datetime.now()
    session.add(row)
    session.commit()
    session.refresh(row)

    invalidate_cache()
    return _row_to_out(row)


@router.post("/{provider_id}/deactivate", response_model=ProviderConfigOut)
def deactivate_provider(
    provider_id: int,
    session: Session = Depends(get_session),
) -> ProviderConfigOut:
    """Deactivate this provider (system will fall back to .env config)."""
    row = session.get(ProviderConfig, provider_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Provider 配置不存在")

    row.is_active = False
    row.updated_at = datetime.now()
    session.add(row)
    session.commit()
    session.refresh(row)

    invalidate_cache()
    return _row_to_out(row)


@router.post("/{provider_id}/test")
async def test_saved_provider(
    provider_id: int,
    session: Session = Depends(get_session),
) -> dict[str, str]:
    """Test a saved provider's connectivity using its stored credentials."""
    row = session.get(ProviderConfig, provider_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Provider 配置不存在")

    api_key = decrypt(row.api_key_encrypted)
    return await _test_provider_connection(
        row.provider_type,
        api_key,
        row.base_url,
        row.model,
    )
