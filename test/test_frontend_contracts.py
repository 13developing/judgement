from __future__ import annotations

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
BANK_HTML = (ROOT / "frontend/bank.html").read_text(encoding="utf-8")
STYLE_CSS = (ROOT / "frontend/static/css/style.css").read_text(encoding="utf-8")


def missing_tokens(content: str, tokens: list[str]) -> list[str]:
    return [token for token in tokens if token not in content]


class FrontendContractTests(unittest.TestCase):
    def test_judge_page_keeps_runtime_hooks_and_gains_shell(self) -> None:
        required = [
            'class="container page-shell judge-page"',
            'class="page-header page-header-featured"',
            'class="workspace judge-workspace"',
            'class="panel judge-panel judge-input-panel"',
            'class="panel judge-panel judge-result-panel"',
            'id="judge-form"',
            'id="image-input"',
            'id="image-preview"',
            'id="upload-area"',
            'id="submit-btn"',
            'id="error-message"',
            'id="manual-answer-group"',
            'id="result-placeholder"',
            'id="result-content"',
            'id="res-score"',
            'id="res-total"',
            'id="res-type"',
            'id="res-judgment"',
            'id="res-recognized"',
            'id="res-explanation"',
            'id="res-steps-container"',
            'id="standard-answer"',
            'name="judge_mode"',
            'id="res-steps-table"',
            "katex.min.css",
            "auto-render.min.js",
        ]
        self.assertEqual([], missing_tokens(INDEX_HTML, required))

    def test_bank_page_keeps_runtime_hooks_and_gains_shell(self) -> None:
        required = [
            'class="container page-shell bank-page"',
            'class="page-header page-header-featured"',
            'class="bank-actions"',
            'class="panel import-panel"',
            'class="panel bank-data-panel"',
            'id="doc-input"',
            'id="upload-doc-btn"',
            'id="preview-container"',
            'id="preview-count"',
            'id="confirm-import-btn"',
            'id="toggle-manual-btn"',
            'id="manual-add-form"',
            'id="cancel-manual-btn"',
            'id="add-q-form"',
            'id="save-manual-btn"',
            'id="search-keyword"',
            'id="filter-type"',
            'id="search-btn"',
            'id="load-more-btn"',
            'id="add-q-type"',
            'id="add-q-content"',
            'id="add-q-answer"',
            'id="preview-table"',
            'id="bank-table"',
            'class="btn btn-danger delete-btn"',
            "katex.min.css",
            "auto-render.min.js",
        ]
        self.assertEqual([], missing_tokens(BANK_HTML, required))

    def test_shared_css_contains_base_layout_contracts(self) -> None:
        required = [
            "--success",
            "--error",
            "--accent",
            "--text-secondary",
            ".hidden",
            ".loading .spinner",
            ".upload-area.dragover",
            ".page-shell",
            ".page-header",
            ".workspace",
            ".panel",
            ".page-eyebrow",
            ".page-title",
            ".page-description",
        ]
        self.assertEqual([], missing_tokens(STYLE_CSS, required))

    def test_judge_page_uses_workstation_sections(self) -> None:
        required = [
            'class="panel-section"',
            'class="section-heading"',
            'class="option-grid"',
            'class="option-card"',
            'class="state-message error-message hidden"',
            'class="result-stack"',
            'class="result-summary"',
            'class="score-total"',
            'class="result-section"',
            'class="section-title"',
            'id="manual-answer-group"',
            'id="result-placeholder"',
            'id="result-content"',
            'id="res-steps-container"',
        ]
        self.assertEqual([], missing_tokens(INDEX_HTML, required))

    def test_judge_page_has_no_inline_styles(self) -> None:
        self.assertNotIn("style=", INDEX_HTML)

    def test_bank_page_uses_management_sections(self) -> None:
        required = [
            'class="bank-actions"',
            'class="import-row"',
            'class="preview-footer"',
            'class="manual-panel hidden mb-3"',
            'class="filter-toolbar"',
            'class="toolbar-group"',
            'class="table-panel"',
            'class="table-scroll"',
            'class="button-row button-row-end"',
            'class="load-more-row"',
            'id="preview-container"',
            'id="manual-add-form"',
            'id="search-keyword"',
            'id="filter-type"',
            'id="search-btn"',
            'id="load-more-btn"',
        ]
        self.assertEqual([], missing_tokens(BANK_HTML, required))

    def test_bank_page_has_no_inline_styles(self) -> None:
        self.assertNotIn("style=", BANK_HTML)

    def test_shared_css_contains_final_state_and_responsive_rules(self) -> None:
        required = [
            ".result-placeholder.state-message",
            ".preview-panel",
            ".result-section.table-panel",
            ".navbar",
            "@media (max-width: 960px)",
            "@media (max-width: 768px)",
            "--success",
            "--error",
            "--accent",
            "--text-secondary",
            ".hidden",
            ".loading .spinner",
            ".upload-area.dragover",
        ]
        self.assertEqual([], missing_tokens(STYLE_CSS, required))


if __name__ == "__main__":
    _ = unittest.main()
