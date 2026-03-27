"""Model-driven document import for exam papers and answer files."""

from __future__ import annotations

import json
import re
from pathlib import Path

from backend.schemas import ParsedDocumentBundle, ParsedQuestion
from backend.services.doc_parser import extract_document_text
from backend.services.llm_client import chat_text

_EXTRACT_SYSTEM_PROMPT = """你是一名大学数学题库整理助手。

任务：从试卷或答案文档的原始文本中提取结构化题目。

要求：
- 只输出 JSON，不要输出解释
- 过滤页码、考试须知、签名区、分值说明、评阅人、章节标题等版式噪音
- 保留真正题干、选项、公式
- sequence_no 表示题号；如果无法确定，尽量根据上下文推断连续编号
- question_type 只能是 fill_blank、short_answer、calculation
- 对答案文档，content 填答案内容，standard_answer 也填答案内容
"""


async def build_import_bundles(
    files: list[Path], filenames: list[str]
) -> tuple[str, list[ParsedQuestion], list[ParsedDocumentBundle]]:
    file_roles = await _classify_files_with_model(filenames)
    exam_files: dict[str, tuple[str, list[ParsedQuestion]]] = {}
    answer_files: dict[str, tuple[str, list[ParsedQuestion]]] = {}

    for file_path, filename in zip(files, filenames, strict=True):
        role_info = file_roles.get(
            filename, {"role": "exam", "group_key": _normalize_doc_name(filename)}
        )
        is_answer = role_info["role"] == "answer"
        raw_text = await extract_document_text(str(file_path))
        parsed_questions = await _extract_questions_with_model(
            raw_text, is_answer=is_answer, filename=filename
        )
        normalized_name = role_info["group_key"]
        if is_answer:
            answer_files[normalized_name] = (filename, parsed_questions)
        else:
            exam_files[normalized_name] = (filename, parsed_questions)

    bundles: list[ParsedDocumentBundle] = []
    flattened_questions: list[ParsedQuestion] = []
    matched_count = 0

    for normalized_name, (exam_name, exam_questions) in exam_files.items():
        answer_name: str | None = None
        merged_questions: list[ParsedQuestion] = []
        answer_questions: list[ParsedQuestion] = []

        if normalized_name in answer_files:
            answer_name, answer_questions = answer_files[normalized_name]
            matched_count += 1
            merged_questions = await _match_questions_with_model(
                exam_questions, answer_questions, exam_name, answer_name
            )
        else:
            merged_questions = [
                ParsedQuestion(
                    sequence_no=q.sequence_no,
                    content=q.content,
                    question_type=q.question_type,
                    standard_answer=None,
                    source_file=exam_name,
                )
                for q in exam_questions
            ]

        flattened_questions.extend(merged_questions)
        bundles.append(
            ParsedDocumentBundle(
                normalized_name=normalized_name,
                status="matched" if answer_name else "exam_only",
                exam_file=exam_name,
                answer_file=answer_name,
                questions=merged_questions,
                answer_questions=answer_questions,
            )
        )

    for normalized_name, (answer_name, answer_questions) in answer_files.items():
        if normalized_name not in exam_files:
            bundles.append(
                ParsedDocumentBundle(
                    normalized_name=normalized_name,
                    status="answer_only",
                    exam_file=None,
                    answer_file=answer_name,
                    questions=[],
                    answer_questions=answer_questions,
                )
            )

    if not flattened_questions:
        raise ValueError("未解析到可导入的试卷题目")

    summary = f"已匹配 {matched_count}/{len(exam_files)} 份试卷"
    return summary, flattened_questions, bundles


async def _extract_questions_with_model(
    raw_text: str, *, is_answer: bool, filename: str
) -> list[ParsedQuestion]:
    mode = "答案文档" if is_answer else "试卷文档"
    user_prompt = (
        f"下面是{mode}的原始文本，请抽取结构化题目列表。\n"
        "返回 JSON 数组，每项格式为："
        '{"sequence_no": 1, "question_type": "short_answer", "content": "...", "standard_answer": "...或null"}。\n'
        f"文件名：{filename}\n\n"
        f"原始文本：\n{raw_text[:18000]}"
    )

    raw = await chat_text(
        system_prompt=_EXTRACT_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        temperature=0.0,
        max_tokens=4000,
    )
    return _parse_question_array(raw, is_answer=is_answer, filename=filename)


async def _match_questions_with_model(
    exam_questions: list[ParsedQuestion],
    answer_questions: list[ParsedQuestion],
    exam_name: str,
    answer_name: str,
) -> list[ParsedQuestion]:
    user_prompt = (
        "请把试卷题目和答案条目直接合并成可入库的题目列表。\n"
        "返回 JSON 数组，每项格式为："
        '{"sequence_no": 1, "question_type": "short_answer", "content": "题面", "standard_answer": "标准答案或null"}。\n'
        "要求：\n"
        "- 以试卷题目为主，不能凭空新增题目\n"
        "- 标准答案来自最匹配的答案条目\n"
        "- 如果没有可靠答案，standard_answer 返回 null\n"
        "- 只输出 JSON，不要解释\n\n"
        f"试卷文件：{exam_name}\n"
        f"答案文件：{answer_name}\n\n"
        f"试卷题目：\n{_format_question_list(exam_questions)}\n\n"
        f"答案条目：\n{_format_question_list(answer_questions)}"
    )

    raw = await chat_text(
        system_prompt="你是一名大学数学题库整理助手，只输出 JSON。",
        user_prompt=user_prompt,
        temperature=0.0,
        max_tokens=4000,
    )
    merged = _parse_question_array(raw, is_answer=False, filename=exam_name)
    return [
        ParsedQuestion(
            sequence_no=q.sequence_no,
            content=q.content,
            question_type=q.question_type,
            standard_answer=q.standard_answer,
            source_file=exam_name,
        )
        for q in merged
    ]


def _parse_question_array(raw: str, *, is_answer: bool, filename: str) -> list[ParsedQuestion]:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```\s*$", "", cleaned)

    data = json.loads(cleaned)
    if not isinstance(data, list):
        raise ValueError("模型未返回题目数组")

    questions: list[ParsedQuestion] = []
    for idx, item in enumerate(data, start=1):
        if not isinstance(item, dict):
            continue
        content = str(item.get("content") or "").strip()
        if not content:
            continue
        standard_answer = item.get("standard_answer")
        if is_answer and not standard_answer:
            standard_answer = content
        questions.append(
            ParsedQuestion(
                sequence_no=_coerce_int(item.get("sequence_no")) or idx,
                content=content,
                question_type=_normalize_question_type(
                    str(item.get("question_type") or "short_answer")
                ),
                standard_answer=str(standard_answer).strip()
                if standard_answer is not None
                else None,
                source_file=filename,
            )
        )
    return questions


def _format_question_list(questions: list[ParsedQuestion]) -> str:
    return "\n".join(
        f"- 题号 {q.sequence_no or idx} | 题型 {q.question_type} | 内容 {_compact_text(q.content)}"
        for idx, q in enumerate(questions, start=1)
    )


def _compact_text(text: str, max_len: int = 220) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    return text[:max_len] + ("..." if len(text) > max_len else "")


def _normalize_question_type(value: str) -> str:
    value = value.strip().lower()
    if value in {"fill_blank", "short_answer", "calculation"}:
        return value
    if any(token in value for token in ("填空", "blank")):
        return "fill_blank"
    if any(token in value for token in ("计算", "证明", "积分", "极限", "导数", "calc")):
        return "calculation"
    return "short_answer"


def _coerce_int(value: object) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def _is_answer_filename(filename: str) -> bool:
    stem = Path(filename).stem.lower()
    return "答案" in stem or "answer" in stem


def _normalize_doc_name(filename: str) -> str:
    stem = Path(filename).stem.lower()
    for token in ("答案", "参考答案", "answer", "ans", "试卷", "卷", "参考", "解析"):
        stem = stem.replace(token, "")
    stem = stem.replace("（", "(").replace("）", ")")
    stem = stem.replace("—", "-").replace("－", "-")
    stem = stem.replace("_", "")
    stem = stem.replace(" ", "")
    return stem


async def _classify_files_with_model(filenames: list[str]) -> dict[str, dict[str, str]]:
    if not filenames:
        return {}

    user_prompt = (
        "请判断下面每个文件名更像试卷、答案，还是无法判断。\n"
        "同时把属于同一套试卷/答案的文件分到同一个 group_key。\n"
        "返回 JSON 数组，每项格式为："
        '{"filename": "xx.pdf", "role": "exam|answer|unknown", "group_key": "同套文件键"}。\n'
        "如果无法判断 role，优先返回 exam。\n"
        "group_key 请尽量让同一套试卷和答案一致。\n\n"
        "文件名列表：\n" + "\n".join(f"- {name}" for name in filenames)
    )

    raw = await chat_text(
        system_prompt="你是一名试卷文件归类助手，只输出 JSON。",
        user_prompt=user_prompt,
        temperature=0.0,
        max_tokens=1200,
    )

    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```\s*$", "", cleaned)

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return {
            name: {
                "role": "answer" if _is_answer_filename(name) else "exam",
                "group_key": _normalize_doc_name(name),
            }
            for name in filenames
        }

    result: dict[str, dict[str, str]] = {}
    if isinstance(data, list):
        for item in data:
            if not isinstance(item, dict):
                continue
            filename = str(item.get("filename") or "")
            if filename not in filenames:
                continue
            role = str(item.get("role") or "exam").lower()
            if role not in {"exam", "answer", "unknown"}:
                role = "exam"
            group_key = str(item.get("group_key") or "").strip() or _normalize_doc_name(filename)
            result[filename] = {
                "role": "exam" if role == "unknown" else role,
                "group_key": _normalize_doc_name(group_key),
            }

    for name in filenames:
        result.setdefault(
            name,
            {
                "role": "answer" if _is_answer_filename(name) else "exam",
                "group_key": _normalize_doc_name(name),
            },
        )

    return result
