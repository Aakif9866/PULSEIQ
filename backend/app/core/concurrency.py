"""Thread-pool submission that keeps the caller's context.

`ThreadPoolExecutor.submit()` runs work in a thread that does NOT inherit
the submitting thread's contextvars — verified directly (docs/PROGRESS.md,
Phase 8 step 5): a request_id bound by RequestLoggingMiddleware read back
as `{}` inside a plain `.submit()`. Both structlog's request-scoped fields
and OpenTelemetry's current span live in contextvars, so a plain submit
silently orphaned any log line or span created inside the worker from the
request that caused it. Running the work inside a copy of the caller's
context fixes both at once.
"""
import contextvars
from collections.abc import Callable
from concurrent.futures import Executor, Future
from typing import ParamSpec, TypeVar

P = ParamSpec("P")
R = TypeVar("R")


def submit_in_context(
    executor: Executor, fn: Callable[P, R], /, *args: P.args, **kwargs: P.kwargs
) -> Future[R]:
    ctx = contextvars.copy_context()

    def _run_in_callers_context() -> R:
        return ctx.run(fn, *args, **kwargs)

    return executor.submit(_run_in_callers_context)
