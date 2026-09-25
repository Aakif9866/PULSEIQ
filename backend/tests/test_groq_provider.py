"""Tests for GroqProvider's reliability layer — retries, the explicit-None
kwargs bug fix, and the fake-"json"-tool-call salvage path — all against a
fake Groq SDK client (no real network call), so these run every time
without needing GROQ_API_KEY or live credits.
"""
from types import SimpleNamespace
from typing import Any

import pytest

from app.ai.providers.groq_provider import GroqProvider
from app.core.exceptions import AiResponseError


@pytest.fixture(autouse=True)
def _no_real_backoff_sleep(monkeypatch):
    """Retries now genuinely back off (Phase 8 step 4). Tests that care
    about the delay re-patch this with a recorder; every other test would
    otherwise really sleep between retries for no reason."""
    monkeypatch.setattr("app.ai.providers.groq_provider.time.sleep", lambda _s: None)


class _FakeToolCallFunction:
    def __init__(self, name: str, arguments: str) -> None:
        self.name = name
        self.arguments = arguments


class _FakeToolCall:
    def __init__(self, id_: str, name: str, arguments: str) -> None:
        self.id = id_
        self.function = _FakeToolCallFunction(name, arguments)


def _fake_response(
    content: str | None,
    tool_calls: list[_FakeToolCall] | None = None,
    usage: SimpleNamespace | None = None,
):
    message = SimpleNamespace(content=content, tool_calls=tool_calls or None)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=usage)


class _BadRequestLike(Exception):
    """Stands in for groq.BadRequestError — GroqProvider only relies on a
    `.body` attribute being present, and (for retry-delay parsing) on
    str(exc) containing the message text, never the real SDK exception
    type. str(exc) here matches the real SDK's actual format, verified
    against this project's own captured logs: "Error code: 429 -
    {'error': {'message': 'Rate limit reached ... Please try again in
    5.0625s...', ...}}" — the body dict's repr, not just a bare code."""

    def __init__(self, body: dict[str, Any]) -> None:
        super().__init__(f"Error code: 400 - {body}")
        self.body = body


class _FakeChatCompletions:
    def __init__(self, side_effects: list) -> None:
        self._side_effects = list(side_effects)
        self.received_kwargs: list[dict[str, Any]] = []

    def create(self, **kwargs: Any):
        self.received_kwargs.append(kwargs)
        effect = self._side_effects.pop(0)
        if isinstance(effect, Exception):
            raise effect
        return effect


class _FakeGroqClient:
    def __init__(self, side_effects: list) -> None:
        self.chat = SimpleNamespace(completions=_FakeChatCompletions(side_effects))


def _install_fake_client(monkeypatch, side_effects: list) -> _FakeGroqClient:
    fake_client = _FakeGroqClient(side_effects)
    monkeypatch.setattr("app.ai.groq_client.get_groq_client", lambda: fake_client)
    return fake_client


def test_chat_never_passes_explicit_none_for_tool_choice_or_response_format(monkeypatch):
    fake_client = _install_fake_client(
        monkeypatch, [_fake_response("hello")]
    )
    GroqProvider().chat(messages=[{"role": "user", "content": "hi"}])
    kwargs = fake_client.chat.completions.received_kwargs[0]
    assert "tool_choice" not in kwargs
    assert "response_format" not in kwargs


def test_chat_includes_tool_choice_only_when_tools_are_passed(monkeypatch):
    fake_client = _install_fake_client(monkeypatch, [_fake_response("hello")])
    GroqProvider().chat(messages=[{"role": "user", "content": "hi"}], tools=[{"type": "function"}])
    kwargs = fake_client.chat.completions.received_kwargs[0]
    assert kwargs["tool_choice"] == "auto"


def test_chat_includes_response_format_only_in_json_mode(monkeypatch):
    fake_client = _install_fake_client(monkeypatch, [_fake_response('{"a": 1}')])
    GroqProvider().chat(messages=[{"role": "user", "content": "hi"}], json_mode=True)
    kwargs = fake_client.chat.completions.received_kwargs[0]
    assert kwargs["response_format"] == {"type": "json_object"}


def test_chat_returns_real_tool_calls(monkeypatch):
    _install_fake_client(
        monkeypatch,
        [_fake_response(None, [_FakeToolCall("1", "get_missing_values", "{}")])],
    )
    message = GroqProvider().chat(
        messages=[{"role": "user", "content": "hi"}], tools=[{"type": "function"}]
    )
    assert message.tool_calls[0].name == "get_missing_values"


def test_chat_captures_token_usage_when_the_sdk_reports_it(monkeypatch):
    # Added for docs/PHASES.md Phase 8 steps 3 (evals/ tokens-per-
    # question) and 4 (cost logging) — Groq's usage object was
    # previously read at all.
    usage = SimpleNamespace(
        prompt_tokens=120, completion_tokens=30, total_tokens=150, total_time=0.42
    )
    _install_fake_client(monkeypatch, [_fake_response("hello", usage=usage)])
    message = GroqProvider().chat(messages=[{"role": "user", "content": "hi"}])
    assert message.usage == {
        "prompt_tokens": 120,
        "completion_tokens": 30,
        "total_tokens": 150,
        "total_time_ms": 420,
    }


def test_chat_usage_is_none_not_zeroed_when_the_sdk_omits_it(monkeypatch):
    _install_fake_client(monkeypatch, [_fake_response("hello")])
    message = GroqProvider().chat(messages=[{"role": "user", "content": "hi"}])
    assert message.usage is None


def test_chat_retries_on_empty_response_then_succeeds(monkeypatch):
    _install_fake_client(monkeypatch, [_fake_response(None), _fake_response("finally")])
    message = GroqProvider().chat(messages=[{"role": "user", "content": "hi"}])
    assert message.content == "finally"


def test_chat_raises_after_exhausting_retries_on_empty_response(monkeypatch):
    _install_fake_client(
        monkeypatch, [_fake_response(None), _fake_response(None), _fake_response(None)]
    )
    with pytest.raises(AiResponseError):
        GroqProvider().chat(messages=[{"role": "user", "content": "hi"}])


def test_chat_salvages_fake_json_tool_call_from_error_body(monkeypatch):
    # Reproduces the real, live-discovered Groq 400: the model tries to
    # call a nonexistent tool named "json" to express its final answer
    # while `tools=` is still attached. GroqProvider must recover the
    # answer from `error.failed_generation` instead of retrying blindly.
    failed_generation = (
        '{"name": "json", "arguments": '
        '{"answer": "No missing values.", "findings": [], "needs_clarification": null}}'
    )
    bad_request = _BadRequestLike(
        {
            "error": {
                "message": "attempted to call tool 'json' which was not in request.tools",
                "code": "tool_use_failed",
                "failed_generation": failed_generation,
            }
        }
    )
    _install_fake_client(monkeypatch, [bad_request])

    message = GroqProvider().chat(
        messages=[{"role": "user", "content": "hi"}], tools=[{"type": "function"}]
    )

    assert message.tool_calls == []
    assert '"answer": "No missing values."' in (message.content or "")


def test_chat_does_not_salvage_unrelated_bad_request_errors(monkeypatch):
    bad_request = _BadRequestLike({"error": {"message": "some other 400", "code": "other"}})
    _install_fake_client(monkeypatch, [bad_request, bad_request, bad_request])
    with pytest.raises(AiResponseError):
        GroqProvider().chat(messages=[{"role": "user", "content": "hi"}])


# ---- Phase 8 step 4 retry backoff (docs/PROGRESS.md) ----
# Found live during the step 3 eval run: every retry previously fired
# instantly, with no delay at all, immediately replaying the identical
# request into the identical rate limit.


def test_retry_actually_sleeps_between_attempts(monkeypatch):
    sleeps: list[float] = []
    monkeypatch.setattr("app.ai.providers.groq_provider.time.sleep", sleeps.append)
    _install_fake_client(
        monkeypatch, [_BadRequestLike({"error": {"message": "transient"}}), _fake_response("ok")]
    )
    GroqProvider().chat(messages=[{"role": "user", "content": "hi"}])
    assert len(sleeps) == 1
    assert sleeps[0] > 0


def test_retry_delay_honors_groqs_own_suggested_wait_from_error_text(monkeypatch):
    sleeps: list[float] = []
    monkeypatch.setattr("app.ai.providers.groq_provider.time.sleep", sleeps.append)
    monkeypatch.setattr("app.ai.providers.groq_provider.random.uniform", lambda lo, hi: hi)
    rate_limited = _BadRequestLike(
        {"error": {"message": "Rate limit reached ... Please try again in 3.5s.", "code": "x"}}
    )
    _install_fake_client(monkeypatch, [rate_limited, _fake_response("ok")])
    GroqProvider().chat(messages=[{"role": "user", "content": "hi"}])
    assert sleeps == [pytest.approx(3.5)]


def test_retry_delay_is_capped_even_when_groq_suggests_minutes(monkeypatch):
    # The real, live-observed case: a daily-quota 429 suggesting an
    # 18-minute wait. A single HTTP request must never actually block
    # that long — the delay is capped, not honored verbatim.
    sleeps: list[float] = []
    monkeypatch.setattr("app.ai.providers.groq_provider.time.sleep", sleeps.append)
    monkeypatch.setattr("app.ai.providers.groq_provider.random.uniform", lambda lo, hi: hi)
    from app.ai.providers.groq_provider import _MAX_RETRY_DELAY_SECONDS

    rate_limited = _BadRequestLike(
        {"error": {"message": "... Please try again in 18m50.112s.", "code": "x"}}
    )
    _install_fake_client(monkeypatch, [rate_limited, _fake_response("ok")])
    GroqProvider().chat(messages=[{"role": "user", "content": "hi"}])
    assert sleeps == [pytest.approx(_MAX_RETRY_DELAY_SECONDS)]


def test_no_delay_after_the_final_attempt_before_giving_up(monkeypatch):
    sleeps: list[float] = []
    monkeypatch.setattr("app.ai.providers.groq_provider.time.sleep", sleeps.append)
    always_fails = _BadRequestLike({"error": {"message": "persistent"}})
    _install_fake_client(monkeypatch, [always_fails, always_fails, always_fails])
    with pytest.raises(AiResponseError):
        GroqProvider().chat(messages=[{"role": "user", "content": "hi"}])
    # 3 attempts (_MAX_RETRIES=2 -> 3 total) means 2 delays, not 3 — no
    # point sleeping after the attempt that's about to give up anyway.
    assert len(sleeps) == 2
