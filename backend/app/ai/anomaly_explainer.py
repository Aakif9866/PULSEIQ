"""Turns an already-detected anomaly into a short business explanation.

Reuses the existing Groq infrastructure (app.ai.groq_client) — no new AI
provider, model, or service. The AI is given structured, already-computed
anomaly data (see app.monitoring.detection) and asked only to describe and
contextualize it in plain language; it never decides whether something is
anomalous (that's entirely app.monitoring.detection's job, before this
module is ever called) and never sees raw dataset rows.

A small, deliberate duplication of app.ai.analyst's _chat_completion
pattern rather than importing that private helper — keeps this feature
from touching V1's AI Analyst code at all.
"""
from app.core.config import settings
from app.core.exceptions import AiResponseError
from app.core.logging import get_logger

logger = get_logger(__name__)

_EXPLAIN_SYSTEM_PROMPT = """You are a business analytics assistant. You will be given \
structured information about an anomaly that has ALREADY been detected by a statistical \
system — your job is only to explain it in plain, concise business language (2-4 sentences), \
not to judge whether it's really anomalous (that has already been decided).

Rules:
- Reference the actual numbers given to you. Never invent a number that isn't in the input.
- Never claim a specific cause with certainty (e.g. "this was caused by X") unless the input \
itself states it — describe what happened and, if relevant, note a plausible business \
interpretation as a possibility, not a fact.
- Respond in plain text only — no markdown formatting (no **, *, #, backticks, bullet lists).
- Do not mention JSON, statistics, z-scores, or the detection method by name — write for a \
business reader, not a data analyst."""


def is_available() -> bool:
    """Whether an AI explanation can be attempted at all — mirrors the
    AI_PROVIDER check app.services.analyst_service already makes for V1's
    AI Analyst, so anomaly explanations follow the exact same on/off
    switch instead of a second one."""
    return settings.AI_PROVIDER == "groq"


def explain_anomaly(context: dict[str, object]) -> str:
    """context is structured, already-computed anomaly data (metric,
    observed/baseline values, change %, direction, severity — see
    app.services.monitor_service for exactly what's built). Raises
    AiResponseError on any failure; callers decide how to degrade (see
    MonitorService.run_monitor, which persists the anomaly regardless and
    simply leaves explanation=None on failure)."""
    from app.ai.groq_client import get_groq_client

    lines = [f"{key}: {value}" for key, value in context.items()]
    user_prompt = "Anomaly details:\n" + "\n".join(lines)

    client = get_groq_client()
    try:
        response = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {"role": "system", "content": _EXPLAIN_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
        )
    except Exception as exc:
        logger.error("anomaly_explanation_request_failed", exc_info=True)
        raise AiResponseError("The AI provider request failed.") from exc

    content = response.choices[0].message.content
    if not content:
        raise AiResponseError("The AI provider returned an empty response.")
    return content.strip()
