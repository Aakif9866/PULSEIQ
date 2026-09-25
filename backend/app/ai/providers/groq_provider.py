"""The only AIProvider actually implemented and exercised in this
project — wraps the existing app.ai.groq_client, adding the reliability
layer docs/AI_ANALYTICS.md calls for: retries on a failed or empty
response, and malformed tool-call-argument JSON recovered rather than
crashing the whole analysis. Every failure path still ends in
AiResponseError, never a silent blank answer — see
app/services/analysis_service.py for the user-facing fallback message
this feeds into.
"""
import json
from typing import Any

from app.ai.providers.base import AIProvider, ProviderMessage, ToolCall
from app.core.config import settings
from app.core.exceptions import AiResponseError
from app.core.logging import get_logger

logger = get_logger(__name__)

_MAX_RETRIES = 2


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
                logger.warning(
                    "groq_provider_request_failed", attempt=attempt, error=str(exc)
                )
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
