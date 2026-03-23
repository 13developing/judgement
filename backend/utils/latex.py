"""LaTeX → readable plain-text conversion.

Used as a fallback when the frontend KaTeX renderer is unavailable.
"""

from __future__ import annotations

_REPLACEMENTS: list[tuple[str, str]] = [
    (r"\frac{", "("),
    (r"}{", ")/("),
    (r"\sqrt{", "√("),
    (r"\pi", "π"),
    (r"\infty", "∞"),
    (r"\int", "∫"),
    (r"\sum", "Σ"),
    (r"\partial", "∂"),
    (r"\alpha", "α"),
    (r"\beta", "β"),
    (r"\gamma", "γ"),
    (r"\delta", "δ"),
    (r"\epsilon", "ε"),
    (r"\theta", "θ"),
    (r"\lambda", "λ"),
    (r"\mu", "μ"),
    (r"\sigma", "σ"),
    (r"\omega", "ω"),
    (r"\leq", "≤"),
    (r"\geq", "≥"),
    (r"\neq", "≠"),
    (r"\approx", "≈"),
    (r"\times", "×"),
    (r"\cdot", "·"),
    (r"\pm", "±"),
    (r"\rightarrow", "→"),
    (r"\leftarrow", "←"),
    (r"\lim", "lim"),
    (r"\\", "\n"),
    (r"\,", " "),
    (r"\;", " "),
]


def format_latex_to_text(text: str) -> str:
    """Replace common LaTeX commands with Unicode equivalents."""
    for old, new in _REPLACEMENTS:
        text = text.replace(old, new)
    return text
