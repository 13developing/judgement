"""FastAPI application entry point."""

from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.config import UPLOAD_DIR
from backend.database import init_db
from backend.routers import judge, provider, question_bank, upload

_FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup / shutdown lifecycle."""
    init_db()
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(
    title="大学智能判题系统",
    description="基于多模态大模型的智能判题 Web 服务",
    version="0.2.0",
    lifespan=lifespan,
)

# ── Routers ──────────────────────────────────────────────────────────────
app.include_router(judge.router)
app.include_router(question_bank.router)
app.include_router(upload.router)
app.include_router(provider.router)

# ── Static files ─────────────────────────────────────────────────────────
if (_FRONTEND_DIR / "static").exists():
    app.mount(
        "/static",
        StaticFiles(directory=str(_FRONTEND_DIR / "static")),
        name="static",
    )

# ── Page routes ──────────────────────────────────────────────────────────


@app.get("/")
async def index_page() -> FileResponse:
    return FileResponse(str(_FRONTEND_DIR / "index.html"))


@app.get("/bank")
async def bank_page() -> FileResponse:
    return FileResponse(str(_FRONTEND_DIR / "bank.html"))


@app.get("/settings")
async def settings_page() -> FileResponse:
    return FileResponse(str(_FRONTEND_DIR / "settings.html"))
