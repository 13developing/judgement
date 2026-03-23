"""SQLModel ORM models — persisted to SQLite."""

from __future__ import annotations

from datetime import datetime

from sqlmodel import Field, SQLModel


class Question(SQLModel, table=True):
    """A question stored in the question bank."""

    id: int | None = Field(default=None, primary_key=True)
    content: str
    question_type: str  # fill_blank / short_answer / calculation
    standard_answer: str | None = None
    source_file: str | None = None
    created_at: datetime = Field(default_factory=datetime.now)


class JudgeResult(SQLModel, table=True):
    """A single grading record."""

    id: int | None = Field(default=None, primary_key=True)
    image_path: str
    question_type: str
    recognized_content: str
    judgment: str  # correct / wrong / partial
    score: float
    total_score: float
    explanation: str
    step_scores: str | None = None  # JSON string for per-step breakdown
    matched_question_id: int | None = None
    standard_answer_used: str | None = None
    created_at: datetime = Field(default_factory=datetime.now)
