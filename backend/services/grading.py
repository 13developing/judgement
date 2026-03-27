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
- 如果提供了手动输入的标准答案，你必须把它视为本次评分的主依据
- 你可以基于题目与学生过程判断该标准答案是否与数学结论不同，但只能在 `explanation` 中指出“模型判断与手动输入答案不一致”，并说明差异
- 即使模型判断与手动输入答案不同，最终评分与结论仍然以手动输入答案为主
- 如果没有标准答案，根据数学正确性自主判断
- 兼容多种等效写法（如 1/2 = 0.5，sin²x = (sin x)²，ln 与 log_e 等价）
- `recognized_content`、`explanation`、`steps[].step`、`steps[].comment` 中只要出现数学公式，都必须使用 LaTeX 表达
- 行内公式统一用 `$...$` 包裹，独立公式统一用 `$$...$$` 包裹
- 极限、分式、三角函数、幂次、根号等必须写成规范 LaTeX，例如 `$\\lim_{x \\to 0} \\frac{\\tan x - x}{x \\arcsin(x^2)} + x \\cos\\left(\\frac{1}{x}\\right)$`
- 不要输出 `lim(x→0)`、`x^2`、`sec^2 x` 这类未包裹且未规范 LaTeX 化的纯文本公式
- 对于选择题或填空题里的空括号、空横线、选项占位，不要写成 `\\(\\)`、`$()$` 这类数学定界符，直接输出普通文本括号或横线，如 `（    ）`、`(    )`、`______`
- `recognized_content` 必须只基于图片中真实可见的内容，不得把提供的标准答案写进“学生作答”
- 如果图片中学生没有填写答案，必须明确写成“学生作答：未作答”或“学生作答：空白”
- 非公式说明文字保持自然中文表达，但不要破坏 LaTeX 定界符或转义字符\
"""


def _build_user_prompt(standard_answer: str | None) -> str:
    if standard_answer:
        return (
            "请根据以下标准答案判断图片中学生的作答是否正确，并给出评分。\n\n"
            "注意：返回的题面、学生作答、判分理由和步骤点评中，所有数学表达式都必须写成可直接由 KaTeX 渲染的 LaTeX。\n\n"
            "注意：空括号、填空横线、选项占位不要使用 LaTeX 定界符，直接保留普通文本形式。\n\n"
            "注意：我手动输入的标准答案是本次评分主依据。你要结合题目和学生作答来综合点评；如果你的数学判断与我输入的答案不一致，请在综合点评中明确指出差异，但最终仍以我输入的答案为主进行评分。\n\n"
            f"标准答案：{standard_answer}"
        )
    return (
        "请判断图片中学生的作答是否正确（无标准答案，请自主判断），并给出评分。\n\n"
        "注意：返回的题面、学生作答、判分理由和步骤点评中，所有数学表达式都必须写成可直接由 KaTeX 渲染的 LaTeX。\n\n"
        "注意：空括号、填空横线、选项占位不要使用 LaTeX 定界符，直接保留普通文本形式。"
    )


def _parse_response(raw: str) -> dict:
    """Parse LLM response, tolerating markdown fences."""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```\s*$", "", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        repaired = _repair_json_backslashes(cleaned)
        try:
            return json.loads(repaired)
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


def _repair_json_backslashes(text: str) -> str:
    """Escape invalid backslashes inside JSON strings, mainly for LaTeX."""
    result: list[str] = []
    in_string = False
    escape = False
    valid_json_escapes = {'"', "\\", "/", "b", "f", "n", "r", "t", "u"}

    i = 0
    while i < len(text):
        ch = text[i]

        if not in_string:
            result.append(ch)
            if ch == '"':
                in_string = True
            i += 1
            continue

        if escape:
            result.append(ch)
            escape = False
            i += 1
            continue

        if ch == "\\":
            next_ch = text[i + 1] if i + 1 < len(text) else ""
            if next_ch in valid_json_escapes:
                result.append(ch)
                escape = True
            else:
                result.append("\\\\")
            i += 1
            continue

        result.append(ch)
        if ch == '"':
            in_string = False
        i += 1

    return "".join(result)


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
