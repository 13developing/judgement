"""Grading history export endpoints."""

from __future__ import annotations

import csv
import io
from collections.abc import Sequence
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select

from backend.database import get_session
from backend.models import JudgeResult

router = APIRouter(prefix="/api/export", tags=["数据导出"])


@router.get("/results")
def export_results(
    session: Annotated[Session, Depends(get_session)],
    format: Annotated[Literal["json", "csv"], Query(description="导出格式")] = "json",
    limit: Annotated[int, Query(ge=1, le=1000, description="最大导出条数")] = 100,
):
    """Export grading history as JSON or CSV."""
    stmt = (
        select(JudgeResult)
        .order_by(JudgeResult.created_at.desc())  # type: ignore[union-attr] # pyright: ignore[reportAttributeAccessIssue,reportUnknownMemberType,reportUnknownArgumentType]
        .limit(limit)
    )
    results = session.exec(stmt).all()

    if format == "csv":
        return _export_csv(results)
    return _export_json(results)


def _export_json(results: Sequence[JudgeResult]) -> list[dict[str, object | None]]:
    """Return results as JSON array."""
    return [
        {
            "id": r.id,
            "score": r.score,
            "total_score": r.total_score,
            "question_type": r.question_type,
            "judgment": r.judgment,
            "recognized_content": r.recognized_content,
            "explanation": r.explanation,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in results
    ]


def _export_csv(results: Sequence[JudgeResult]) -> StreamingResponse:
    """Return results as CSV download."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "得分", "总分", "题型", "判定", "识别内容", "点评", "创建时间"])
    for r in results:
        writer.writerow(
            [
                r.id,
                r.score,
                r.total_score,
                r.question_type,
                r.judgment,
                (r.recognized_content or "")[:200],
                (r.explanation or "")[:200],
                r.created_at.isoformat() if r.created_at else "",
            ]
        )
    _ = output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=grading_results.csv"},
    )
