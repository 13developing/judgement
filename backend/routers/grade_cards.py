"""Answer card grading endpoint: upload paper + rubric + many student cards.

Goal:
- Upload paper + rubric + up to 100 student answer cards.
- Let the LLM:
  1) extract/normalize paper & rubric (to text)
  2) grade each card: per-question scores + total score
- Return a table-friendly JSON response.

Request (multipart/form-data):
- paper: UploadFile
- rubric: UploadFile
- cards: list[UploadFile]  (<=100)

Response (application/json):
{
  "question_count": int,
  "rows": [
    {"card_filename": str, "scores": [float], "total_score": float, "error": str|null}
  ]
}
"""

from __future__ import annotations

import asyncio
import json
import shutil
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile

from backend.config import UPLOAD_DIR
from backend.services.doc_parser import extract_document_text
from backend.services.llm_client import chat_text, chat_with_image
from backend.utils.image import compress_and_encode

router = APIRouter(prefix="/api/grade-cards", tags=["答题卡批改"])

_ALLOWED_EXT = {".docx", ".pdf", ".png", ".jpg", ".jpeg", ".txt"}
_MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB per file
_MAX_CARDS_PER_REQUEST = 100

# LLM concurrency limit (avoid provider overload); tune as needed.
_LLM_CONCURRENCY = 5


def _ext_of(upload: UploadFile) -> str:
    return Path(upload.filename or "").suffix.lower()


async def _validate_upload(upload: UploadFile, *, label: str) -> None:
    ext = _ext_of(upload)
    if ext not in _ALLOWED_EXT:
        raise HTTPException(
            400,
            f"{label} 不支持的文件类型：{ext or '(无后缀)'}，仅支持 {', '.join(sorted(_ALLOWED_EXT))}",
        )

    content = await upload.read()
    if len(content) > _MAX_FILE_SIZE:
        raise HTTPException(
            400,
            f"{label} 文件大小超过限制（最大 20MB，当前 {len(content) / 1024 / 1024:.1f}MB）",
        )
    await upload.seek(0)


def _save_upload(upload: UploadFile) -> Path:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    ext = _ext_of(upload) or ".bin"
    dest = UPLOAD_DIR / f"{uuid.uuid4().hex}{ext}"
    with open(dest, "wb") as f:
        shutil.copyfileobj(upload.file, f)
    return dest


def _read_text_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def _clean_llm_text(raw: str) -> str:
    cleaned = (raw or "").strip()
    if cleaned.startswith("```"):
        # remove first fence line + trailing fence
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned
        cleaned = cleaned.rsplit("```", 1)[0].strip()
    return cleaned.strip()


def _parse_json_lenient(raw: str) -> dict[str, Any]:
    cleaned = _clean_llm_text(raw)
    try:
        data = json.loads(cleaned)
        return data if isinstance(data, dict) else {}
    except Exception:
        # try to extract a {...} block
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                data = json.loads(cleaned[start : end + 1])
                return data if isinstance(data, dict) else {}
            except Exception:
                return {}
        return {}


async def _image_to_text_via_llm(image_path: Path, *, label: str) -> str:
    """OCR/transcribe an image to text using multimodal LLM."""
    image_b64 = compress_and_encode(str(image_path))
    raw = await chat_with_image(
        system_prompt=(
            "你是一名试卷文本整理助手。请忠实转写图片中的中文、题面、评分细则、学生作答内容。"
            "只输出纯文本，不要加解释，不要使用 markdown 代码块。"
            "如果出现数学公式，必须输出为可直接被 KaTeX 渲染的 LaTeX。"
        ),
        user_prompt=(
            f"请按阅读顺序转写这张图片（类型：{label}）。保留题号、换行，以及“答案：”“解：”“评分细则：”等标记。"
            "不要自创不存在的内容。"
        ),
        image_base64=image_b64,
        max_tokens=3500,
    )
    return _clean_llm_text(raw)


async def file_to_text(path: Path, *, label: str) -> str:
    """
    Convert supported file types to plain text:
    - .txt: read directly
    - .docx/.pdf: use extract_document_text
    - .png/.jpg/.jpeg: use LLM OCR/transcription
    """
    ext = path.suffix.lower()

    if ext == ".txt":
        return _read_text_file(path).strip()

    if ext in {".docx", ".pdf"}:
        try:
            return (await extract_document_text(str(path))).strip()
        except Exception:
            return ""

    if ext in {".png", ".jpg", ".jpeg"}:
        return (await _image_to_text_via_llm(path, label=label)).strip()

    return ""


async def grade_one_card_with_llm(
    *,
    paper_text: str,
    rubric_text: str,
    card_text: str,
    card_filename: str,
) -> dict[str, Any]:
    """Ask LLM to grade a single card and return normalized result."""
    system_prompt = (
        "你是一名严格的阅卷老师与评分系统。"
        "我会给你：试卷内容、评分细则/标准答案、以及某位学生的答题卡内容。"
        "你的任务是：对齐题号并逐题给分，最后汇总总分。"
        "必须严格输出纯 JSON（不要 markdown 代码块，不要多余解释）。"
    )

    user_prompt = f"""
【试卷内容（paper）】
{paper_text}

【评分细则/标准答案（rubric）】
{rubric_text}

【学生答题卡内容（card）- 文件名：{card_filename}】
{card_text}

请输出 JSON，格式如下：
{{
  "question_count": 题目数量(整数),
  "scores": [每一道题的得分数字，按题号顺序排列],
  "total_score": 总分数字,
  "error": null 或 字符串错误信息
}}

规则：
- 题目数量与每题分值/评分点，以“评分细则/标准答案”为主，并结合试卷内容校验。
- 学生未作答的题目得分为 0。
- 只输出 JSON。
""".strip()

    raw = await chat_text(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        max_tokens=2500,
        temperature=0.1,
    )

    data = _parse_json_lenient(raw)

    question_count = data.get("question_count")
    scores = data.get("scores")
    total_score = data.get("total_score")
    error = data.get("error")

    # Normalize fields
    if not isinstance(scores, list):
        scores = []

    norm_scores: list[float] = []
    for s in scores:
        if isinstance(s, (int, float)):
            norm_scores.append(float(s))
        elif isinstance(s, str):
            try:
                norm_scores.append(float(s.strip()))
            except Exception:
                norm_scores.append(0.0)
        else:
            norm_scores.append(0.0)

    if not isinstance(question_count, int):
        question_count = len(norm_scores)

    if not isinstance(total_score, (int, float)):
        total_score = float(sum(norm_scores))
    else:
        total_score = float(total_score)

    if error is not None and not isinstance(error, str):
        error = str(error)

    return {
        "card_filename": card_filename,
        "scores": norm_scores,
        "total_score": total_score,
        "error": error,
        "question_count": int(question_count),
    }


@router.post("")
async def grade_cards(
    paper: UploadFile = File(...),
    rubric: UploadFile = File(...),
    cards: list[UploadFile] = File(..., description="批量学生答题卡（<=100份）"),
) -> dict[str, Any]:
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
    card_paths: list[tuple[str, Path]] = [(c.filename or "", _save_upload(c)) for c in cards]

    # Convert paper/rubric to text once
    paper_text = await file_to_text(paper_path, label="paper")
    rubric_text = await file_to_text(rubric_path, label="rubric")

    if not paper_text.strip() and not rubric_text.strip():
        raise HTTPException(400, "试卷与评分细则均未解析出有效文本，请检查文件内容或格式。")

    sem = asyncio.Semaphore(_LLM_CONCURRENCY)

    async def _grade_task(filename: str, path: Path) -> dict[str, Any]:
        async with sem:
            try:
                card_text = await file_to_text(path, label="card")
                if not card_text.strip():
                    return {
                        "card_filename": filename,
                        "scores": [],
                        "total_score": 0,
                        "error": "未从答题卡解析出有效文本（可能是空白/格式不支持/图片无法识别）",
                        "question_count": 0,
                    }
                return await grade_one_card_with_llm(
                    paper_text=paper_text,
                    rubric_text=rubric_text,
                    card_text=card_text,
                    card_filename=filename,
                )
            except Exception as exc:
                return {
                    "card_filename": filename,
                    "scores": [],
                    "total_score": 0,
                    "error": f"批改失败：{exc}",
                    "question_count": 0,
                }

    results = await asyncio.gather(*[_grade_task(fn, p) for fn, p in card_paths])

    # Compute question_count from max
    question_count = 0
    rows: list[dict[str, Any]] = []
    for r in results:
        qc = r.get("question_count", 0)
        if isinstance(qc, int):
            question_count = max(question_count, qc)
        scores = r.get("scores", [])
        if isinstance(scores, list):
            question_count = max(question_count, len(scores))
        r.pop("question_count", None)
        rows.append(r)

    return {"question_count": question_count, "rows": rows}