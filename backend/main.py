"""FastAPI application entry point."""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.config import UPLOAD_DIR
from backend.database import init_db
from backend.logging_config import setup_logging
from backend.middleware.access_log import AccessLogMiddleware
from backend.middleware.error_handler import ErrorHandlerMiddleware
from backend.middleware.request_id import RequestIDMiddleware
from backend.routers import (
    export,  # pyright: ignore[reportAttributeAccessIssue,reportUnknownVariableType]
    health,
    judge,
    metrics,
    provider,
    question_bank,
    upload,
    grade_cards,
)
from backend.services.cleanup import start_cleanup_scheduler, stop_cleanup_scheduler
from backend.services.http_client import shutdown_http_client, startup_http_client

_FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup / shutdown lifecycle."""
    setup_logging()
    init_db()
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    await startup_http_client()
    await start_cleanup_scheduler()
    yield
    log.info("Shutting down gracefully...")
    await stop_cleanup_scheduler()
    await shutdown_http_client()
    log.info("Shutdown complete.")


app = FastAPI(
    title="大学智能判题系统",
    description="基于多模态大模型的智能判题 Web 服务",
    version="0.2.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {"name": "智能判题", "description": "图片上传与 AI 判题"},
        {"name": "题库管理", "description": "题目 CRUD 操作"},
        {"name": "文档导入", "description": "试卷/答案文档上传与解析"},
        {"name": "系统设置", "description": "LLM Provider 配置管理"},
        {"name": "健康检查", "description": "存活与就绪探针"},
        {"name": "监控指标", "description": "LLM 用量与系统监控"},
    ],
    lifespan=lifespan,
)

# ── Middleware ────────────────────────────────────────────────────────────
app.add_middleware(RequestIDMiddleware)
app.add_middleware(AccessLogMiddleware)
app.add_middleware(ErrorHandlerMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)

# ── Routers ──────────────────────────────────────────────────────────────
app.include_router(health.router)
app.include_router(judge.router)
app.include_router(export.router)  # pyright: ignore[reportUnknownMemberType,reportUnknownArgumentType]
app.include_router(question_bank.router)
app.include_router(upload.router)
app.include_router(provider.router)
app.include_router(metrics.router)
app.include_router(grade_cards.router)

# ── Static files ─────────────────────────────────────────────────────────
if (_FRONTEND_DIR / "static").exists():
    app.mount(
        "/static",
        StaticFiles(directory=str(_FRONTEND_DIR / "static")),
        name="static",
    )

app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR), check_dir=False), name="uploads")

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
