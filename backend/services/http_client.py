"""Shared httpx.AsyncClient with connection pooling.

Usage::
    from backend.services.http_client import get_http_client
    client = get_http_client()
    resp = await client.post(url, ...)
"""

from __future__ import annotations

import httpx

_client: httpx.AsyncClient | None = None


def get_http_client() -> httpx.AsyncClient:
    """Return the shared async HTTP client. Raises if not initialized."""
    if _client is None:
        raise RuntimeError("HTTP client not initialized. Call startup_http_client() first.")
    return _client


async def startup_http_client() -> None:
    """Create the shared client. Call during app startup."""
    global _client  # noqa: PLW0603
    _client = httpx.AsyncClient(
        timeout=httpx.Timeout(120.0, connect=10.0),
        limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        follow_redirects=True,
    )


async def shutdown_http_client() -> None:
    """Close the shared client. Call during app shutdown."""
    global _client  # noqa: PLW0603
    if _client is not None:
        await _client.aclose()
        _client = None
