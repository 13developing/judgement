"""Model-based matching for question-bank lookup."""

from __future__ import annotations

import json
import re

from sqlmodel import Session, select

from backend.models import Question
from backend.services.llm_client import chat_text


def _compact_text(text: str, max_len: int = 220) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    return text[:max_len] + ("..." if len(text) > max_len else "")


async def find_matching_question(session: Session, recognized_content: str) -> Question | None:
    """Use the active LLM to match recognized content to one bank question."""
    text = re.sub(r"\s+", " ", recognized_content or "").strip()
    if not text:
        return None

    stmt = select(Question).order_by(Question.created_at.desc()).limit(30)  # type: ignore[union-attr]
    questions = session.exec(stmt).all()
    if not questions:
        return None

    user_prompt = (
        "请从候选题库中选出与下面识别内容最匹配的一道题。\n"
        "如果没有可靠匹配，返回 JSON：{\"question_id\": null}。\n"
        "如果有匹配，返回 JSON：{\"question_id\": 题目ID}。\n"
        "不要输出任何解释。\n\n"
        f"识别内容：{_compact_text(text, 500)}\n\n"
        "候选题库：\n"
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
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return None

    question_id = data.get("question_id") if isinstance(data, dict) else None
    if not isinstance(question_id, int):
        return None

    return next((question for question in questions if question.id == question_id), None)
