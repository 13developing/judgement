"""Model-driven document import for exam papers and answer files."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from backend.schemas import ParsedDocumentBundle, ParsedQuestion
from backend.services.doc_parser import extract_document_text
from backend.services.llm_client import chat_text
from backend.services.text_utils import (
    chunk_text,
    extract_json_from_text,
    validate_parsed_questions,
)

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_CONTENT_RETRIES = 2  # Retry LLM call when output is unparseable
_CHUNK_MAX_CHARS = 12000  # Max chars per LLM extraction chunk
_EXTRACT_MAX_TOKENS = 8000  # Token budget for question extraction

_EXTRACT_SYSTEM_PROMPT = """\
你是一名大学数学题库整理助手。

任务：从试卷或答案文档的原始文本中提取结构化题目。

要求：
- 只输出 JSON 数组，不要输出任何解释、注释或 markdown
- 过滤页码、考试须知、签名区、分值说明、评阅人、章节标题等版式噪音
- 保留真正题干、选项、公式
- sequence_no 表示题号；如果无法确定，尽量根据上下文推断连续编号
- question_type 只能是以下三种之一：fill_blank、short_answer、calculation
- 对答案文档，content 填答案内容，standard_answer 也填答案内容
- 如果文本中有数学公式，保留原始 LaTeX 格式

输出格式示例：
[
  {"sequence_no": 1, "question_type": "short_answer", "content": "题面...", "standard_answer": null},
  {"sequence_no": 2, "question_type": "calculation", "content": "题面...", "standard_answer": "答案..."}
]"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def build_import_bundles(
    files: list[Path], filenames: list[str]
) -> tuple[str, list[ParsedQuestion], list[ParsedDocumentBundle]]:
    """Parse uploaded documents and build structured import bundles."""
    log.info("Building import bundles for %d files: %s", len(filenames), filenames)

    file_roles = await _classify_files_with_model(filenames)
    log.info("File roles: %s", file_roles)

    exam_files: dict[str, tuple[str, list[ParsedQuestion]]] = {}
    answer_files: dict[str, tuple[str, list[ParsedQuestion]]] = {}

    for file_path, filename in zip(files, filenames, strict=True):
        role_info = file_roles.get(
            filename, {"role": "exam", "group_key": _normalize_doc_name(filename)}
        )
        is_answer = role_info["role"] == "answer"

        log.info("Processing file %r as %s", filename, "answer" if is_answer else "exam")
        raw_text = await extract_document_text(str(file_path))
        log.info("Extracted %d chars from %r", len(raw_text), filename)

        parsed_questions = await _extract_questions_with_model(
            raw_text, is_answer=is_answer, filename=filename
        )
        log.info("Extracted %d questions from %r", len(parsed_questions), filename)

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
            log.info("Matching exam %r with answer %r", exam_name, answer_name)
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
    log.info("Import summary: %s, total questions: %d", summary, len(flattened_questions))
    return summary, flattened_questions, bundles


# ---------------------------------------------------------------------------
# Question extraction (with chunking and retry)
# ---------------------------------------------------------------------------


async def _extract_questions_with_model(
    raw_text: str, *, is_answer: bool, filename: str
) -> list[ParsedQuestion]:
    """Extract structured questions from document text using LLM.

    Improvements over original:
    - Splits long text into chunks to avoid truncation
    - Retries on unparseable LLM output
    - Validates and deduplicates results
    """
    mode = "答案文档" if is_answer else "试卷文档"

    # Chunk the text if it's too long
    chunks = chunk_text(raw_text, max_chars=_CHUNK_MAX_CHARS)
    log.info("Processing %r: %d chars in %d chunk(s)", filename, len(raw_text), len(chunks))

    all_raw_items: list[dict[str, Any]] = []

    for chunk_idx, chunk in enumerate(chunks):
        chunk_context = ""
        if len(chunks) > 1:
            chunk_context = f"（第 {chunk_idx + 1}/{len(chunks)} 段）"

        user_prompt = (
            f"下面是{mode}的原始文本{chunk_context}，请抽取结构化题目列表。\n"
            "严格返回 JSON 数组，每项格式为：\n"
            '{"sequence_no": 1, "question_type": "short_answer", '
            '"content": "...", "standard_answer": "...或null"}\n'
            f"文件名：{filename}\n\n"
            f"原始文本：\n{chunk}"
        )

        raw_items = await _call_llm_with_content_retry(
            system_prompt=_EXTRACT_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            context_label=f"{filename} chunk {chunk_idx + 1}",
        )
        all_raw_items.extend(raw_items)

    # Validate and clean
    validated = validate_parsed_questions(all_raw_items)

    # Convert to ParsedQuestion models
    questions: list[ParsedQuestion] = []
    for item in validated:
        content = str(item.get("content") or "").strip()
        standard_answer = item.get("standard_answer")
        if is_answer and not standard_answer:
            standard_answer = content
        questions.append(
            ParsedQuestion(
                sequence_no=item.get("sequence_no") or len(questions) + 1,
                content=content,
                question_type=item.get("question_type", "short_answer"),
                standard_answer=str(standard_answer).strip()
                if standard_answer is not None
                else None,
                source_file=filename,
            )
        )

    return questions


async def _call_llm_with_content_retry(
    *,
    system_prompt: str,
    user_prompt: str,
    context_label: str,
) -> list[dict[str, Any]]:
    """Call LLM and retry if the output cannot be parsed as a JSON array.

    Returns the parsed list of dicts. Retries up to _MAX_CONTENT_RETRIES times
    with increasingly explicit instructions.
    """
    last_error: Exception | None = None

    for attempt in range(_MAX_CONTENT_RETRIES + 1):
        prompt = user_prompt
        if attempt > 0:
            # Add stronger hint on retry
            prompt = (
                "【重要：上次你的回复不是合法 JSON，请这次务必只输出 JSON 数组，"
                "不要加任何解释文字、markdown 代码块或其他内容】\n\n" + user_prompt
            )
            log.warning(
                "Content retry %d/%d for %s (previous error: %s)",
                attempt,
                _MAX_CONTENT_RETRIES,
                context_label,
                last_error,
            )

        try:
            raw = await chat_text(
                system_prompt=system_prompt,
                user_prompt=prompt,
                temperature=0.0,
                max_tokens=_EXTRACT_MAX_TOKENS,
            )

            log.debug("LLM response for %s (%d chars): %s...", context_label, len(raw), raw[:200])

            data = extract_json_from_text(raw)

            if isinstance(data, dict):
                # Model returned a single object — wrap in list
                data = [data]
            if not isinstance(data, list):
                raise ValueError(f"期望 JSON 数组，实际得到 {type(data).__name__}")

            # Filter to only valid dicts
            items = [item for item in data if isinstance(item, dict)]
            log.info("Parsed %d question items from %s", len(items), context_label)
            return items

        except (ValueError, TypeError) as exc:
            last_error = exc
            log.warning("Failed to parse LLM output for %s: %s", context_label, exc)

    # All retries exhausted — return empty list instead of crashing
    log.error(
        "All %d content retries exhausted for %s. Last error: %s",
        _MAX_CONTENT_RETRIES + 1,
        context_label,
        last_error,
    )
    return []


# ---------------------------------------------------------------------------
# Question matching
# ---------------------------------------------------------------------------


async def _match_questions_with_model(
    exam_questions: list[ParsedQuestion],
    answer_questions: list[ParsedQuestion],
    exam_name: str,
    answer_name: str,
) -> list[ParsedQuestion]:
    """Merge exam and answer questions using LLM."""
    user_prompt = (
        "请把试卷题目和答案条目直接合并成可入库的题目列表。\n"
        "严格返回 JSON 数组，每项格式为：\n"
        '{"sequence_no": 1, "question_type": "short_answer", '
        '"content": "题面", "standard_answer": "标准答案或null"}\n'
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

    items = await _call_llm_with_content_retry(
        system_prompt="你是一名大学数学题库整理助手，只输出 JSON 数组。",
        user_prompt=user_prompt,
        context_label=f"match {exam_name}+{answer_name}",
    )

    validated = validate_parsed_questions(items)

    return [
        ParsedQuestion(
            sequence_no=item.get("sequence_no") or idx,
            content=str(item.get("content") or "").strip(),
            question_type=item.get("question_type", "short_answer"),
            standard_answer=str(item["standard_answer"]).strip()
            if item.get("standard_answer") is not None
            else None,
            source_file=exam_name,
        )
        for idx, item in enumerate(validated, start=1)
    ]


# ---------------------------------------------------------------------------
# File classification
# ---------------------------------------------------------------------------


async def _classify_files_with_model(filenames: list[str]) -> dict[str, dict[str, str]]:
    """Classify uploaded files as exam/answer and group them by name similarity."""
    if not filenames:
        return {}

    user_prompt = (
        "请判断下面每个文件名更像试卷、答案，还是无法判断。\n"
        "同时把属于同一套试卷/答案的文件分到同一个 group_key。\n"
        "严格返回 JSON 数组，每项格式为：\n"
        '{"filename": "xx.pdf", "role": "exam|answer|unknown", '
        '"group_key": "同套文件键"}\n'
        "如果无法判断 role，优先返回 exam。\n"
        "group_key 请尽量让同一套试卷和答案一致。\n\n"
        "文件名列表：\n" + "\n".join(f"- {name}" for name in filenames)
    )

    try:
        raw = await chat_text(
            system_prompt="你是一名试卷文件归类助手，只输出 JSON 数组。",
            user_prompt=user_prompt,
            temperature=0.0,
            max_tokens=1200,
        )
        data = extract_json_from_text(raw)
    except (ValueError, TypeError) as exc:
        log.warning("File classification LLM call failed (%s), using filename heuristics", exc)
        return _classify_files_by_name(filenames)

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

    # Fill in any missing filenames with heuristic fallback
    for name in filenames:
        result.setdefault(
            name,
            {
                "role": "answer" if _is_answer_filename(name) else "exam",
                "group_key": _normalize_doc_name(name),
            },
        )

    return result


def _classify_files_by_name(filenames: list[str]) -> dict[str, dict[str, str]]:
    """Fallback: classify files purely by filename heuristics."""
    return {
        name: {
            "role": "answer" if _is_answer_filename(name) else "exam",
            "group_key": _normalize_doc_name(name),
        }
        for name in filenames
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _format_question_list(questions: list[ParsedQuestion]) -> str:
    return "\n".join(
        f"- 题号 {q.sequence_no or idx} | 题型 {q.question_type} | 内容 {_compact_text(q.content)}"
        for idx, q in enumerate(questions, start=1)
    )


def _compact_text(text: str, max_len: int = 220) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    return text[:max_len] + ("..." if len(text) > max_len else "")


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
