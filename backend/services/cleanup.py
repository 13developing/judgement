"""Periodic cleanup of old uploaded files."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from pathlib import Path

from backend.config import UPLOAD_DIR

log = logging.getLogger(__name__)

# Files older than this (seconds) are candidates for removal.
MAX_FILE_AGE_SECONDS: int = 24 * 60 * 60  # 24 hours
# How often to run the cleanup sweep.
CLEANUP_INTERVAL_SECONDS: int = 60 * 60  # 1 hour

_task: asyncio.Task[None] | None = None


def cleanup_old_files(directory: Path, max_age_seconds: int = MAX_FILE_AGE_SECONDS) -> int:
    """Delete files in *directory* older than *max_age_seconds*. Returns count deleted."""
    if not directory.exists():
        return 0
    now = time.time()
    deleted = 0
    for file_path in directory.iterdir():
        if not file_path.is_file():
            continue
        age = now - file_path.stat().st_mtime
        if age > max_age_seconds:
            try:
                file_path.unlink()
                deleted += 1
                log.debug("Deleted old file: %s (age=%.0fs)", file_path.name, age)
            except OSError:
                log.warning("Failed to delete: %s", file_path, exc_info=True)
    if deleted:
        log.info("Cleanup: removed %d file(s) from %s", deleted, directory)
    return deleted


async def _periodic_cleanup() -> None:
    """Background loop that runs cleanup at regular intervals."""
    while True:
        await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)
        try:
            _ = cleanup_old_files(UPLOAD_DIR)
        except Exception:
            log.exception("Error during periodic cleanup")


async def start_cleanup_scheduler() -> None:
    """Start the periodic cleanup background task."""
    global _task  # noqa: PLW0603
    _task = asyncio.create_task(_periodic_cleanup())
    log.info(
        "File cleanup scheduler started (interval=%ds, max_age=%ds)",
        CLEANUP_INTERVAL_SECONDS,
        MAX_FILE_AGE_SECONDS,
    )


async def stop_cleanup_scheduler() -> None:
    """Cancel the cleanup background task."""
    global _task  # noqa: PLW0603
    if _task is not None:
        _ = _task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await _task
        _task = None
        log.info("File cleanup scheduler stopped")
