"""Grading endpoints — the core user-facing API."""

from __future__ import annotations

import json
import re
import shutil
import uuid
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Annotated, cast

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlmodel import Session

from backend.config import UPLOAD_DIR
from backend.database import get_session
from backend.models import JudgeResult
from backend.schemas import JudgeResponse, StepDetail
from backend.services.grading import grade_image
from backend.services.question_matcher import find_matching_question
from backend.utils.image import compress_and_encode

router = APIRouter(prefix="/api/judge", tags=["判题"])

_MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10 MB
_ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
ResultDict = dict[str, object]
grade_answer = cast(Callable[[str, str | None], Awaitable[ResultDict]], grade_image)


def _as_str(value: object, default: str = "") -> str:
    return value if isinstance(value, str) else default


def _as_int(value: object, default: int = 0) -> int:
    return value if isinstance(value, int) else default


def _as_steps(value: object) -> list[StepDetail] | None:
    if not isinstance(value, list):
        return None

    normalized: list[StepDetail] = []
    for item in cast(list[object], value):
        if isinstance(item, StepDetail):
            normalized.append(item)
            continue
        if not isinstance(item, dict):
            return None
        try:
            normalized.append(StepDetail.model_validate(item))
        except Exception:
            return None
    return normalized


async def _validate_image(image: UploadFile) -> None:
    """Validate uploaded image: size limit and content type."""
    if image.content_type and image.content_type not in _ALLOWED_IMAGE_TYPES:
        raise HTTPException(400, f"不支持的图片格式: {image.content_type}")

    content = await image.read()
    if len(content) > _MAX_IMAGE_SIZE:
        raise HTTPException(
            400,
            f"图片大小超过限制（最大 10MB，当前 {len(content) / 1024 / 1024:.1f}MB）",
        )
    await image.seek(0)


def _save_upload(image: UploadFile) -> Path:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    ext = Path(image.filename or "upload.png").suffix or ".png"
    dest = UPLOAD_DIR / f"{uuid.uuid4().hex}{ext}"
    with open(dest, "wb") as f:
        shutil.copyfileobj(image.file, f)
    return dest


def _to_response(result: ResultDict) -> JudgeResponse:
    steps = _as_steps(result.get("steps"))
    return JudgeResponse(
        question_type=_as_str(result.get("question_type"), "unknown"),
        recognized_content=_as_str(result.get("recognized_content"), ""),
        judgment=_as_str(result.get("judgment"), "unknown"),
        score=_as_int(result.get("score"), 0),
        total_score=_as_int(result.get("total_score"), 10),
        explanation=_as_str(result.get("explanation"), ""),
        steps=steps,
    )


def _save_record(
    session: Session,
    result: ResultDict,
    image_path: str,
    *,
    standard_answer: str | None = None,
    matched_id: int | None = None,
) -> None:
    steps = _as_steps(result.get("steps"))
    record = JudgeResult(
        image_path=image_path,
        question_type=_as_str(result.get("question_type"), "unknown"),
        recognized_content=_as_str(result.get("recognized_content"), ""),
        judgment=_as_str(result.get("judgment"), "unknown"),
        score=_as_int(result.get("score"), 0),
        total_score=_as_int(result.get("total_score"), 10),
        explanation=_as_str(result.get("explanation"), ""),
        step_scores=json.dumps([step.model_dump() for step in steps], ensure_ascii=False)
        if steps
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


def _force_blank_result(result: ResultDict) -> ResultDict:
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
    image: Annotated[UploadFile, File(...)],
    session: Annotated[Session, Depends(get_session)],
    standard_answer: Annotated[str | None, Form()] = None,
) -> JudgeResponse:
    """Upload an image with an optional standard answer and get a grading result."""
    await _validate_image(image)
    dest = _save_upload(image)
    img_b64 = compress_and_encode(str(dest))
    first_pass_result = cast(ResultDict, await grade_image(img_b64))
    result = first_pass_result
    if standard_answer:
        result = cast(ResultDict, await grade_image(img_b64, standard_answer))
        first_recognized = str(first_pass_result.get("recognized_content", ""))
        second_recognized = str(result.get("recognized_content", ""))
        result["recognized_content"] = (
            second_recognized
            if _recognized_has_answer_work(second_recognized)
            else first_recognized
        )
        if _recognized_as_blank(first_recognized) and not _recognized_has_answer_work(
            second_recognized
        ):
            result = _force_blank_result(result)
        result["explanation"] = _prepend_explanation(
            _as_str(result.get("explanation"), ""),
            f"手动输入标准答案：{standard_answer}（综合点评与评分均以手动输入为主；若模型判断不同，会在下文说明差异）",
        )
    _save_record(session, result, str(dest), standard_answer=standard_answer)
    return _to_response(result)


# ── POST /api/judge/with-bank ────────────────────────────────────────────


@router.post("/with-bank", response_model=JudgeResponse)
async def judge_with_bank(
    image: Annotated[UploadFile, File(...)],
    session: Annotated[Session, Depends(get_session)],
) -> JudgeResponse:
    """Upload an image — auto-match to the question bank, then grade."""
    await _validate_image(image)
    dest = _save_upload(image)
    img_b64 = compress_and_encode(str(dest))

    # First pass: recognise content without answer
    first_pass_result = cast(ResultDict, await grade_image(img_b64))
    result = first_pass_result

    # Try to match to question bank
    matched = await find_matching_question(
        session,
        str(result.get("recognized_content", "")),
    )
    std_answer: str | None = None
    if matched and matched.standard_answer:
        std_answer = matched.standard_answer
        # Second pass: re-grade with the matched standard answer
        result = cast(ResultDict, await grade_image(img_b64, std_answer))
        first_recognized = str(first_pass_result.get("recognized_content", ""))
        second_recognized = str(result.get("recognized_content", ""))
        result["recognized_content"] = (
            second_recognized
            if _recognized_has_answer_work(second_recognized)
            else first_recognized
        )
        if _recognized_as_blank(first_recognized) and not _recognized_has_answer_work(
            second_recognized
        ):
            result = _force_blank_result(result)
        result["explanation"] = _prepend_explanation(
            _as_str(result.get("explanation"), ""),
            f"题库标准答案：{std_answer}",
        )
    else:
        result["explanation"] = _prepend_explanation(
            _as_str(result.get("explanation"), ""),
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


@router.post("/batch", tags=["智能判题"])
async def judge_batch(
    images: Annotated[list[UploadFile], File(..., description="多张答卷图片")],
    session: Annotated[Session, Depends(get_session)],
    standard_answer: Annotated[str | None, Form()] = None,
) -> list[dict[str, object]]:
    """Batch grade multiple answer images against the same standard answer."""
    if len(images) > 10:
        raise HTTPException(400, "单次最多提交 10 张图片")

    results: list[dict[str, object]] = []
    for image in images:
        try:
            await _validate_image(image)
            file_path = _save_upload(image)
            img_b64 = compress_and_encode(str(file_path))
            grade_result = await grade_answer(img_b64, standard_answer)

            score = grade_result.get("score")
            total_score = grade_result.get("total_score")
            db_result = JudgeResult(
                image_path=str(file_path),
                recognized_content=_as_str(grade_result.get("recognized_content"), ""),
                score=float(score) if isinstance(score, (int, float)) else 0,
                total_score=float(total_score) if isinstance(total_score, (int, float)) else 100,
                judgment=_as_str(grade_result.get("judgment"), "unknown"),
                explanation=_as_str(grade_result.get("explanation"), ""),
                question_type=_as_str(grade_result.get("question_type"), "unknown"),
                standard_answer_used=standard_answer,
            )
            session.add(db_result)
            results.append(grade_result)
        except HTTPException:
            raise
        except Exception as exc:
            results.append({"error": str(exc), "filename": image.filename or ""})

    session.commit()
    return results


# ── GET /api/judge/results ───────────────────────────────────────────────


@router.get("/results")
def list_results(
    session: Annotated[Session, Depends(get_session)],
    offset: int = 0,
    limit: int = 20,
) -> list[dict[str, object]]:
    """Return recent grading records."""
    from sqlmodel import select

    stmt = (
        select(JudgeResult)
        .order_by(JudgeResult.created_at.desc())  # type: ignore[union-attr] # pyright: ignore[reportAttributeAccessIssue,reportUnknownMemberType,reportUnknownArgumentType]
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
