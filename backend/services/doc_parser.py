"""Extract raw text from Word/PDF documents."""

from __future__ import annotations

import base64
import io
import logging
import re
import unicodedata
from pathlib import Path

from backend.services.llm_client import chat_with_image


log = logging.getLogger(__name__)

_MAX_OCR_PAGES = 20  # Maximum pages to OCR (safety limit for very long documents)


async def extract_document_text(file_path: str) -> str:
    """Extract raw text from a document, using OCR fallback for PDFs."""
    ext = Path(file_path).suffix.lower()
    log.info("Extracting text from %s (%s)", file_path, ext)
    if ext == ".docx":
        return _extract_docx_text(file_path)
    if ext == ".pdf":
        return await _extract_pdf_text(file_path)
    raise ValueError(f"不支持的文件类型：{ext}")


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------


def _extract_docx_text(file_path: str) -> str:
    import docx  # pyright: ignore[reportMissingImports]  # python-docx

    doc = docx.Document(file_path)
    parts: list[str] = []
    paragraph_count = 0
    table_cell_count = 0

    for element in doc.element.body:
        tag = element.tag.split("}")[-1] if "}" in element.tag else element.tag
        if tag == "p":
            # Paragraph
            para = element
            text = "".join(node.text or "" for node in para.iter() if node.text)
            text = text.strip()
            if text:
                parts.append(text)
                paragraph_count += 1
        elif tag == "tbl":
            # Table — extract row by row, tab-separated
            for tr in element.iter():
                tr_tag = tr.tag.split("}")[-1] if "}" in tr.tag else tr.tag
                if tr_tag == "tr":
                    cells: list[str] = []
                    for tc in tr.iter():
                        tc_tag = tc.tag.split("}")[-1] if "}" in tc.tag else tc.tag
                        if tc_tag == "tc":
                            cell_text = "".join(
                                node.text or "" for node in tc.iter() if node.text
                            ).strip()
                            if cell_text:
                                cells.append(cell_text)
                                table_cell_count += 1
                    if cells:
                        parts.append("\t".join(cells))

    log.debug("DOCX extracted %d paragraphs, %d table cells", paragraph_count, table_cell_count)
    return "\n".join(parts)


async def _extract_pdf_text(file_path: str) -> str:
    import pdfplumber

    pages: list[str] = []
    total_pages = 0
    pages_with_text = 0
    with pdfplumber.open(file_path) as pdf:
        total_pages = len(pdf.pages)
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages.append(text)
                pages_with_text += 1

    merged_text = "\n".join(pages).strip()
    log.info("PDF pdfplumber extracted %d chars from %d pages", len(merged_text), len(pages))
    log.debug("PDF pdfplumber pages with text: %d/%d", pages_with_text, total_pages)
    if merged_text and not _looks_garbled(merged_text):
        return merged_text
    if merged_text:
        log.warning("PDF text looks garbled, falling back to LLM OCR")

    llm_text = await _parse_pdf_with_llm(file_path)
    if llm_text.strip():
        return llm_text

    return merged_text


def _looks_garbled(text: str) -> bool:
    if not text:
        return False

    suspicious_count = sum(1 for ch in text if ch == "\ufffd" or unicodedata.category(ch) == "Co")
    if suspicious_count >= 3:
        return True
    if suspicious_count / max(len(text), 1) > 0.01:
        return True

    # Low information density check
    meaningful = sum(1 for ch in text if ch.isalnum() or "\u4e00" <= ch <= "\u9fff")
    if meaningful / max(len(text), 1) < 0.3:
        log.warning(
            "PDF text has low information density (%.1f%%), treating as garbled",
            meaningful / max(len(text), 1) * 100,
        )
        return True

    return False


async def _parse_pdf_with_llm(file_path: str) -> str:
    import pdfplumber

    rendered_pages: list[str] = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages[:_MAX_OCR_PAGES]:
            page_image = page.to_image(resolution=144).original.convert("RGB")
            rendered_pages.append(_image_to_base64(page_image))

    page_texts: list[str] = []
    for idx, image_base64 in enumerate(rendered_pages, start=1):
        raw = await chat_with_image(
            system_prompt=(
                "你是一名试卷文本整理助手。请忠实转写图片中的中文、数学题面和答案内容。"
                "只输出纯文本，不要加解释，不要使用 markdown 代码块。"
                "如果出现数学公式，必须输出为可直接被 KaTeX 渲染的 LaTeX。"
            ),
            user_prompt=(
                f"请按阅读顺序转写第 {idx} 页内容。保留题号、换行，以及“答案：”“解：”等标记。"
                "若存在数学公式，统一使用  或  包裹的规范 LaTeX，不要输出 、、 这类普通文本公式。"
            ),
            image_base64=image_base64,
            max_tokens=3000,
        )
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:text)?\s*\n?", "", cleaned)
            cleaned = re.sub(r"\n?```\s*$", "", cleaned)
        page_texts.append(cleaned)

    log.info("LLM OCR completed for %d pages", len(rendered_pages))
    return "\n\n".join(page_texts)


def _image_to_base64(image) -> str:
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")
