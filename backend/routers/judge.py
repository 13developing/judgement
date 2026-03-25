"""Grading endpoints — the core user-facing API."""

from __future__ import annotations

import json
import re
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


def _recognized_as_blank(recognized_content: str) -> bool:
    normalized = (recognized_content or "").replace(" ", "")
    return "学生作答：空白" in normalized or "学生作答：未作答" in normalized


def _recognized_has_answer_work(recognized_content: str) -> bool:
    content = recognized_content or ""
    match = re.search(r"学生作答[：:](.*)", content, re.S)
    if not match:
        return False
    answer_part = match.group(1).strip()
    if not answer_part:
        return False
    blank_markers = ("空白", "未作答", "未填写", "未答")
    if any(marker in answer_part for marker in blank_markers):
        return False
    return True


def _force_blank_result(result: dict) -> dict:
    fixed = dict(result)
    fixed["judgment"] = "wrong"
    fixed["score"] = 0
    fixed["explanation"] = "图片中学生未填写答案，判为未作答，不应按标准答案给分。"
    if fixed.get("steps"):
        fixed["steps"] = []
    return fixed


def _prepend_explanation(explanation: str, prefix: str) -> str:
    explanation = explanation or ""
    return f"{prefix}\n\n{explanation}" if explanation else prefix


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
    first_pass_result = await grade_image(img_b64)
    result = first_pass_result
    if standard_answer:
        result = await grade_image(img_b64, standard_answer)
        first_recognized = first_pass_result.get("recognized_content", "")
        second_recognized = result.get("recognized_content", "")
        result["recognized_content"] = second_recognized if _recognized_has_answer_work(second_recognized) else first_recognized
        if _recognized_as_blank(first_recognized) and not _recognized_has_answer_work(second_recognized):
            result = _force_blank_result(result)
        result["explanation"] = _prepend_explanation(
            result.get("explanation", ""),
            f"手动输入标准答案：{standard_answer}（综合点评与评分均以手动输入为主；若模型判断不同，会在下文说明差异）",
        )
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
    first_pass_result = await grade_image(img_b64)
    result = first_pass_result

    # Try to match to question bank
    matched = await find_matching_question(session, result.get("recognized_content", ""))
    std_answer: str | None = None
    if matched and matched.standard_answer:
        std_answer = matched.standard_answer
        # Second pass: re-grade with the matched standard answer
        result = await grade_image(img_b64, std_answer)
        first_recognized = first_pass_result.get("recognized_content", "")
        second_recognized = result.get("recognized_content", "")
        result["recognized_content"] = second_recognized if _recognized_has_answer_work(second_recognized) else first_recognized
        if _recognized_as_blank(first_recognized) and not _recognized_has_answer_work(second_recognized):
            result = _force_blank_result(result)
        result["explanation"] = _prepend_explanation(
            result.get("explanation", ""),
            f"题库标准答案：{std_answer}",
        )
    else:
        result["explanation"] = _prepend_explanation(
            result.get("explanation", ""),
            "未在题库中搜索到可用标准答案。",
        )

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
