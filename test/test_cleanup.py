"""Tests for file cleanup."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from backend.services.cleanup import cleanup_old_files


@pytest.fixture
def temp_upload_dir(tmp_path: Path) -> Path:
    """Create a temporary directory with test files."""
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    return upload_dir


def test_cleanup_deletes_old_files(temp_upload_dir: Path) -> None:
    """Files older than max_age are deleted."""
    old_file = temp_upload_dir / "old.png"
    _ = old_file.write_bytes(b"old content")
    # Set mtime to 2 days ago
    old_time = time.time() - (2 * 24 * 60 * 60)
    import os

    os.utime(old_file, (old_time, old_time))

    new_file = temp_upload_dir / "new.png"
    _ = new_file.write_bytes(b"new content")

    deleted = cleanup_old_files(temp_upload_dir, max_age_seconds=24 * 60 * 60)

    assert deleted == 1
    assert not old_file.exists()
    assert new_file.exists()


def test_cleanup_no_files(temp_upload_dir: Path) -> None:
    """Empty directory returns 0 deleted."""
    deleted = cleanup_old_files(temp_upload_dir)
    assert deleted == 0


def test_cleanup_nonexistent_dir(tmp_path: Path) -> None:
    """Non-existent directory returns 0 without error."""
    deleted = cleanup_old_files(tmp_path / "nonexistent")
    assert deleted == 0


def test_cleanup_skips_recent_files(temp_upload_dir: Path) -> None:
    """Recent files are not deleted."""
    recent = temp_upload_dir / "recent.jpg"
    _ = recent.write_bytes(b"recent")

    deleted = cleanup_old_files(temp_upload_dir, max_age_seconds=24 * 60 * 60)

    assert deleted == 0
    assert recent.exists()
