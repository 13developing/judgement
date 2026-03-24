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
