"""Grading endpoints — the core user-facing API."""

from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlmodel import Session

from backend.config import UPLOAD_DIR
from backend.database import get_session
from backend.models import JudgeResult
from backend.schemas import JudgeResponse
from backend.services.grading import grade_image
from backend.services.question_matcher import find_matching_question
from backend.utils.image import compress_and_encode

router = APIRouter(prefix="/api/judge", tags=["判题"])


def _save_upload(image: UploadFile) -> Path:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    ext = Path(image.filename or "upload.png").suffix or ".png"
    dest = UPLOAD_DIR / f"{uuid.uuid4().hex}{ext}"
    with open(dest, "wb") as f:
        shutil.copyfileobj(image.file, f)
    return dest


def _to_response(result: dict) -> JudgeResponse:
    return JudgeResponse(
        question_type=result.get("question_type", "unknown"),
        recognized_content=result.get("recognized_content", ""),
        judgment=result.get("judgment", "unknown"),
        score=result.get("score", 0),
        total_score=result.get("total_score", 10),
        explanation=result.get("explanation", ""),
        steps=result.get("steps"),
    )


def _save_record(
    session: Session,
    result: dict,
    image_path: str,
    *,
    standard_answer: str | None = None,
    matched_id: int | None = None,
) -> None:
    record = JudgeResult(
        image_path=image_path,
        question_type=result.get("question_type", "unknown"),
        recognized_content=result.get("recognized_content", ""),
        judgment=result.get("judgment", "unknown"),
        score=result.get("score", 0),
        total_score=result.get("total_score", 10),
        explanation=result.get("explanation", ""),
        step_scores=json.dumps(result.get("steps"), ensure_ascii=False)
        if result.get("steps")
        else None,
        matched_question_id=matched_id,
        standard_answer_used=standard_answer,
    )
    session.add(record)
    session.commit()


# ── POST /api/judge ──────────────────────────────────────────────────────


@router.post("", response_model=JudgeResponse)
async def judge_exam(
    image: UploadFile = File(...),
    standard_answer: str = Form(None),
    session: Session = Depends(get_session),
) -> JudgeResponse:
    """Upload an image with an optional standard answer and get a grading result."""
    dest = _save_upload(image)
    img_b64 = compress_and_encode(str(dest))
    result = await grade_image(img_b64, standard_answer or None)
    _save_record(session, result, str(dest), standard_answer=standard_answer)
    return _to_response(result)


# ── POST /api/judge/with-bank ────────────────────────────────────────────


@router.post("/with-bank", response_model=JudgeResponse)
async def judge_with_bank(
    image: UploadFile = File(...),
    session: Session = Depends(get_session),
) -> JudgeResponse:
    """Upload an image — auto-match to the question bank, then grade."""
    dest = _save_upload(image)
    img_b64 = compress_and_encode(str(dest))

    # First pass: recognise content without answer
    result = await grade_image(img_b64)

    # Try to match to question bank
    matched = find_matching_question(session, result.get("recognized_content", ""))
    std_answer: str | None = None
    if matched and matched.standard_answer:
        std_answer = matched.standard_answer
        # Second pass: re-grade with the matched standard answer
        result = await grade_image(img_b64, std_answer)

    _save_record(
        session,
        result,
        str(dest),
        standard_answer=std_answer,
        matched_id=matched.id if matched else None,
    )
    return _to_response(result)


# ── GET /api/judge/results ───────────────────────────────────────────────


@router.get("/results")
def list_results(
    offset: int = 0,
    limit: int = 20,
    session: Session = Depends(get_session),
) -> list[dict]:
    """Return recent grading records."""
    from sqlmodel import select

    stmt = (
        select(JudgeResult)
        .order_by(JudgeResult.created_at.desc())  # type: ignore[union-attr]
        .offset(offset)
        .limit(limit)
    )
    records = session.exec(stmt).all()
    return [
        {
            "id": r.id,
            "question_type": r.question_type,
            "judgment": r.judgment,
            "score": r.score,
            "total_score": r.total_score,
            "explanation": r.explanation,
            "created_at": r.created_at.isoformat() if r.created_at else "",
        }
        for r in records
    ]
