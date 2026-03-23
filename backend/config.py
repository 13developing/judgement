"""Centralized configuration via environment variables."""

from __future__ import annotations

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
DATABASE_PATH = DATA_DIR / "db.sqlite"

# ---------------------------------------------------------------------------
# LLM Provider
# ---------------------------------------------------------------------------
# Supported values: "ark" (豆包，primary), "openai" (OpenAI-compatible, fallback)
# The OPENAI_* env vars are kept as fallback aliases for backward compatibility.
LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "ark")

LLM_API_KEY: str = os.getenv(
    "LLM_API_KEY",
    os.getenv("OPENAI_API_KEY", ""),
)
LLM_BASE_URL: str = os.getenv(
    "LLM_BASE_URL",
    os.getenv("OPENAI_BASE_URL", ""),
)
LLM_MODEL: str = os.getenv(
    "LLM_MODEL",
    os.getenv("OPENAI_MODEL", ""),
)

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{DATABASE_PATH}")
