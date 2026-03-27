from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from typing_extensions import override

log = logging.getLogger(__name__)


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    @override
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        try:
            return await call_next(request)
        except Exception:
            log.exception("Unhandled exception on %s %s", request.method, request.url.path)
            return JSONResponse(
                status_code=500,
                content={"detail": "服务器内部错误，请稍后重试。"},
            )
