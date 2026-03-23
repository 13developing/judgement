# AGENTS.md — Intelligent Exam Judging System

> Auto-generated coding-agent reference. Keep up to date as the project evolves.

## Project Overview

Web application for automated university exam grading (大学智能判题系统). Supports photo-based answer capture, OCR via multimodal LLM, and intelligent scoring for fill-in-the-blank, short-answer, and calculation questions.

**Tech stack**: Python · tkinter (desktop GUI) · requests · Pillow · OpenAI-compatible API  
**Stage**: Early / greenfield — minimal structure, single-file backend, no CI/CD.

## Repository Layout

```
backend/          # Python application code (main entry: main.py)
frontend/         # Reserved for future frontend (currently empty)
test/             # Test assets (PDF exam papers for manual testing)
  pdf/            # Sample exam papers and answer keys
docs/             # Project documentation (Chinese)
  request/        # Stakeholder requirements
  reply/          # Specs and deliverables (需求规格说明书)
```

## Build / Run / Test Commands

### Install Dependencies

```bash
pip install requests pillow
```

No `requirements.txt` or `pyproject.toml` exists yet. When adding dependencies, create `requirements.txt`:

```bash
pip freeze > requirements.txt
```

### Run the Application

```bash
python backend/main.py
```

The app opens a tkinter GUI window. Requires a display environment (no headless mode).

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
| Constant       | `UPPER_SNAKE_CASE`| `COLOR_MAIN`, `OPENAI_MODEL` |
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
- Network errors: catch `requests.exceptions.RequestException`
- Show user-friendly messages via `messagebox` for GUI errors
- Log technical details for debugging; show summaries to users

```python
try:
    response = requests.post(url, json=payload, timeout=30)
    response.raise_for_status()
except requests.exceptions.RequestException as e:
    error_detail = str(e)
    if hasattr(e, "response") and e.response is not None:
        error_detail += f"\n{e.response.text}"
    messagebox.showerror("请求失败", f"判题请求失败：{error_detail}")
```

### Configuration & Secrets

- **NEVER hardcode API keys in source code** — use environment variables
- Access config via `os.getenv("KEY", "default_value")`
- Document required env vars in this file and README

```
Required env vars:
  OPENAI_API_KEY     — API key for the LLM provider
  OPENAI_BASE_URL    — API base URL (default: https://api.ethan0x0000.work/v1)
  OPENAI_MODEL       — Model identifier (default: gpt-4o-mini)
```

### GUI / tkinter Patterns

- Use class-based structure: one class per window/dialog
- Keep UI construction in `_build_ui()` methods
- Store widget references on `self` only when needed for later access
- Use named color constants at module level (`COLOR_MAIN`, `COLOR_BG`, etc.)
- Disable buttons during async operations; re-enable in `finally` blocks
- Use `self.root.update()` sparingly — prefer `after()` for non-blocking updates

### API Integration

- All LLM calls go through the OpenAI-compatible chat completions endpoint
- Encode images as base64 for multimodal input
- Set `temperature=0.1` for deterministic grading results
- Set reasonable `timeout` on all HTTP calls (30s default)
- Structure prompts as system/user messages with clear grading rubrics

### File Organization (Target Structure)

As the project grows, refactor toward:

```
backend/
  __init__.py
  main.py              # Entry point, GUI initialization
  ui/                  # UI components (windows, dialogs, widgets)
  services/            # Business logic (grading, API calls)
  utils/               # Helpers (image processing, LaTeX formatting)
  config.py            # Centralized configuration
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

- Minimize external dependencies — this is a desktop app
- Current deps: `requests`, `pillow` (PIL)
- Prefer stdlib when possible (e.g., `tkinter` over heavier GUI frameworks)
- When adding a dep, update `requirements.txt` and document the reason

### Security Notes

- API keys must come from environment variables, never committed to git
- The current codebase has a hardcoded API key in `backend/main.py` — this must be removed
- Add `.env` to `.gitignore` if using dotenv for local config
