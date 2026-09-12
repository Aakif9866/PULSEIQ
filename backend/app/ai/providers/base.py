"""Provider abstraction for the AI Analyst engine — the engine (and every
tool-calling loop it runs) talks only to this interface, never to a
specific SDK. See docs/AI_ANALYTICS.md: this makes it possible to add
another provider later without touching app/ai/analyst_engine.py at all.

Only GroqProvider actually exists and is exercised in this project today
(the only provider with real, working credentials here) — this base
class and the shape below are what a second provider would implement,
not a claim that OpenAI/Gemini support already works.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class ProviderMessage:
    """One assistant turn: plain content, or a request to call tools (a
    model can return both text and tool calls in some providers, but in
    practice here it's one or the other)."""

    content: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)


class AIProvider(ABC):
    @abstractmethod
    def chat(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        json_mode: bool = False,
        temperature: float = 0.1,
    ) -> ProviderMessage:
        """Send a chat request. `messages` follows the OpenAI-compatible
        role/content(/tool_calls/tool_call_id) shape every provider this
        project could plausibly add already speaks natively. Raises
        AiResponseError (app.core.exceptions) on any failure — callers
        never need to catch a provider-specific exception type."""
