"""Tests for the shared HTTP client lifecycle."""

from __future__ import annotations

import pytest

from backend.services.http_client import (
    get_http_client,
    shutdown_http_client,
    startup_http_client,
)


@pytest.mark.asyncio
async def test_client_not_initialized_raises() -> None:
    """get_http_client() raises RuntimeError before startup."""
    # Ensure clean state
    await shutdown_http_client()
    with pytest.raises(RuntimeError, match="not initialized"):
        get_http_client()


@pytest.mark.asyncio
async def test_client_lifecycle() -> None:
    """startup creates client, get returns it, shutdown closes it."""
    await startup_http_client()
    client = get_http_client()
    assert client is not None
    assert not client.is_closed

    await shutdown_http_client()

    # After shutdown, should raise again
    with pytest.raises(RuntimeError):
        get_http_client()
