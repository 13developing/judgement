# AGENTS.md — Intelligent Exam Judging System

> Auto-generated coding-agent reference. Keep up to date as the project evolves.

## Project Overview

Web application for automated university exam grading (大学智能判题系统). Supports photo-based answer capture, OCR via multimodal LLM, and intelligent scoring for fill-in-the-blank, short-answer, and calculation questions.

**Tech stack**: Python · FastAPI · httpx · Pillow · Multi-provider LLM (Doubao primary, OpenAI fallback)  
**Stage**: Early / greenfield — modular backend, provider abstraction in place, no CI/CD.

## Repository Layout

```
backend/          # Python application code (main entry: main.py)
  services/       # Business logic (grading, doc parsing, matching)
    providers/    # LLM provider abstraction (ark / openai_compat)
  routers/        # FastAPI route handlers
  utils/          # Helpers (image processing, LaTeX formatting)
  config.py       # Centralized configuration
frontend/         # Web frontend (HTML + CSS + JS)
test/             # Test assets (PDF exam papers for manual testing)
  pdf/            # Sample exam papers and answer keys
docs/             # Project documentation (Chinese)
  request/        # Stakeholder requirements
  reply/          # Specs and deliverables (需求规格说明书)
```

## Build / Run / Test Commands

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Run the Application

```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

### Run a Single Test

No test framework is configured yet. When adding tests:

```bash
# Preferred: pytest
pip install pytest
pytest test/test_something.py               # single file
pytest test/test_something.py::test_name    # single test function
pytest test/ -k "keyword"                   # by keyword match
pytest -x                                   # stop on first failure
```

### Linting / Formatting

No linter or formatter is configured. The project should adopt:

```bash
# Recommended toolchain
pip install ruff
ruff check .                    # lint
ruff check --fix .              # auto-fix
ruff format .                   # format (Black-compatible)
```

### Type Checking

```bash
pip install pyright              # or mypy
pyright backend/
```

## Code Style Guidelines

### Language & Encoding

- All code identifiers (variables, functions, classes) in **English**
- Comments and UI strings may be in **Chinese** (project audience is Chinese educators)
- Files must be **UTF-8** encoded

### Imports

- Standard library imports first, then third-party, then local — separated by blank lines
- Use explicit imports; avoid wildcard `from x import *`

```python
import os
import base64

import requests
from PIL import Image, ImageTk

from backend.utils import format_latex
```

### Naming Conventions

| Entity         | Convention        | Example                   |
|----------------|-------------------|---------------------------|
| Module         | `snake_case`      | `exam_judge.py`           |
| Class          | `PascalCase`      | `ExamJudgeApp`            |
| Function/Method| `snake_case`      | `judge_exam()`            |
| Private method | `_snake_case`     | `_build_ui()`             |
| Constant       | `UPPER_SNAKE_CASE`| `COLOR_MAIN`, `LLM_MODEL` |
| Variable       | `snake_case`      | `img_base64`              |

### Formatting

- **Indentation**: 4 spaces (no tabs)
- **Max line length**: 100 characters (soft limit)
- **Trailing commas**: Use in multi-line collections and function args
- **Quotes**: Double quotes `"` for strings (consistent with existing code)
- **Blank lines**: 2 between top-level definitions, 1 within class methods

### Type Hints

- Add type hints to all new function signatures (parameters + return type)
- Use `from __future__ import annotations` for forward references

```python
from __future__ import annotations

def judge_exam(image_path: str, standard_answer: str | None = None) -> dict[str, Any]:
    ...
```

### Error Handling

- Never use bare `except:` — always specify exception types
- Network errors: catch `httpx.HTTPStatusError` or `httpx.RequestError`
- Return structured JSON error responses from API endpoints
- Log technical details for debugging; show summaries to users

```python
try:
    resp = await client.post(url, json=payload, timeout=120)
    resp.raise_for_status()
except httpx.HTTPStatusError as e:
    raise HTTPException(status_code=502, detail=f"LLM 请求失败: {e.response.text}")
except httpx.RequestError as e:
    raise HTTPException(status_code=502, detail=f"LLM 连接失败: {e}")
```

### Configuration & Secrets

- **NEVER hardcode API keys in source code** — use environment variables
- Access config via `os.getenv("KEY", "default_value")`
- Document required env vars in this file and README

```
Required env vars:
  LLM_API_KEY      — API key for the active LLM provider (required)

Optional env vars (override provider defaults):
  LLM_PROVIDER     — "ark" (default, 豆包) or "openai" (fallback)
  LLM_BASE_URL     — API base URL (default varies by provider)
  LLM_MODEL        — Model identifier (default varies by provider)

Backward-compatible aliases (lower priority):
  OPENAI_API_KEY   — Fallback for LLM_API_KEY
  OPENAI_BASE_URL  — Fallback for LLM_BASE_URL
  OPENAI_MODEL     — Fallback for LLM_MODEL
```

### Web Frontend Patterns

- Frontend lives in `frontend/` — plain HTML + CSS + JS (no build step)
- Use `fetch()` for API calls to the FastAPI backend
- Keep JS modular: separate files per page (`app.js`, `bank.js`)
- CSS in `frontend/static/css/`; JS in `frontend/static/js/`

### API Integration

- All LLM calls go through `backend/services/llm_client.py` (thin façade)
- Provider logic lives in `backend/services/providers/` (strategy pattern)
- Primary provider: **Volcengine Ark (豆包)** — `ArkProvider`
- Fallback provider: **OpenAI-compatible** — `OpenAICompatProvider`
- Both providers use the OpenAI-compatible Chat Completions format (`/chat/completions`)
- Encode images as base64 for multimodal input
- Set `temperature=0.1` for deterministic grading results
- Set reasonable `timeout` on all HTTP calls (120s for LLM calls)
- Structure prompts as system/user messages with clear grading rubrics
- To add a new provider: subclass `LLMProvider` in `providers/base.py`, register in `providers/__init__.py`

### File Organization (Target Structure)

As the project grows, refactor toward:

```
backend/
  __init__.py
  main.py              # Entry point, FastAPI app
  config.py            # Centralized configuration
  routers/             # FastAPI route handlers
  services/            # Business logic (grading, API calls)
    providers/         # LLM provider abstraction
      base.py          # LLMProvider ABC + shared implementation
      ark.py           # Volcengine Ark (豆包) — primary
      openai_compat.py # OpenAI-compatible — fallback
    llm_client.py      # Public API façade
  utils/               # Helpers (image processing, LaTeX formatting)
test/
  test_services/       # Unit tests for business logic
  test_utils/          # Unit tests for utilities
  conftest.py          # Shared pytest fixtures
  pdf/                 # Test fixture files
```

### Git Conventions

- **Commit prefix**: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`, `init:`
- **Branch naming**: `feature/xxx`, `fix/xxx`, `docs/xxx`
- Commit messages in English, concise imperative mood
- Keep `.gitignore` updated — exclude `__pycache__/`, `*.pyc`, `.env`, `venv/`, `*.egg-info/`

### Dependencies Policy

- Minimize external dependencies — this is a web application
- Current deps: `fastapi`, `uvicorn`, `httpx`, `pillow`, `sqlmodel`, `python-docx`, `pdfplumber`, `jinja2`
- Prefer stdlib when possible
- When adding a dep, update `requirements.txt` and document the reason

### Security Notes

- API keys must come from environment variables, never committed to git
- Add `.env` to `.gitignore` if using dotenv for local config
