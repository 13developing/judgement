"""Question-bank CRUD endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from backend.database import get_session
from backend.models import Question
from backend.schemas import QuestionCreate, QuestionOut

router = APIRouter(prefix="/api/questions", tags=["题库"])


@router.get("", response_model=list[QuestionOut])
def list_questions(
    keyword: str = Query(None),
    question_type: str = Query(None),
    offset: int = 0,
    limit: int = 50,
    session: Session = Depends(get_session),
) -> list[QuestionOut]:
    stmt = select(Question)
    if keyword:
        stmt = stmt.where(Question.content.contains(keyword))  # type: ignore[union-attr]
    if question_type:
        stmt = stmt.where(Question.question_type == question_type)
    stmt = (
        stmt.order_by(Question.created_at.desc())  # type: ignore[union-attr]
        .offset(offset)
        .limit(limit)
    )
    rows = session.exec(stmt).all()
    return [
        QuestionOut(
            id=q.id,  # type: ignore[arg-type]
            content=q.content,
            question_type=q.question_type,
            standard_answer=q.standard_answer,
            source_file=q.source_file,
            created_at=q.created_at.isoformat() if q.created_at else "",
        )
        for q in rows
    ]


@router.post("", response_model=QuestionOut, status_code=201)
def create_question(
    data: QuestionCreate,
    session: Session = Depends(get_session),
) -> QuestionOut:
    q = Question(
        content=data.content,
        question_type=data.question_type,
        standard_answer=data.standard_answer,
    )
    session.add(q)
    session.commit()
    session.refresh(q)
    return QuestionOut(
        id=q.id,  # type: ignore[arg-type]
        content=q.content,
        question_type=q.question_type,
        standard_answer=q.standard_answer,
        source_file=q.source_file,
        created_at=q.created_at.isoformat() if q.created_at else "",
    )


@router.delete("/{question_id}")
def delete_question(
    question_id: int,
    session: Session = Depends(get_session),
) -> dict:
    q = session.get(Question, question_id)
    if not q:
        raise HTTPException(status_code=404, detail="题目不存在")
    session.delete(q)
    session.commit()
    return {"detail": "已删除"}
