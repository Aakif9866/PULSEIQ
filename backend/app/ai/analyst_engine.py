"""The hybrid AI Analyst engine — the core redesign described in
docs/AI_ANALYTICS.md:

    question -> LLM interprets intent -> tool calls execute against the
    FULL dataset -> structured evidence -> LLM interprets evidence ->
    validation -> final answer

The LLM never computes a statistic itself — app.ai.tools does, against
the real, complete Polars DataFrame, never a preview or a sample. This
module only orchestrates: which tools get called, feeding their real
results back to the model, and turning its final structured response
into a validated AnalyzeResponse.
"""
import json
import time
from typing import Any

import polars as pl
from opentelemetry.trace import Status, StatusCode
from pydantic import ValidationError

from app.ai.answer_validator import validate_findings
from app.ai.providers.base import AIProvider
from app.ai.tool_specs import TOOL_SPECS, call_tool
from app.core.exceptions import AiResponseError
from app.core.logging import get_logger
from app.core.tracing import get_tracer
from app.schemas.analysis import AnalyzeResponse, ConversationTurn, Finding, ToolCallRecord

logger = get_logger(__name__)

_MAX_TOOL_ITERATIONS = 6
_MAX_TOOL_RESULT_CHARS = 4000
_MAX_HISTORY_TURNS = 5

_SYSTEM_PROMPT = """You are a rigorous data analyst assistant. You have tools that compute \
real statistics from the user's FULL dataset — you MUST call a tool to get any number before \
stating it in your answer. Never invent, estimate, or round a number from memory. If a \
question needs several computations, call multiple tools, one at a time, before answering.

Dataset columns:
{column_overview}

Once you have enough evidence, respond with ONLY a single JSON object (no prose, no markdown \
fences) shaped exactly like this:
{{
  "answer": "<a concise, plain-language analyst answer, 3-6 sentences,
             no code, no raw tool names>",
  "findings": [
    {{
      "claim": "<one specific factual claim>",
      "value": <number, string, or null>,
      "unit": "<e.g. 'rows', 'percent', 'INR', or null>",
      "affected_rows": <integer or null>,
      "total_rows": <integer or null>,
      "calculation": "<which computation produced this, in plain words>",
      "classification": "<one of: statistical_outlier, logical_violation,
                          missing_data, duplicate, referential_inconsistency,
                          cross_column_inconsistency, temporal_anomaly,
                          potential_business_anomaly,
                          confirmed_data_quality_issue, unknown>",
      "confidence": "<high|medium|low>",
      "evidence": ["<short line citing an actual computed result>"]
    }}
  ],
  "needs_clarification": null
}}

Rules:
- Every "value" / "affected_rows" / "total_rows" MUST come from an actual tool result you \
already received in this conversation — never a guess.
- Distinguish a statistical_outlier (an extreme but possibly legitimate value) from a \
logical_violation (outside a documented/common-sense range) — never call every unusual value \
an error.
- Never state a root cause as settled fact. Use "may indicate", "a possible explanation is", or \
"this would require further verification" for anything the data doesn't directly prove.
- If a question needs a column that doesn't exist in this dataset, say so plainly in "answer" \
instead of guessing, and return an empty "findings" list.
- If a term like "best" is ambiguous, state the interpretation you used in "answer" rather than \
setting "needs_clarification" — only set it when the ambiguity would genuinely change the answer.
- "answer" must read like an analyst talking to a colleague — never mention tool names, JSON, or \
Python/pandas code unless the user explicitly asked for code."""

_FINAL_JSON_NUDGE = (
    "Based on everything computed so far, respond now with ONLY the JSON "
    "object described earlier — no other text."
)

_FALLBACK_MESSAGE = (
    "Analysis could not be completed because the AI service returned an empty or invalid "
    "response. Your dataset was loaded successfully and the computations that did run are "
    "shown below. Please retry."
)


def _traced_tool_call(name: str, df: pl.DataFrame, arguments: dict[str, Any]) -> dict[str, Any]:
    """One span and one log line per tool call — both inherit the
    request's request_id/trace from context, so a single request can be
    followed from the HTTP layer through every tool it triggered.
    Argument *names* are recorded, never values: a filter value is the
    user's own data."""
    start = time.perf_counter()
    with get_tracer().start_as_current_span(f"tool.{name}") as span:
        span.set_attribute("pulseiq.tool.name", name)
        span.set_attribute("pulseiq.tool.argument_names", sorted(arguments))
        result = call_tool(name, df, arguments)
        error = result.get("error") if isinstance(result, dict) else None
        if error:
            span.set_status(Status(StatusCode.ERROR, str(error)[:200]))
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.info(
            "tool_call_completed",
            tool=name,
            duration_ms=duration_ms,
            failed=bool(error),
        )
        return result


def _column_overview(df: pl.DataFrame) -> str:
    return "\n".join(f"- {name} ({dtype})" for name, dtype in df.schema.items())


def _tool_messages(tool_call_id: str, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": tool_call_id,
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(arguments, default=str)},
    }


def _serialize_tool_result(result: dict[str, Any]) -> str:
    serialized = json.dumps(result, default=str)
    if len(serialized) > _MAX_TOOL_RESULT_CHARS:
        return serialized[:_MAX_TOOL_RESULT_CHARS] + " ...[truncated, result too large]"
    return serialized


def _parse_final_answer(content: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _build_findings(raw_findings: list[Any]) -> list[Finding]:
    findings: list[Finding] = []
    for raw in raw_findings:
        if not isinstance(raw, dict):
            continue
        try:
            findings.append(Finding.model_validate(raw))
        except ValidationError as exc:
            logger.warning("analysis_finding_dropped_invalid_shape", error=str(exc))
    return findings


def run_analysis(
    df: pl.DataFrame,
    provider: AIProvider,
    question: str,
    conversation_history: list[ConversationTurn] | None = None,
) -> AnalyzeResponse:
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": _SYSTEM_PROMPT.format(column_overview=_column_overview(df))}
    ]
    for turn in (conversation_history or [])[-_MAX_HISTORY_TURNS:]:
        messages.append({"role": "user", "content": turn.question})
        messages.append({"role": "assistant", "content": turn.answer})
    messages.append({"role": "user", "content": question})

    tool_records: list[ToolCallRecord] = []
    tools_exhausted = True
    salvaged_final: dict[str, Any] | None = None

    for _ in range(_MAX_TOOL_ITERATIONS):
        # Deliberately never mixed with json_mode, and never the call we
        # ask for a final answer from: a model with `tools` attached and
        # no more real tool calls to make sometimes tries to express its
        # final JSON answer *as a fake tool call* instead of plain content
        # (a real 400 from Groq — "attempted to call tool 'json'..." —
        # found live, not assumed). GroqProvider now salvages that case by
        # recovering the model's real intended content from the error
        # body, so this call's only two outcomes are still "make another
        # real tool call" or "stop gathering evidence" — but its
        # plain-text content is checked below in case it's actually a
        # salvaged final answer, rather than always re-asked for.
        #
        # Guarded exactly like the final call below. Found live (Phase 8
        # step 5, docs/BUGS.md BUG-017): only the final call used to be
        # guarded, so a provider failure on *this* call — Groq's daily
        # rate limit, in the case that found it — escaped run_analysis
        # entirely, and the route turned it into a generic 400 "request
        # could not be completed" instead of the designed degraded answer.
        try:
            message = provider.chat(messages=messages, tools=TOOL_SPECS, temperature=0.1)
        except AiResponseError:
            return _fallback_response(question, tool_records)

        if not message.tool_calls:
            tools_exhausted = False
            candidate = _parse_final_answer(message.content or "")
            if isinstance(candidate, dict) and "answer" in candidate:
                # A salvaged fake-"json"-tool-call: this IS the complete
                # final answer already, so skip the extra dedicated call
                # below — both to avoid burning another (rate-limited)
                # request and because the model has nothing new to add.
                salvaged_final = candidate
            break

        messages.append(
            {
                "role": "assistant",
                "content": message.content,
                "tool_calls": [
                    _tool_messages(tc.id, tc.name, tc.arguments) for tc in message.tool_calls
                ],
            }
        )
        for tc in message.tool_calls:
            result = _traced_tool_call(tc.name, df, tc.arguments)
            tool_records.append(
                ToolCallRecord(tool=tc.name, arguments=tc.arguments, result=result)
            )
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": _serialize_tool_result(result),
                }
            )

    if tools_exhausted:
        logger.warning("analysis_hit_max_tool_iterations", question=question)

    if salvaged_final is not None:
        parsed: dict[str, Any] | None = salvaged_final
    else:
        # One dedicated, tools-disabled, json_mode call for the actual
        # final answer — the model can no longer "call a tool" here at
        # all, which is what makes it reliably return plain JSON content
        # instead.
        messages.append({"role": "user", "content": _FINAL_JSON_NUDGE})
        try:
            final = provider.chat(messages=messages, json_mode=True, temperature=0.1)
        except AiResponseError:
            return _fallback_response(question, tool_records)
        parsed = _parse_final_answer(final.content or "")

    if parsed is None:
        return _fallback_response(question, tool_records)

    findings = _build_findings(parsed.get("findings") or [])
    findings, warnings = validate_findings(findings, tool_records)

    return AnalyzeResponse(
        question=question,
        answer=str(parsed.get("answer") or "").strip() or _FALLBACK_MESSAGE,
        findings=findings,
        tool_calls=tool_records,
        needs_clarification=parsed.get("needs_clarification"),
        status="ok" if parsed.get("answer") else "degraded",
        warnings=warnings,
    )


def _fallback_response(question: str, tool_records: list[ToolCallRecord]) -> AnalyzeResponse:
    logger.error(
        "analysis_fallback_triggered", question=question, tool_call_count=len(tool_records)
    )
    return AnalyzeResponse(
        question=question,
        answer=_FALLBACK_MESSAGE,
        findings=[],
        tool_calls=tool_records,
        status="degraded",
        warnings=["The AI provider did not return a usable final answer."],
    )
