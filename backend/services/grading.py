"""Core grading logic — prompt engineering + response parsing."""

from __future__ import annotations

import json
import re

from backend.services.llm_client import chat_with_image, chat_with_images

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

EXAM_SHEET_SYSTEM_PROMPT = """\
你是一名大学阅卷老师，正在查看同一位学生的一整份答题纸（会连续给你多张图片）。

请先识别并整合同一位学生多页答卷中的关键信息，再严格输出纯 JSON：

{
  "student_name": "学生姓名，无法识别则写 未识别",
  "subject": "考试科目，无法识别则写 未识别",
  "judgment": "correct 或 wrong 或 partial",
  "score": 得分数字,
  "total_score": 满分数字,
  "recognized_content": "对整份答卷的识别摘要，需包含姓名、科目、主要作答情况",
  "explanation": "总评，说明给分依据与失分原因",
  "page_summaries": ["第1页摘要", "第2页摘要"]
}

规则：
- 多张图片按给定顺序视为同一位学生的连续答题纸
- 必须尽量从答题纸中识别学生姓名和考试科目
- 优先读取首页页眉或信息栏中的字段，尤其是 `姓名`、`课程名称`、`考试科目`、`标题`
- `student_name` 必须只填写真实人名，不要把班级、学院、专业、课程名写成姓名
- 如果 `姓名:` 后面的内容像班级或专业（如包含“高数”“数学”“生科”“学院”“班级”），说明识别错位，必须重新判断附近手写姓名
- `subject` 优先取试卷标题中的课程名，例如“高等数学（2）上”
- 如果图片中有总分或题目分值，优先据此给分；否则可基于可见作答估计总分
- `recognized_content` 需要明确写出“姓名：...”“科目：...”
- `page_summaries` 数量要与图片页数一致
- 输出必须是纯 JSON，不要附加 markdown 或解释文字\
"""

EXAM_SHEET_METADATA_SYSTEM_PROMPT = """\
你正在识别大学试卷首页顶部的元信息。系统会提供：
- 同一张首页的完整图
- 同一张首页顶部裁切图

请严格输出纯 JSON：
{
  "student_name": "学生真实姓名，无法确认则写 未识别",
  "subject": "课程名称，无法确认则写 未识别",
  "confidence": "high 或 medium 或 low",
  "reason": "简短说明依据"
}

规则：
- 只提取学生真实姓名，不要输出班级、学院、专业、学号、座号
- 优先读取 `姓名` 字段附近的手写内容
- 如果名字与专业/学院词语混在一起，必须只保留看起来像中文人名的部分
- `subject` 优先读取试卷标题中的课程名，例如“高等数学（2）上”
- 无法确认时宁可输出 `未识别`，不要猜测\
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


def _cleanup_metadata_value(value: object) -> str:
    if not isinstance(value, str):
        return "未识别"
    cleaned = re.sub(r"\s+", "", value.strip())
    return cleaned or "未识别"


def _looks_like_subject(text: str) -> bool:
    markers = ("数学", "英语", "物理", "化学", "课程", "学院", "专业", "班", "生科")
    return any(marker in text for marker in markers)


def _looks_like_person_name(text: str) -> bool:
    return bool(re.fullmatch(r"[\u4e00-\u9fff]{2,4}", text))


async def extract_exam_sheet_metadata(
    first_page_base64: str,
    first_page_top_base64: str,
) -> dict[str, str]:
    """Extract student name and subject from the first page header area."""
    raw = await chat_with_images(
        system_prompt=EXAM_SHEET_METADATA_SYSTEM_PROMPT,
        user_prompt=(
            "第 1 张图是整页首页，第 2 张图是首页顶部裁切区域。"
            "请优先根据顶部裁切图识别姓名和课程名称，再用整页图交叉确认。"
        ),
        image_base64_list=[first_page_base64, first_page_top_base64],
        max_tokens=1200,
    )
    parsed = _parse_response(raw)
    student_name = _cleanup_metadata_value(parsed.get("student_name"))
    subject = _cleanup_metadata_value(parsed.get("subject"))

    if not _looks_like_person_name(student_name) or _looks_like_subject(student_name):
        student_name = "未识别"
    if _looks_like_person_name(subject) and not _looks_like_subject(subject):
        subject = "未识别"

    return {
        "student_name": student_name,
        "subject": subject,
    }


def _build_exam_sheet_prompt(standard_answer: str | None, page_count: int) -> str:
    base_prompt = (
        f"现在会提供同一位学生的 {page_count} 张连续答卷图片，请整合识别后给出整份答卷的总成绩。"
    )
    if standard_answer:
        return (
            f"{base_prompt}\n\n"
            "先从第一页顶部提取姓名和课程名称，再综合整份答卷评分。姓名必须是学生真实姓名，不得把班级、学院或专业当成姓名。\n\n"
            "请优先按照以下评分依据或标准答案进行整卷评分；如果图片内容与评分依据存在冲突，也请在总评中说明。\n\n"
            f"评分依据：{standard_answer}"
        )
    return (
        f"{base_prompt}\n\n"
        "先从第一页顶部提取姓名和课程名称，再综合整份答卷评分。姓名必须是学生真实姓名，不得把班级、学院或专业当成姓名。\n\n"
        "若缺少标准答案，请根据图片中可见内容进行合理总评和估分。"
    )


def _parse_exam_sheet_response(raw: str, page_count: int) -> dict[str, object]:
    parsed = _parse_response(raw)
    page_summaries_raw = parsed.get("page_summaries")
    page_summaries = []
    if isinstance(page_summaries_raw, list):
        for item in page_summaries_raw:
            if isinstance(item, str):
                page_summaries.append(item)

    while len(page_summaries) < page_count:
        page_summaries.append(f"第 {len(page_summaries) + 1} 页内容待补充")

    return {
        "student_name": parsed.get("student_name")
        if isinstance(parsed.get("student_name"), str)
        else "未识别",
        "subject": parsed.get("subject") if isinstance(parsed.get("subject"), str) else "未识别",
        "judgment": parsed.get("judgment") if isinstance(parsed.get("judgment"), str) else "partial",
        "score": parsed.get("score") if isinstance(parsed.get("score"), (int, float)) else 0,
        "total_score": parsed.get("total_score")
        if isinstance(parsed.get("total_score"), (int, float))
        else 100,
        "recognized_content": parsed.get("recognized_content")
        if isinstance(parsed.get("recognized_content"), str)
        else "",
        "explanation": parsed.get("explanation")
        if isinstance(parsed.get("explanation"), str)
        else raw,
        "page_summaries": page_summaries[:page_count],
    }


async def grade_exam_sheet(
    image_base64_list: list[str],
    metadata: dict[str, str] | None = None,
    standard_answer: str | None = None,
) -> dict[str, object]:
    """Grade one student's multi-page answer sheet."""
    raw = await chat_with_images(
        system_prompt=EXAM_SHEET_SYSTEM_PROMPT,
        user_prompt=_build_exam_sheet_prompt(standard_answer, len(image_base64_list)),
        image_base64_list=image_base64_list,
    )
    parsed = _parse_exam_sheet_response(raw, len(image_base64_list))
    if metadata:
        student_name = metadata.get("student_name", "未识别")
        subject = metadata.get("subject", "未识别")
        if student_name != "未识别":
            parsed["student_name"] = student_name
        if subject != "未识别":
            parsed["subject"] = subject

        recognized = str(parsed.get("recognized_content", ""))
        if student_name != "未识别" and "姓名：" not in recognized:
            recognized = f"姓名：{student_name}\n科目：{subject}\n\n{recognized}".strip()
        parsed["recognized_content"] = recognized

    return parsed
