"""Simple question matcher — finds the best-matching question in the bank."""

from __future__ import annotations

from sqlmodel import Session, select

from backend.models import Question


def find_matching_question(
    session: Session,
    recognized_content: str,
) -> Question | None:
    """Return the question whose content is most similar, or None."""
    questions = session.exec(select(Question)).all()
    if not questions:
        return None

    best: Question | None = None
    best_score = 0.0

    for q in questions:
        score = _jaccard(recognized_content, q.content)
        if score > best_score and score > 0.25:
            best_score = score
            best = q

    return best


def _jaccard(a: str, b: str) -> float:
    """Character-level Jaccard similarity (quick approximation)."""
    sa = set(a.replace(" ", ""))
    sb = set(b.replace(" ", ""))
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)
