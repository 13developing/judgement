"""Health check endpoints for monitoring and orchestration."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from backend.database import get_session

router = APIRouter(tags=["健康检查"])


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Basic liveness probe — always returns OK if the process is running."""
    return {"status": "ok"}


@router.get("/ready")
def readiness_check(session: Annotated[Session, Depends(get_session)]) -> dict[str, str]:
    """Readiness probe — verifies database connectivity."""
    try:
        _ = session.exec(select(1)).one()
        return {"status": "ready", "database": "ok"}
    except Exception as exc:
        raise HTTPException(status_code=503, detail="数据库连接失败") from exc
