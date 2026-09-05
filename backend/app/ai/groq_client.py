"""Thin wrapper around the Groq SDK, isolated so callers never touch the
SDK directly — swapping providers later means changing this file only."""
from functools import lru_cache

from groq import Groq

from app.core.config import settings


@lru_cache
def get_groq_client() -> Groq:
    return Groq(api_key=settings.GROQ_API_KEY, timeout=settings.AI_REQUEST_TIMEOUT_SECONDS)
