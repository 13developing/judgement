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


class ExamDocument(SQLModel, table=True):
    """Uploaded exam-paper document metadata."""

    id: int | None = Field(default=None, primary_key=True)
    filename: str
    normalized_name: str
    created_at: datetime = Field(default_factory=datetime.now)


class AnswerDocument(SQLModel, table=True):
    """Uploaded answer document metadata."""

    id: int | None = Field(default=None, primary_key=True)
    filename: str
    normalized_name: str
    created_at: datetime = Field(default_factory=datetime.now)


class ExamAnswerMapping(SQLModel, table=True):
    """Filename-based mapping between exam and answer documents."""

    id: int | None = Field(default=None, primary_key=True)
    normalized_name: str
    status: str
    exam_document_id: int | None = Field(default=None, foreign_key="examdocument.id")
    answer_document_id: int | None = Field(default=None, foreign_key="answerdocument.id")
    created_at: datetime = Field(default_factory=datetime.now)


class ExamQuestionItem(SQLModel, table=True):
    """Question items extracted from an exam document."""

    id: int | None = Field(default=None, primary_key=True)
    exam_document_id: int = Field(foreign_key="examdocument.id")
    sequence_no: int
    content: str
    question_type: str
    created_at: datetime = Field(default_factory=datetime.now)


class AnswerQuestionItem(SQLModel, table=True):
    """Question-answer items extracted from an answer document."""

    id: int | None = Field(default=None, primary_key=True)
    answer_document_id: int = Field(foreign_key="answerdocument.id")
    sequence_no: int
    content: str
    question_type: str
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


class ProviderConfig(SQLModel, table=True):
    """User-managed LLM provider configuration.

    API keys are stored encrypted via Fernet.  Only one provider may be
    ``is_active=True`` at a time; the active provider is used for all LLM
    calls.  When no row is active the system falls back to ``.env`` values.
    """

    id: int | None = Field(default=None, primary_key=True)
    name: str
    provider_type: str  # "ark" | "openai"
    api_key_encrypted: str  # Fernet token
    base_url: str = ""
    model: str = ""
    is_active: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
