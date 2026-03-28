"""Pydantic request / response schemas (decoupled from ORM models)."""

from __future__ import annotations

from pydantic import BaseModel

# ── Judge ────────────────────────────────────────────────────────────────


class StepDetail(BaseModel):
    step: str
    correct: bool
    score: float
    comment: str


class JudgeResponse(BaseModel):
    question_type: str
    recognized_content: str
    judgment: str
    score: float
    total_score: float
    explanation: str
    steps: list[StepDetail] | None = None


class ExamSheetJudgeResponse(BaseModel):
    id: int | None = None
    student_name: str
    subject: str
    judgment: str
    score: float
    total_score: float
    recognized_content: str
    explanation: str
    page_count: int
    page_summaries: list[str] = []
    image_urls: list[str] = []


class ExamSheetListItem(BaseModel):
    id: int
    student_name: str
    subject: str
    judgment: str
    score: float
    total_score: float
    explanation: str
    recognized_content: str
    page_count: int
    page_summaries: list[str] = []
    image_urls: list[str] = []
    created_at: str


class ExamSheetUpdateRequest(BaseModel):
    student_name: str
    subject: str


# ── Question Bank ────────────────────────────────────────────────────────


class QuestionCreate(BaseModel):
    content: str
    question_type: str = "short_answer"
    standard_answer: str | None = None


class QuestionOut(BaseModel):
    id: int
    content: str
    question_type: str
    standard_answer: str | None
    source_file: str | None
    created_at: str


class QuestionBulkDeleteRequest(BaseModel):
    ids: list[int]


# ── Document Upload ──────────────────────────────────────────────────────


class ParsedQuestion(BaseModel):
    sequence_no: int | None = None
    content: str
    question_type: str
    standard_answer: str | None = None
    source_file: str | None = None


class ParsedDocumentBundle(BaseModel):
    normalized_name: str
    status: str
    exam_file: str | None = None
    answer_file: str | None = None
    questions: list[ParsedQuestion] = []
    answer_questions: list[ParsedQuestion] = []


class DocumentParseResponse(BaseModel):
    filename: str
    questions: list[ParsedQuestion]
    count: int
    bundles: list[ParsedDocumentBundle] = []


class DocumentConfirmRequest(BaseModel):
    questions: list[ParsedQuestion]
    source_file: str = ""
    bundles: list[ParsedDocumentBundle] = []


# ── Provider Config ──────────────────────────────────────────────────────


class ProviderConfigCreate(BaseModel):
    name: str
    provider_type: str  # "ark" | "openai"
    api_key: str
    base_url: str = ""
    model: str = ""


class ProviderConfigUpdate(BaseModel):
    name: str | None = None
    provider_type: str | None = None
    api_key: str | None = None  # only sent when user changes key
    base_url: str | None = None
    model: str | None = None


class ProviderConfigOut(BaseModel):
    id: int
    name: str
    provider_type: str
    api_key_masked: str  # e.g. "sk-ab****yz"
    base_url: str
    model: str
    is_active: bool
    created_at: str
    updated_at: str


class ProviderTestRequest(BaseModel):
    """Inline test — caller provides credentials directly (no DB row required)."""

    provider_type: str
    api_key: str
    base_url: str = ""
    model: str = ""
