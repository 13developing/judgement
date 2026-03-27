from __future__ import annotations

# pyright: reportPrivateUsage=false

from backend.services.question_matcher import (
    _SENTINEL,
    _cache_key,
    _get_cached,
    _match_cache,
    _set_cache,
)


def test_cache_key_deterministic() -> None:
    assert _cache_key("hello world") == _cache_key("hello world")
    assert _cache_key("hello world") == _cache_key("  Hello World  ")


def test_cache_set_and_get() -> None:
    _match_cache.clear()
    key = "test-key"

    _set_cache(key, 42)
    result = _get_cached(key)

    assert result == 42


def test_cache_miss_returns_sentinel() -> None:
    _match_cache.clear()
    result = _get_cached("nonexistent")
    assert result is _SENTINEL
