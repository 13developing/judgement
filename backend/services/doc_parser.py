"""Parse Word (.docx) and PDF files to extract question-answer pairs."""

from __future__ import annotations

import re
from pathlib import Path


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_document(file_path: str) -> list[dict]:
    """Dispatch to the correct parser based on file extension."""
    ext = Path(file_path).suffix.lower()
    if ext == ".docx":
        return _parse_docx(file_path)
    if ext == ".pdf":
        return _parse_pdf(file_path)
    raise ValueError(f"不支持的文件类型：{ext}")


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------


def _parse_docx(file_path: str) -> list[dict]:
    import docx  # python-docx

    doc = docx.Document(file_path)
    full_text = "\n".join(p.text.strip() for p in doc.paragraphs if p.text.strip())
    return _extract_qa_pairs(full_text)


def _parse_pdf(file_path: str) -> list[dict]:
    import pdfplumber

    pages: list[str] = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages.append(text)
    return _extract_qa_pairs("\n".join(pages))


# ---------------------------------------------------------------------------
# Question-answer extraction
# ---------------------------------------------------------------------------

# Matches common numbering: "1." / "1、" / "（1）" / "(1)" / "第1题"
_NUM_PATTERN = re.compile(
    r"(?:^|\n)\s*(?:"
    r"(\d+)\s*[.、．]"
    r"|[（(]\s*(\d+)\s*[）)]"
    r"|第\s*(\d+)\s*题"
    r")",
)

_ANSWER_PATTERN = re.compile(
    r"\n\s*(?:答案|参考答案|解答|解|答)\s*[:：]\s*",
)


def _extract_qa_pairs(text: str) -> list[dict]:
    """Split raw text into question-answer dicts."""
    # Find all split positions
    matches = list(_NUM_PATTERN.finditer(text))
    if not matches:
        # Fallback: treat the entire text as one question
        return [
            {
                "content": text.strip(),
                "question_type": _guess_type(text),
                "standard_answer": None,
            }
        ]

    results: list[dict] = []
    for idx, m in enumerate(matches):
        start = m.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        body = text[start:end].strip()

        # Try to separate answer from question body
        answer: str | None = None
        ans_match = _ANSWER_PATTERN.search(body)
        if ans_match:
            answer = body[ans_match.end() :].strip() or None
            body = body[: ans_match.start()].strip()

        if body:
            results.append(
                {
                    "content": body,
                    "question_type": _guess_type(body),
                    "standard_answer": answer,
                }
            )

    return results


def _guess_type(text: str) -> str:
    fill_kw = ("填空", "____", "___", "（  ）", "(  )")
    calc_kw = ("求", "计算", "证明", "解方程", "积分", "微分", "极限", "求解", "求导")
    for kw in fill_kw:
        if kw in text:
            return "fill_blank"
    for kw in calc_kw:
        if kw in text:
            return "calculation"
    return "short_answer"
