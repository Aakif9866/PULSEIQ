"""Request logging, request IDs, and the root trace span.

Binds a request_id to structlog's contextvars for the lifetime of each
request, so every log line emitted while handling it — including from deep
inside a service, a tool call, or an LLM call — carries the same id without
threading it through every function call. logging.py's `merge_contextvars`
processor is what actually pulls these into each log line.

Phase 8 step 5 (docs/PROGRESS.md) fixed three real gaps here, each
verified live before the fix, not assumed:

1. An inbound `X-Request-ID` (sent by the frontend) was ignored — so a
   browser-side error and the server-side log line for it had no shared
   id. Now honored when it's well-formed.
2. An unhandled exception escaped this middleware to Starlette's
   outermost error handler, whose 500 response carried NO X-Request-ID —
   the one response a user most needs a reference id for.
3. That outer handler's log line (the one holding the actual error)
   ran *after* this middleware had already cleared its contextvars, so it
   carried no request_id either. The 500 is now produced here, with the
   error logged while the request's context is still bound.
"""
import re
import time
import uuid
from collections.abc import Awaitable, Callable

import structlog
from opentelemetry.trace import Status, StatusCode
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.logging import get_logger
from app.core.tracing import current_trace_id, get_tracer

logger = get_logger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"
# A client-supplied id goes straight into log lines and a response header,
# so it's accepted only if it's short and plainly boring — no newlines
# (log injection), no header-splitting characters, no multi-KB payloads.
# Anything else is replaced with a fresh server-generated id, not rejected:
# a bad correlation id should never fail the actual request.
_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


def _resolve_request_id(inbound: str | None) -> str:
    if inbound and _VALID_REQUEST_ID.fullmatch(inbound):
        return inbound
    return str(uuid.uuid4())


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = _resolve_request_id(request.headers.get(REQUEST_ID_HEADER))
        start = time.perf_counter()

        with get_tracer().start_as_current_span(f"{request.method} {request.url.path}") as span:
            span.set_attribute("http.request.method", request.method)
            span.set_attribute("url.path", request.url.path)
            span.set_attribute("pulseiq.request_id", request_id)

            log_context: dict[str, str] = {"request_id": request_id}
            trace_id = current_trace_id()
            if trace_id is not None:
                log_context["trace_id"] = trace_id
            structlog.contextvars.bind_contextvars(**log_context)

            try:
                response = await call_next(request)
            except Exception as exc:
                duration_ms = round((time.perf_counter() - start) * 1000, 2)
                span.record_exception(exc)
                span.set_status(Status(StatusCode.ERROR, type(exc).__name__))
                span.set_attribute("http.response.status_code", 500)
                logger.exception(
                    "request_failed",
                    method=request.method,
                    path=request.url.path,
                    error_type=type(exc).__name__,
                    duration_ms=duration_ms,
                )
                # Same generic body as main.py's last-resort handler — never
                # leak internals — plus the id, so a user can quote it.
                return JSONResponse(
                    status_code=500,
                    content={
                        "detail": "Something went wrong on our end. Please try again.",
                        "request_id": request_id,
                    },
                    headers={REQUEST_ID_HEADER: request_id},
                )
            else:
                route = request.scope.get("route")
                route_template = getattr(route, "path", None)
                if route_template:
                    # Name by template ("/datasets/{dataset_id}/analyze"),
                    # not the concrete path — one span name per endpoint,
                    # not one per dataset id.
                    span.update_name(f"{request.method} {route_template}")
                    span.set_attribute("http.route", route_template)
                span.set_attribute("http.response.status_code", response.status_code)
                if response.status_code >= 500:
                    span.set_status(Status(StatusCode.ERROR))
                logger.info(
                    "request_completed",
                    method=request.method,
                    path=request.url.path,
                    status_code=response.status_code,
                    duration_ms=round((time.perf_counter() - start) * 1000, 2),
                )
                response.headers[REQUEST_ID_HEADER] = request_id
                return response
            finally:
                # Cleared after logging in either branch above, not before —
                # otherwise the log lines this middleware itself emits would
                # never carry the request_id they exist to attach.
                structlog.contextvars.clear_contextvars()
