"""Document upload + import endpoints."""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlmodel import Session

from backend.config import UPLOAD_DIR
from backend.database import get_session
from backend.models import Question
from backend.schemas import (
    DocumentConfirmRequest,
    DocumentParseResponse,
    ParsedQuestion,
)
from backend.services.doc_parser import parse_document

router = APIRouter(prefix="/api/upload", tags=["上传"])

_ALLOWED_DOC_EXT = {".docx", ".pdf"}


@router.post("/document", response_model=DocumentParseResponse)
async def upload_document(
    file: UploadFile = File(...),
) -> DocumentParseResponse:
    """Upload a Word/PDF file and return parsed question-answer pairs."""
    ext = Path(file.filename or "").suffix.lower()
    if ext not in _ALLOWED_DOC_EXT:
        raise HTTPException(400, f"不支持的文件类型：{ext}，仅支持 .docx 和 .pdf")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    dest = UPLOAD_DIR / f"{uuid.uuid4().hex}{ext}"
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        pairs = parse_document(str(dest))
    except Exception as exc:
        raise HTTPException(500, f"文档解析失败：{exc}") from exc

    return DocumentParseResponse(
        filename=file.filename or "",
        questions=[ParsedQuestion(**p) for p in pairs],
        count=len(pairs),
    )


@router.post("/document/confirm")
def confirm_import(
    body: DocumentConfirmRequest,
    session: Session = Depends(get_session),
) -> dict:
    """Confirm parsed questions and import them into the question bank."""
    for q in body.questions:
        session.add(
            Question(
                content=q.content,
                question_type=q.question_type,
                standard_answer=q.standard_answer,
                source_file=body.source_file or None,
            )
        )
    session.commit()
    return {"imported": len(body.questions)}
