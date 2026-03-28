"""Document upload + import endpoints."""

from __future__ import annotations

import logging
import shutil
import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlmodel import Session

from backend.config import UPLOAD_DIR
from backend.database import get_session
from backend.models import (
    AnswerDocument,
    AnswerQuestionItem,
    ExamAnswerMapping,
    ExamDocument,
    ExamQuestionItem,
    Question,
)
from backend.schemas import DocumentConfirmRequest, DocumentParseResponse
from backend.services.document_importer import build_import_bundles

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/upload", tags=["上传"])

_ALLOWED_DOC_EXT = {".docx", ".pdf"}
_MAX_DOC_SIZE = 20 * 1024 * 1024  # 20 MB


@router.post("/document", response_model=DocumentParseResponse)
async def upload_document(
    files: Annotated[list[UploadFile], File(...)],
) -> DocumentParseResponse:
    """Upload multiple docs and let the model extract+match import items."""
    if not files:
        raise HTTPException(400, "请至少上传一份文档")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    saved_paths: list[Path] = []
    saved_names: list[str] = []
    for upload in files:
        saved_paths.append(_save_upload_file(upload))
        saved_names.append(upload.filename or "")

    try:
        summary, questions, bundles = await build_import_bundles(saved_paths, saved_names)
    except ValueError as exc:
        log.warning("Document parsing returned no results: %s", exc)
        raise HTTPException(422, f"文档解析未提取到题目：{exc}") from exc
    except Exception as exc:
        log.exception("Document parsing failed for files: %s", saved_names)
        raise HTTPException(500, f"文档解析失败：{exc}") from exc

    if not questions:
        raise HTTPException(422, "文档解析完成但未提取到任何题目，请检查文档内容格式是否正确")

    return DocumentParseResponse(
        filename=summary,
        questions=questions,
        count=len(questions),
        bundles=bundles,
    )


@router.post("/document/confirm")
def confirm_import(
    body: DocumentConfirmRequest,
    session: Annotated[Session, Depends(get_session)],
) -> dict[str, int]:
    """Confirm parsed questions and import them into the question bank and doc tables."""
    imported = 0
    for bundle in body.bundles:
        exam_document_id: int | None = None
        answer_document_id: int | None = None

        if bundle.exam_file:
            exam_document = ExamDocument(
                filename=bundle.exam_file,
                normalized_name=bundle.normalized_name,
            )
            session.add(exam_document)
            session.flush()
            exam_document_id = exam_document.id
            if exam_document_id is None:
                raise HTTPException(500, "试卷文档保存失败")
            exam_id = exam_document_id

            for idx, question in enumerate(bundle.questions, start=1):
                session.add(
                    ExamQuestionItem(
                        exam_document_id=exam_id,
                        sequence_no=question.sequence_no or idx,
                        content=question.content,
                        question_type=question.question_type,
                    )
                )
                session.add(
                    Question(
                        content=question.content,
                        question_type=question.question_type,
                        standard_answer=question.standard_answer,
                        source_file=question.source_file or bundle.exam_file,
                    )
                )
                imported += 1

        if bundle.answer_file:
            answer_document = AnswerDocument(
                filename=bundle.answer_file,
                normalized_name=bundle.normalized_name,
            )
            session.add(answer_document)
            session.flush()
            answer_document_id = answer_document.id
            if answer_document_id is None:
                raise HTTPException(500, "答案文档保存失败")
            answer_id = answer_document_id

            for idx, answer_question in enumerate(bundle.answer_questions, start=1):
                session.add(
                    AnswerQuestionItem(
                        answer_document_id=answer_id,
                        sequence_no=answer_question.sequence_no or idx,
                        content=answer_question.standard_answer or answer_question.content,
                        question_type=answer_question.question_type,
                    )
                )

        session.add(
            ExamAnswerMapping(
                normalized_name=bundle.normalized_name,
                status=bundle.status,
                exam_document_id=exam_document_id,
                answer_document_id=answer_document_id,
            )
        )

    session.commit()
    return {"imported": imported}


def _save_upload_file(upload: UploadFile) -> Path:
    ext = Path(upload.filename or "").suffix.lower()
    if ext not in _ALLOWED_DOC_EXT:
        raise HTTPException(400, f"不支持的文件类型：{ext}，仅支持 .docx 和 .pdf")

    content = upload.file.read()
    if len(content) > _MAX_DOC_SIZE:
        raise HTTPException(400, "文档大小超过限制（最大 20MB）")
    _ = upload.file.seek(0)

    dest = UPLOAD_DIR / f"{uuid.uuid4().hex}{ext}"
    with open(dest, "wb") as f:
        shutil.copyfileobj(upload.file, f)
    return dest
