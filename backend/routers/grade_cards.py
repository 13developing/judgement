"""Answer card grading endpoint: upload paper + rubric + many student cards."""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile

from backend.config import UPLOAD_DIR

router = APIRouter(prefix="/api/grade-cards", tags=["答题卡批改"])

# You asked: docx, pdf, png, img, txt
# In practice "img" means common image formats; we support jpg/jpeg/png.
_ALLOWED_EXT = {".docx", ".pdf", ".png", ".jpg", ".jpeg", ".txt"}

_MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB per file (aligns with upload.py)
_MAX_CARDS_PER_REQUEST = 100


def _ext_of(upload: UploadFile) -> str:
    return Path(upload.filename or "").suffix.lower()


async def _validate_upload(upload: UploadFile, *, label: str) -> None:
    ext = _ext_of(upload)
    if ext not in _ALLOWED_EXT:
        raise HTTPException(
            400,
            f"{label} 不支持的文件类型：{ext or '(无后缀)'}，仅支持 {', '.join(sorted(_ALLOWED_EXT))}",
        )

    # Size check (read then seek back)
    content = await upload.read()
    if len(content) > _MAX_FILE_SIZE:
        raise HTTPException(
            400,
            f"{label} 文件大小超过限制（最大 20MB，当前 {len(content) / 1024 / 1024:.1f}MB）",
        )
    await upload.seek(0)


def _save_upload(upload: UploadFile) -> Path:
    """Save UploadFile to UPLOAD_DIR and return path."""
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    ext = _ext_of(upload) or ".bin"
    dest = UPLOAD_DIR / f"{uuid.uuid4().hex}{ext}"
    with open(dest, "wb") as f:
        shutil.copyfileobj(upload.file, f)
    return dest


async def grade_one_card(
    *,
    paper_path: Path,
    rubric_path: Path,
    card_path: Path,
    card_filename: str,
) -> dict[str, Any]:
    """
    Grade a single card.

    TODO: Replace this placeholder with your real LLM workflow:
      - parse paper + rubric into question structure
      - parse card
      - call multimodal/text LLM
      - return per-question scores + total

    Return shape MUST match:
      {
        "card_filename": str,
        "scores": list[float],
        "total_score": float,
        "error": str | None
      }
    """
    # ---- PLACEHOLDER IMPLEMENTATION (for integration) ----
    # Use a deterministic pseudo-score so UI can render.
    # You will replace this whole block.
    try:
        # Fake: assume 5 questions
        question_count = 5
        base = sum(card_filename.encode("utf-8")) % 6  # 0..5
        scores = [float(min(10, base + i)) for i in range(question_count)]
        total = float(sum(scores))
        return {
            "card_filename": card_filename,
            "scores": scores,
            "total_score": total,
            "error": None,
        }
    except Exception as exc:  # pragma: no cover
        return {
            "card_filename": card_filename,
            "scores": [],
            "total_score": 0,
            "error": f"批改失败：{exc}",
        }


@router.post("")
async def grade_cards(
    paper: UploadFile = File(...),
    rubric: UploadFile = File(...),
    cards: list[UploadFile] = File(
        ...,
        description="批量学生答题卡（<=100份）",
        openapi_extra={
            "type": "array",
            "items": {"type": "string", "format": "binary"},
        },
    ),
):
    """
    Upload paper + rubric + up to 100 student answer cards,
    returns per-card per-question scores and totals (for table rendering).
    """
    # Basic validations
    if not cards:
        raise HTTPException(400, "请至少上传 1 份学生答题卡")
    if len(cards) > _MAX_CARDS_PER_REQUEST:
        raise HTTPException(400, f"单次最多提交 {_MAX_CARDS_PER_REQUEST} 份答题卡")

    await _validate_upload(paper, label="试卷本身")
    await _validate_upload(rubric, label="评分细则/答案")

    for c in cards:
        await _validate_upload(c, label="学生答题卡")

    # Save uploads
    paper_path = _save_upload(paper)
    rubric_path = _save_upload(rubric)

    rows: list[dict[str, Any]] = []

    # Grade each card (MVP serial; later you can add concurrency)
    for c in cards:
        card_filename = c.filename or ""
        card_path = _save_upload(c)

        row = await grade_one_card(
            paper_path=paper_path,
            rubric_path=rubric_path,
            card_path=card_path,
            card_filename=card_filename,
        )
        rows.append(row)

    # Infer question_count for frontend header
    question_count = 0
    for r in rows:
        if isinstance(r.get("scores"), list):
            question_count = max(question_count, len(r["scores"]))
    return {
        "question_count": question_count,
        "rows": rows,
    }
