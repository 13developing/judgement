"""Centralized configuration via environment variables."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 自动加载项目根目录下的 .env 文件（不覆盖已有环境变量）
load_dotenv(PROJECT_ROOT / ".env")
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
