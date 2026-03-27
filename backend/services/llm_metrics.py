"""In-memory LLM token usage tracking."""

from __future__ import annotations

import threading
from dataclasses import dataclass


@dataclass
class UsageRecord:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    request_count: int = 0


_lock = threading.Lock()
_usage = UsageRecord()


def record_usage(prompt_tokens: int, completion_tokens: int, total_tokens: int) -> None:
    """Record token usage from a single LLM call."""
    with _lock:
        _usage.prompt_tokens += prompt_tokens
        _usage.completion_tokens += completion_tokens
        _usage.total_tokens += total_tokens
        _usage.request_count += 1


def get_usage() -> dict[str, int]:
    """Return accumulated usage stats."""
    with _lock:
        return {
            "prompt_tokens": _usage.prompt_tokens,
            "completion_tokens": _usage.completion_tokens,
            "total_tokens": _usage.total_tokens,
            "request_count": _usage.request_count,
        }


def reset_usage() -> None:
    """Reset all counters (mainly for testing)."""
    global _usage  # noqa: PLW0603
    with _lock:
        _usage = UsageRecord()
