"""Wraps any AIProvider to accumulate token usage/latency across every
`.chat()` call made through it — docs/PHASES.md Phase 8 step 4 ("Log
tokens, latency and cost per request"). Reuses the exact pattern
`evals/instrumentation.py` proved out for the eval harness, formalized
here as production code: `app.ai.analyst_engine.run_analysis` makes
several `.chat()` calls per single user question (the tool-calling
loop), and neither it nor `AnalyzeResponse` currently expose a combined
total — wrapping the *provider* means the totals are available to the
caller with zero change to run_analysis or the AnalyzeResponse schema.

Cost is intentionally NOT hardcoded here. Groq's per-model pricing
wasn't available to verify at the time this was written (its pricing
page renders client-side; nothing came back fetchable), and this
project's own standing rule is to never present an invented number as
real — so cost is computed only when GROQ_INPUT_COST_PER_1M_TOKENS /
GROQ_OUTPUT_COST_PER_1M_TOKENS are explicitly configured (see
.env.example), from Groq's own current pricing, by whoever operates
this. Left unset, cost is honestly reported as unavailable — tokens and
latency are still always real numbers either way.
"""
import time
from dataclasses import dataclass, field
from typing import Any

from app.ai.providers.base import AIProvider, ProviderMessage
from app.core.config import settings


@dataclass
class UsageTotals:
    call_count: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    wall_clock_ms: float = 0.0
    groq_reported_ms: float = 0.0
    calls: list[dict[str, Any]] = field(default_factory=list)

    @property
    def estimated_cost_usd(self) -> float | None:
        input_rate = settings.GROQ_INPUT_COST_PER_1M_TOKENS
        output_rate = settings.GROQ_OUTPUT_COST_PER_1M_TOKENS
        if input_rate is None or output_rate is None:
            return None
        return round(
            (self.prompt_tokens / 1_000_000) * input_rate
            + (self.completion_tokens / 1_000_000) * output_rate,
            6,
        )


class UsageTrackingProvider(AIProvider):
    """Delegates every call to `wrapped`, recording each one's usage/
    latency onto `.totals`. One instance per request/analysis, not
    shared — `.totals` describes exactly one logical operation (e.g. one
    /analyze call), the same scope `evals/instrumentation.py`'s
    `track_usage()` context manager uses."""

    def __init__(self, wrapped: AIProvider) -> None:
        self._wrapped = wrapped
        self.totals = UsageTotals()

    def chat(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        json_mode: bool = False,
        temperature: float = 0.1,
    ) -> ProviderMessage:
        start = time.perf_counter()
        message = self._wrapped.chat(
            messages=messages, tools=tools, json_mode=json_mode, temperature=temperature
        )
        latency_ms = (time.perf_counter() - start) * 1000

        self.totals.call_count += 1
        self.totals.wall_clock_ms += latency_ms
        record: dict[str, Any] = {"latency_ms": round(latency_ms)}
        if message.usage:
            for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
                value = message.usage.get(key)
                if value is not None:
                    setattr(self.totals, key, getattr(self.totals, key) + value)
                    record[key] = value
            total_time_ms = message.usage.get("total_time_ms")
            if total_time_ms is not None:
                self.totals.groq_reported_ms += total_time_ms
                record["total_time_ms"] = total_time_ms
        self.totals.calls.append(record)
        return message
