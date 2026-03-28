"""Utility functions for robust document text processing and question extraction."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Regex patterns for question boundary detection
# ---------------------------------------------------------------------------

# Question number patterns (compiled once for performance)
_QUESTION_NUM_PATTERNS: list[re.Pattern[str]] = [
    # "1." "1．" "1。" "1、" "1)" "1）"
    re.compile(r"^\s*(\d+)\s*[.．。、\)）]", re.MULTILINE),
    # "(1)" "（1）"
    re.compile(r"^\s*[（(]\s*(\d+)\s*[)）]", re.MULTILINE),
    # "第1题" "第 1 题"
    re.compile(r"^\s*第\s*(\d+)\s*题", re.MULTILINE),
]

# Section header patterns (these mark question type sections, not individual questions)
_SECTION_HEADER_RE = re.compile(
    r"^\s*(?:(?:一|二|三|四|五|六|七|八|九|十)[、.．]"
    + r"|(?:填空题|选择题|简答题|计算题|证明题|解答题|判断题|论述题|应用题))",
    re.MULTILINE,
)

# Unified boundary regex that matches any question start
_BOUNDARY_RE = re.compile(
    r"(?:^|\n)"
    + r"(?:"
    + r"\s*\d+\s*[.．。、\)）]"  # 1. / 1、 / 1）
    + r"|\s*[（(]\s*\d+\s*[)）]"  # (1) / （1）
    + r"|\s*第\s*\d+\s*题"  # 第1题
    + r"|\s*(?:一|二|三|四|五|六|七|八|九|十)[、.．]"  # 一、
    + r"|\s*(?:填空题|选择题|简答题|计算题|证明题|解答题|判断题|论述题|应用题)"
    + r")",
    re.MULTILINE,
)


# ---------------------------------------------------------------------------
# JSON extraction
# ---------------------------------------------------------------------------


def extract_json_from_text(raw: str) -> Any:
    """Robustly extract JSON from LLM output that may be wrapped in markdown or extra text.

    Strategy:
    1. Strip markdown code fences
    2. Try json.loads on cleaned string
    3. Regex-find outermost [...] or {...}
    4. Raise ValueError if nothing works
    """
    if not raw or not raw.strip():
        raise ValueError("无法从模型输出中提取 JSON：输入为空")

    cleaned = raw.strip()

    # Step 1: Strip markdown code fences
    cleaned = _strip_code_fences(cleaned)

    # Step 2: Try direct parse
    parsed = _try_json_loads(cleaned)
    if parsed is not None:
        return parsed

    # Step 3: Try to find JSON array or object via regex
    # Look for outermost [...] first (most common for question lists)
    for pattern in [
        re.compile(r"\[[\s\S]*\]"),  # Array
        re.compile(r"\{[\s\S]*\}"),  # Object
    ]:
        match = pattern.search(cleaned)
        if match:
            candidate = match.group(0)
            parsed = _try_json_loads(candidate)
            if parsed is not None:
                log.debug("Extracted JSON via regex fallback (%d chars)", len(candidate))
                return parsed

    # Step 4: Last resort — try stripping trailing commas and retrying
    no_trailing = re.sub(r",\s*([}\]])", r"\1", cleaned)
    parsed = _try_json_loads(no_trailing)
    if parsed is not None:
        log.debug("Extracted JSON after removing trailing commas")
        return parsed

    log.warning("Failed to extract JSON from LLM output (%d chars): %s...", len(raw), raw[:200])
    raise ValueError("无法从模型输出中提取 JSON")


def _strip_code_fences(text: str) -> str:
    """Remove markdown code fences like ```json ... ``` from text."""
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json|JSON|text)?\s*\n?", "", stripped)
        stripped = re.sub(r"\n?```\s*$", "", stripped)
    return stripped.strip()


def _try_json_loads(text: str) -> Any | None:
    """Try to parse JSON, return None on failure instead of raising."""
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Text chunking
# ---------------------------------------------------------------------------


def chunk_text(text: str, max_chars: int = 12000, overlap: int = 500) -> list[str]:
    """Split text into chunks suitable for LLM processing.

    Tries to split at paragraph boundaries (double-newline), then single
    newlines, then character boundaries as last resort.  Each chunk except
    the first includes ``overlap`` characters from the previous chunk's end
    for context continuity.
    """
    if not text:
        return [""]
    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    start = 0

    while start < len(text):
        end = start + max_chars

        if end >= len(text):
            chunks.append(text[start:])
            break

        # Try to find a paragraph boundary (double newline) near the end
        boundary = text.rfind("\n\n", start + max_chars // 2, end)
        if boundary != -1:
            end = boundary + 2  # Include the double newline
        else:
            # Try single newline
            boundary = text.rfind("\n", start + max_chars // 2, end)
            if boundary != -1:
                end = boundary + 1
            # else: hard split at max_chars (end stays as is)

        chunks.append(text[start:end])

        # Next chunk starts with overlap from previous
        next_start = max(end - overlap, start + 1)
        if next_start <= start:
            next_start = end  # Safety: avoid infinite loop
        start = next_start

    log.debug("Split text (%d chars) into %d chunks", len(text), len(chunks))
    return chunks


# ---------------------------------------------------------------------------
# Question pre-segmentation
# ---------------------------------------------------------------------------


def pre_segment_questions(text: str) -> list[dict[str, str]]:
    """Use regex to detect question boundaries in exam paper text.

    Returns a list of dicts with keys ``sequence_no`` (str) and ``raw_text``.
    If no question patterns are found, returns a single segment with the full text.
    """
    if not text or not text.strip():
        return [{"sequence_no": "1", "raw_text": text or ""}]

    # Find all boundary positions
    boundaries: list[tuple[int, str]] = []  # (position, sequence_no_or_label)

    for line_match in re.finditer(r"^(.+)$", text, re.MULTILINE):
        line = line_match.group(1)
        line_start = line_match.start()

        # Check if this line is a section header (not a numbered question)
        if _SECTION_HEADER_RE.match(line):
            boundaries.append((line_start, "section"))
            continue

        # Check numbered question patterns
        for pat in _QUESTION_NUM_PATTERNS:
            m = pat.match(line)
            if m:
                boundaries.append((line_start, m.group(1)))
                break

    if not boundaries:
        log.debug("No question boundaries detected, returning full text as single segment")
        return [{"sequence_no": "1", "raw_text": text.strip()}]

    # Build segments
    segments: list[dict[str, str]] = []
    pending_section_text = ""  # Text from section headers to prepend to next question

    for i, (pos, label) in enumerate(boundaries):
        # Determine end of this segment
        next_pos = boundaries[i + 1][0] if i + 1 < len(boundaries) else len(text)
        raw_text = text[pos:next_pos].strip()

        if label == "section":
            # Section headers are prepended to the next question
            pending_section_text += raw_text + "\n"
            continue

        if pending_section_text:
            raw_text = pending_section_text + raw_text
            pending_section_text = ""

        segments.append(
            {
                "sequence_no": label,
                "raw_text": raw_text,
            }
        )

    # If there's trailing section text with no following question, add it as a segment
    if pending_section_text:
        segments.append(
            {
                "sequence_no": str(len(segments) + 1),
                "raw_text": pending_section_text.strip(),
            }
        )

    log.debug("Pre-segmented text into %d question boundaries", len(segments))
    return segments if segments else [{"sequence_no": "1", "raw_text": text.strip()}]


# ---------------------------------------------------------------------------
# Question validation
# ---------------------------------------------------------------------------


def validate_parsed_questions(questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Post-process and validate a list of parsed question dicts.

    - Removes empty or too-short entries
    - Deduplicates by exact content match
    - Ensures sequential numbering
    - Normalizes question_type to allowed values
    """
    _VALID_TYPES = {"fill_blank", "short_answer", "calculation"}
    seen_contents: set[str] = set()
    cleaned: list[dict[str, Any]] = []

    for q in questions:
        content = str(q.get("content") or "").strip()

        # Skip empty or too-short entries
        if len(content) < 4:
            log.debug("Skipping question with short content: %r", content[:30])
            continue

        # Deduplicate by exact content match (after whitespace normalization)
        normalized = re.sub(r"\s+", " ", content)
        if normalized in seen_contents:
            log.debug("Skipping duplicate question: %s...", content[:40])
            continue
        seen_contents.add(normalized)

        # Normalize question_type
        qtype = str(q.get("question_type") or "short_answer").strip().lower()
        if qtype not in _VALID_TYPES:
            qtype = _infer_question_type(qtype, content)

        cleaned.append(
            {
                **q,
                "content": content,
                "question_type": qtype,
            }
        )

    # Re-number sequentially
    for idx, item in enumerate(cleaned, start=1):
        item["sequence_no"] = idx

    if len(cleaned) < len(questions):
        log.info(
            "Validation: %d → %d questions (removed %d invalid/duplicate)",
            len(questions),
            len(cleaned),
            len(questions) - len(cleaned),
        )

    return cleaned


def _infer_question_type(raw_type: str, content: str) -> str:
    """Infer question type from raw type string or content hints."""
    raw_type = raw_type.lower()

    if any(kw in raw_type for kw in ("填空", "blank", "fill")):
        return "fill_blank"
    if any(kw in raw_type for kw in ("计算", "证明", "积分", "极限", "导数", "calc", "proof")):
        return "calculation"
    if any(kw in raw_type for kw in ("简答", "论述", "short", "essay")):
        return "short_answer"

    # Try to infer from content
    if re.search(r"_{2,}|（\s*）|\(\s*\)", content):
        return "fill_blank"
    if re.search(r"计算|求解|解方程|证明|求导|求积分|求极限", content):
        return "calculation"

    return "short_answer"
