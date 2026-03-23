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


# ── Document Upload ──────────────────────────────────────────────────────


class ParsedQuestion(BaseModel):
    content: str
    question_type: str
    standard_answer: str | None = None


class DocumentParseResponse(BaseModel):
    filename: str
    questions: list[ParsedQuestion]
    count: int


class DocumentConfirmRequest(BaseModel):
    questions: list[ParsedQuestion]
    source_file: str = ""
