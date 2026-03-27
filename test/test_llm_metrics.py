from __future__ import annotations

from backend.services.llm_metrics import (  # pyright: ignore[reportMissingImports]
    get_usage,
    record_usage,
    reset_usage,
)


def test_record_and_get_usage() -> None:
    reset_usage()
    record_usage(10, 20, 30)
    record_usage(5, 10, 15)

    stats = get_usage()
    assert stats["prompt_tokens"] == 15
    assert stats["completion_tokens"] == 30
    assert stats["total_tokens"] == 45
    assert stats["request_count"] == 2


def test_reset_usage() -> None:
    reset_usage()
    record_usage(100, 200, 300)
    reset_usage()

    stats = get_usage()
    assert stats["total_tokens"] == 0
    assert stats["request_count"] == 0
