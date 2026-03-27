"""LLM usage metrics endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from backend.services.llm_metrics import get_usage

router = APIRouter(prefix="/api/metrics", tags=["监控指标"])


@router.get("/llm")
async def llm_usage_metrics() -> dict[str, int]:
    """Return accumulated LLM token usage statistics."""
    return get_usage()
