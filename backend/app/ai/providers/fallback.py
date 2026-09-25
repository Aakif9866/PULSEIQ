"""A configurable multi-provider fallback chain — docs/PHASES.md Phase 8
step 4 ("429 handling: ... plus a configurable fallback provider behind
the existing provider abstraction").

Built as reusable infrastructure, not wired into production by default:
this codebase has exactly one real AIProvider (GroqProvider) — see
app/ai/providers/base.py's own docstring, which already says plainly
that a second provider isn't a claim this project makes yet. A
"fallback" with nowhere real to fall back to would just be
FallbackProvider([GroqProvider()]), which is a no-op. Adding a second
real provider (OpenAI, Gemini, ...) needs its own account/API key — a
new paid service, which this project's standing rule is to ask about
before adding, not assume. This class is ready to adopt the moment that
happens; nothing about it depends on which second provider it would be.
"""
from typing import Any

from app.ai.providers.base import AIProvider, ProviderMessage
from app.core.exceptions import AiResponseError
from app.core.logging import get_logger

logger = get_logger(__name__)


class FallbackProvider(AIProvider):
    """Tries each provider in order, moving to the next only when one
    raises AiResponseError (every AIProvider's documented failure mode,
    per base.py) — never on a successful-but-maybe-imperfect answer,
    which every provider already decides for itself before returning."""

    def __init__(self, providers: list[AIProvider]) -> None:
        if not providers:
            raise ValueError("FallbackProvider needs at least one provider")
        self._providers = providers

    def chat(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        json_mode: bool = False,
        temperature: float = 0.1,
    ) -> ProviderMessage:
        last_error: AiResponseError | None = None
        for i, provider in enumerate(self._providers):
            try:
                return provider.chat(
                    messages=messages, tools=tools, json_mode=json_mode, temperature=temperature
                )
            except AiResponseError as exc:
                last_error = exc
                if i < len(self._providers) - 1:
                    logger.warning(
                        "fallback_provider_switching",
                        failed_provider=type(provider).__name__,
                        next_provider=type(self._providers[i + 1]).__name__,
                        error=str(exc),
                    )
                continue
        # Unreachable with a non-empty provider list (enforced in
        # __init__) — every branch of the loop above either returns or
        # sets last_error before falling through here.
        raise last_error or AiResponseError("No provider was available.")
