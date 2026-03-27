"""Model-based matching for question-bank lookup."""

from __future__ import annotations

import hashlib
import json
import re
import time
from typing import cast

from sqlmodel import Session, select

from backend.models import Question
from backend.services.llm_client import chat_text

_match_cache: dict[str, tuple[float, int | None]] = {}
_CACHE_TTL = 300
_SENTINEL = object()


def _cache_key(text: str) -> str:
    """Create a normalized cache key from recognized text."""
    normalized = text.strip().lower()[:500]
    return hashlib.md5(normalized.encode()).hexdigest()  # noqa: S324


def _get_cached(key: str) -> int | None | object:
    """Return cached question_id if still valid, else sentinel."""
    if key in _match_cache:
        ts, question_id = _match_cache[key]
        if time.time() - ts < _CACHE_TTL:
            return question_id
        del _match_cache[key]
    return _SENTINEL


def _set_cache(key: str, question_id: int | None) -> None:
    """Store match result in cache."""
    _match_cache[key] = (time.time(), question_id)


def _compact_text(text: str, max_len: int = 220) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    return text[:max_len] + ("..." if len(text) > max_len else "")


async def find_matching_question(session: Session, recognized_content: str) -> Question | None:
    """Use the active LLM to match recognized content to one bank question."""
    text = re.sub(r"\s+", " ", recognized_content or "").strip()
    if not text:
        return None

    key = _cache_key(text)
    cached = _get_cached(key)
    if cached is not _SENTINEL:
        if isinstance(cached, int):
            return session.get(Question, cached)
        return None

    stmt = select(Question).order_by(Question.created_at.desc()).limit(200)  # pyright: ignore[reportAttributeAccessIssue,reportUnknownMemberType,reportUnknownArgumentType]
    questions = session.exec(stmt).all()
    if not questions:
        _set_cache(key, None)
        return None

    user_prompt = (
        "请从候选题库中选出与下面识别内容最匹配的一道题。\n"
        + '如果没有可靠匹配，返回 JSON：{"question_id": null}。\n'
        + '如果有匹配，返回 JSON：{"question_id": 题目ID}。\n'
        + "不要输出任何解释。\n\n"
        + f"识别内容：{_compact_text(text, 500)}\n\n"
        + "候选题库：\n"
        + "\n".join(
            f"- id={question.id} | 题型={question.question_type} | 题面={_compact_text(question.content, 180)}"
            for question in questions
        )
    )

    raw = await chat_text(
        system_prompt="你是一名数学题库匹配助手，只输出 JSON。",
        user_prompt=user_prompt,
        temperature=0.0,
        max_tokens=800,
    )

    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```\s*$", "", cleaned)

    try:
        parsed = cast(object, json.loads(cleaned))
    except json.JSONDecodeError:
        _set_cache(key, None)
        return None

    if not isinstance(parsed, dict):
        _set_cache(key, None)
        return None

    data = cast(dict[str, object], parsed)
    question_id = data.get("question_id")
    if not isinstance(question_id, int):
        _set_cache(key, None)
        return None

    matched_question = next(
        (question for question in questions if question.id == question_id), None
    )
    _set_cache(key, matched_question.id if matched_question else None)
    return matched_question
