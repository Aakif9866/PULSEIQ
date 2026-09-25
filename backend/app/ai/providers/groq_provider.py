"""The only AIProvider actually implemented and exercised in this
project — wraps the existing app.ai.groq_client, adding the reliability
layer docs/AI_ANALYTICS.md calls for: retries on a failed or empty
response, and malformed tool-call-argument JSON recovered rather than
crashing the whole analysis. Every failure path still ends in
AiResponseError, never a silent blank answer — see
app/services/analysis_service.py for the user-facing fallback message
this feeds into.

Retry backoff (docs/PHASES.md Phase 8 step 4): found live, not assumed
— every retry previously fired with NO delay at all, immediately
replaying the identical request into the identical rate limit. A real
429 during the step 3 eval run showed this doing nothing useful; a
harder one (Groq's *daily* token cap, not just per-minute) made the gap
obvious — no in-request retry delay, however generous, helps when the
suggested wait is 18+ minutes. So the fix has two parts, not one: real
delay-then-retry for the genuinely brief case (jittered, honoring
Groq's own suggested wait via the response's Retry-After header or its
error-message text when present), capped low (_MAX_RETRY_DELAY_SECONDS)
so one slow provider call can never make a single HTTP request hang for
minutes — and, for waits past what a live request should ever block on,
that's what a configurable fallback provider is for, not a longer
sleep. See FallbackProvider below.
"""
import json
import random
import re
import time
from typing import Any

from app.ai.providers.base import AIProvider, ProviderMessage, ToolCall
from app.core.config import settings
from app.core.exceptions import AiResponseError
from app.core.logging import get_logger

logger = get_logger(__name__)

_MAX_RETRIES = 2
# A real request can't block on Groq's own suggested wait when that's
# minutes long (observed live: 5s up to 18m50s for the same daily-quota
# error) — this bounds what an automatic in-request retry will ever
# actually sleep for, regardless of what Groq suggests. Waits longer
# than this need a fallback provider or the caller giving up, not a
# longer sleep here.
_MAX_RETRY_DELAY_SECONDS = 8.0
_BASE_BACKOFF_SECONDS = 0.5
_RETRY_AFTER_TEXT_RE = re.compile(r"try again in (?:(\d+)m)?([\d.]+)s", re.IGNORECASE)


def _suggested_retry_delay(exc: Exception) -> float | None:
    """Reads Groq's own suggested wait, when it tells us one — the
    standard `Retry-After` response header first, then (Groq doesn't
    always set that header even though its error *message* always
    names a wait — verified live) its human-readable error text as a
    fallback. Returns None, not a guess, when neither is present."""
    response = getattr(exc, "response", None)
    header_value = getattr(response, "headers", {}).get("retry-after") if response else None
    if header_value is not None:
        try:
            return float(header_value)
        except ValueError:
            pass
    message = str(exc)
    match = _RETRY_AFTER_TEXT_RE.search(message)
    if match:
        minutes = float(match.group(1)) if match.group(1) else 0.0
        seconds = float(match.group(2))
        return minutes * 60 + seconds
    return None


def _retry_delay_seconds(exc: Exception, attempt: int) -> float:
    suggested = _suggested_retry_delay(exc)
    base = suggested if suggested is not None else _BASE_BACKOFF_SECONDS * (2**attempt)
    capped = min(base, _MAX_RETRY_DELAY_SECONDS)
    # Full jitter (not just +/-): spreads out multiple concurrent
    # requests that all just hit the same rate limit at once, instead of
    # every one of them retrying in lockstep at the exact same moment.
    return random.uniform(0, capped)


def _safe_parse_arguments(raw: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        logger.warning("groq_tool_call_arguments_malformed", raw=raw)
        return {}


def _salvage_fake_json_tool_call(exc: Exception) -> ProviderMessage | None:
    """Even with `tools` still attached (mid-loop, before we've decided the
    model is done gathering evidence), the model sometimes tries to express
    its final answer as a fake tool call literally named "json" instead of
    plain content — a real 400 from Groq ("attempted to call tool 'json'
    which was not in request.tools"), found live, not assumed. Retrying the
    identical request just reproduces the same 400 until retries are
    exhausted and the whole analysis falls back, even though the model's
    intended answer is sitting right there: Groq echoes it back verbatim in
    the error body's `failed_generation` field as
    `{"name": "json", "arguments": {...the real answer...}}`. Recover it
    instead of discarding it.
    """
    body = getattr(exc, "body", None)
    if not isinstance(body, dict):
        return None
    error = body.get("error")
    if not isinstance(error, dict) or error.get("code") != "tool_use_failed":
        return None
    failed_generation = error.get("failed_generation")
    if not isinstance(failed_generation, str):
        return None
    try:
        parsed = json.loads(failed_generation)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict) or parsed.get("name") != "json":
        return None
    arguments = parsed.get("arguments")
    if isinstance(arguments, str):
        content = arguments
    elif isinstance(arguments, dict):
        content = json.dumps(arguments)
    else:
        return None
    logger.warning("groq_provider_salvaged_fake_json_tool_call")
    return ProviderMessage(content=content, tool_calls=[])


def _extract_usage(response: Any) -> dict[str, int] | None:
    """Groq's response.usage is an OpenAI-compatible CompletionUsage —
    prompt/completion/total tokens, plus Groq-reported generation time
    (`total_time`, seconds) which is a more precise "how long did the
    model actually take" number than a caller's own wall-clock timing
    (that also includes network/queueing). None (not a zeroed dict) when
    the SDK didn't report usage at all, so a caller can tell the
    difference rather than silently summing in a false zero."""
    usage = getattr(response, "usage", None)
    if usage is None:
        return None
    result: dict[str, int] = {}
    for field_name in ("prompt_tokens", "completion_tokens", "total_tokens"):
        value = getattr(usage, field_name, None)
        if value is not None:
            result[field_name] = value
    total_time = getattr(usage, "total_time", None)
    if total_time is not None:
        result["total_time_ms"] = round(total_time * 1000)
    return result or None


class GroqProvider(AIProvider):
    def chat(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        json_mode: bool = False,
        temperature: float = 0.1,
    ) -> ProviderMessage:
        from app.ai.groq_client import get_groq_client

        client = get_groq_client()
        last_error: Exception | None = None

        # Built conditionally rather than always passed (even as an
        # explicit None) — the SDK serializes an explicit None as JSON
        # `null`, and Groq's API rejects tool_choice/response_format
        # being present at all when there's nothing meaningful to set,
        # rather than treating null as "omitted". Found by a real 400
        # error during live testing, not assumed.
        kwargs: dict[str, Any] = {
            "model": settings.GROQ_MODEL,
            "messages": messages,
            "temperature": temperature,
            "timeout": settings.AI_REQUEST_TIMEOUT_SECONDS,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        for attempt in range(_MAX_RETRIES + 1):
            try:
                response = client.chat.completions.create(**kwargs)
            except Exception as exc:  # noqa: BLE001 - any SDK/network failure, retried uniformly
                salvaged = _salvage_fake_json_tool_call(exc)
                if salvaged is not None:
                    return salvaged
                last_error = exc
                delay = _retry_delay_seconds(exc, attempt) if attempt < _MAX_RETRIES else 0.0
                logger.warning(
                    "groq_provider_request_failed",
                    attempt=attempt, error=str(exc), retry_delay_seconds=round(delay, 2),
                )
                if delay:
                    time.sleep(delay)
                continue

            message = response.choices[0].message
            raw_tool_calls = message.tool_calls or []
            tool_calls = [
                ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=_safe_parse_arguments(tc.function.arguments),
                )
                for tc in raw_tool_calls
            ]

            if not message.content and not tool_calls:
                # The exact "empty response" failure mode docs/AI_ANALYTICS.md
                # names explicitly — retry rather than surface a blank answer.
                logger.warning("groq_provider_empty_response", attempt=attempt)
                last_error = AiResponseError("The AI provider returned an empty response.")
                continue

            return ProviderMessage(
                content=message.content, tool_calls=tool_calls, usage=_extract_usage(response)
            )

        logger.error("groq_provider_exhausted_retries", error=str(last_error))
        raise AiResponseError(
            "The AI provider did not return a usable response after retrying."
        ) from last_error
