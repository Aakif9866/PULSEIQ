"""Request logging.

Binds a request_id to structlog's contextvars for the lifetime of each
request, so every log line emitted while handling it — including from deep
inside a service or repository — carries the same id without threading it
through every function call. logging.py's `merge_contextvars` processor is
what actually pulls these into each log line.
"""
import time
import uuid
from collections.abc import Awaitable, Callable

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import get_logger

logger = get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = str(uuid.uuid4())
        structlog.contextvars.bind_contextvars(request_id=request_id)
        start = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            logger.error(
                "request_failed",
                method=request.method,
                path=request.url.path,
                duration_ms=round((time.perf_counter() - start) * 1000, 2),
            )
            raise
        else:
            logger.info(
                "request_completed",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=round((time.perf_counter() - start) * 1000, 2),
            )
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            # Cleared after logging in either branch above, not before —
            # otherwise the log lines this middleware itself emits would
            # never carry the request_id they exist to attach.
            structlog.contextvars.clear_contextvars()
