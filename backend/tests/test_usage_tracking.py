from app.ai.providers.base import AIProvider, ProviderMessage
from app.ai.providers.usage_tracking import UsageTrackingProvider
from app.core.config import settings


class _ScriptedProvider(AIProvider):
    def __init__(self, responses: list[ProviderMessage]) -> None:
        self._responses = list(responses)

    def chat(self, *, messages, tools=None, json_mode=False, temperature=0.1) -> ProviderMessage:
        return self._responses.pop(0)


def _message(total_tokens, prompt_tokens, completion_tokens, total_time_ms=None):
    usage = {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
    }
    if total_time_ms is not None:
        usage["total_time_ms"] = total_time_ms
    return ProviderMessage(content="ok", usage=usage)


def test_accumulates_tokens_across_multiple_calls():
    wrapped = _ScriptedProvider([_message(100, 80, 20), _message(50, 40, 10)])
    tracker = UsageTrackingProvider(wrapped)

    tracker.chat(messages=[])
    tracker.chat(messages=[])

    assert tracker.totals.call_count == 2
    assert tracker.totals.total_tokens == 150
    assert tracker.totals.prompt_tokens == 120
    assert tracker.totals.completion_tokens == 30


def test_returns_the_wrapped_providers_message_unchanged():
    message = _message(10, 8, 2)
    tracker = UsageTrackingProvider(_ScriptedProvider([message]))
    result = tracker.chat(messages=[])
    assert result is message


def test_handles_a_call_with_no_usage_reported_without_crashing():
    tracker = UsageTrackingProvider(_ScriptedProvider([ProviderMessage(content="ok", usage=None)]))
    tracker.chat(messages=[])
    assert tracker.totals.call_count == 1
    assert tracker.totals.total_tokens == 0


def test_estimated_cost_is_none_when_pricing_is_not_configured(monkeypatch):
    monkeypatch.setattr(settings, "GROQ_INPUT_COST_PER_1M_TOKENS", None)
    monkeypatch.setattr(settings, "GROQ_OUTPUT_COST_PER_1M_TOKENS", None)
    tracker = UsageTrackingProvider(_ScriptedProvider([_message(100, 80, 20)]))
    tracker.chat(messages=[])
    assert tracker.totals.estimated_cost_usd is None


def test_estimated_cost_is_computed_when_pricing_is_configured(monkeypatch):
    monkeypatch.setattr(settings, "GROQ_INPUT_COST_PER_1M_TOKENS", 10.0)
    monkeypatch.setattr(settings, "GROQ_OUTPUT_COST_PER_1M_TOKENS", 20.0)
    tracker = UsageTrackingProvider(_ScriptedProvider([_message(100, 1_000_000, 500_000)]))
    tracker.chat(messages=[])
    # 1,000,000 prompt tokens @ $10/1M + 500,000 completion tokens @ $20/1M
    assert tracker.totals.estimated_cost_usd == 10.0 + 10.0


def test_groq_reported_latency_is_tracked_separately_from_wall_clock():
    tracker = UsageTrackingProvider(_ScriptedProvider([_message(10, 8, 2, total_time_ms=250)]))
    tracker.chat(messages=[])
    assert tracker.totals.groq_reported_ms == 250
    # wall_clock_ms includes this test's own call overhead, so it's only
    # ever asserted to be non-negative, not equal to a fixed value.
    assert tracker.totals.wall_clock_ms >= 0
