"""Thin wrapper around the Groq SDK, isolated so callers never touch the
SDK directly — swapping providers later means changing this file only."""
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from functools import lru_cache
from typing import Any

from groq import Groq

from app.core.config import settings


@lru_cache
def get_groq_client() -> Groq:
    return Groq(api_key=settings.GROQ_API_KEY, timeout=settings.AI_REQUEST_TIMEOUT_SECONDS)


# Token counting for the paths that call the SDK directly (/ask, /ask-sql,
# monitor explanations). /analyze counts through UsageTrackingProvider
# instead, so it never opens this scope and nothing is counted twice.
_usage: ContextVar[list[int] | None] = ContextVar("groq_raw_usage", default=None)


@contextmanager
def count_tokens() -> Iterator[list[int]]:
    """Yields [prompt, completion] totals for every raw call in the block."""
    totals = [0, 0]
    token = _usage.set(totals)
    try:
        yield totals
    finally:
        _usage.reset(token)


def note_usage(response: Any) -> None:
    totals = _usage.get()
    usage = getattr(response, "usage", None)
    if totals is None or usage is None:
        return
    totals[0] += getattr(usage, "prompt_tokens", 0) or 0
    totals[1] += getattr(usage, "completion_tokens", 0) or 0
