"""Core grading logic — prompt engineering + response parsing."""

from __future__ import annotations

import json
import re

from backend.services.llm_client import chat_with_image

# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
你是一名专业的大学数学阅卷老师，擅长高等数学、线性代数、概率论与数理统计等课程的判题。

请严格按照以下 JSON 格式输出判题结果（纯 JSON，不要用 markdown 代码块包裹）：

{
  "question_type": "fill_blank 或 short_answer 或 calculation",
  "recognized_content": "识别出的完整题面与学生作答内容",
  "judgment": "correct 或 wrong 或 partial",
  "score": 得分数字,
  "total_score": 满分数字,
  "explanation": "判分理由",
  "steps": [
    {"step": "步骤描述", "correct": true, "score": 分值, "comment": "评语"}
  ]
}

规则：
- 填空题和简答题的 steps 可以为空数组 []
- 计算题必须逐步拆分过程分，每步给出得分与评语
- score 是学生实际得分，total_score 是该题满分（默认 10）
- 如果提供了标准答案，以标准答案为评分依据
- 如果没有标准答案，根据数学正确性自主判断
- 兼容多种等效写法（如 1/2 = 0.5，sin²x = (sin x)²，ln 与 log_e 等价）\
"""


def _build_user_prompt(standard_answer: str | None) -> str:
    if standard_answer:
        return (
            "请根据以下标准答案判断图片中学生的作答是否正确，并给出评分。\n\n"
            f"标准答案：{standard_answer}"
        )
    return "请判断图片中学生的作答是否正确（无标准答案，请自主判断），并给出评分。"


def _parse_response(raw: str) -> dict:
    """Parse LLM response, tolerating markdown fences."""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```\s*$", "", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {
            "question_type": "unknown",
            "recognized_content": "",
            "judgment": "unknown",
            "score": 0,
            "total_score": 10,
            "explanation": raw,
            "steps": [],
        }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def grade_image(
    image_base64: str,
    standard_answer: str | None = None,
) -> dict:
    """Call LLM to grade an exam answer image. Returns a structured dict."""
    user_prompt = _build_user_prompt(standard_answer)
    raw = await chat_with_image(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        image_base64=image_base64,
    )
    return _parse_response(raw)
