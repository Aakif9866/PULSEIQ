"""Turns a natural-language question into a grounded answer.

Two Groq calls, not one:
  1. question + column profile -> a DatasetQueryRequest (JSON, validated by
     Pydantic) — reuses app.analytics.query_engine's existing safety
     guarantees (row cap, timeout, no free-form SQL) instead of inventing a
     new execution path.
  2. question + the *actual computed result* -> a plain-language answer,
     so the model is summarizing real numbers, not guessing at them.
"""
import json

from app.core.config import settings
from app.core.exceptions import AiResponseError
from app.core.logging import get_logger
from app.models.dataset import Dataset
from app.schemas.dataset_query import DatasetQueryRequest, DatasetQueryResult

logger = get_logger(__name__)

_MAX_ROWS_FOR_SUMMARY = 50

_QUERY_SYSTEM_PROMPT = """You are a data analyst assistant. Given a dataset's column profile \
and a user's question, respond with ONLY a single JSON object (no prose, no markdown fences) \
shaped exactly like this:

{
  "group_by": [<column names to group by, or an empty list>],
  "aggregations": [
    {"op": "sum" | "avg" | "min" | "max" | "count", "column": <column name, omit for "count">, \
"alias": <short snake_case name for this output column>}
  ],
  "filters": [
    {"column": <name>, "op": "eq" | "ne" | "gt" | "gte" | "lt" | "lte" | "contains", \
"value": <string, number, or boolean>}
  ],
  "sort_by": <column name to sort the result by, or null>,
  "sort_desc": true | false,
  "limit": <integer, or null>
}

Rules:
- Only ever reference column names that are actually listed below.
- If the question asks for a total/average/count/etc., use "aggregations" (with "group_by" if \
the question is "per <something>").
- If the question just wants to see/filter specific rows, leave "aggregations" empty.
- "aggregations" and "group_by" are the ONLY way to summarize; never leave both empty AND expect \
a summary — an empty "aggregations" list means "return raw rows"."""

_ANSWER_SYSTEM_PROMPT = """You are a data analyst assistant. Given a user's question and the \
result of a query already run against their dataset, write a concise, plain-language answer \
(2-4 sentences). Reference the actual numbers in the result. Never mention JSON, queries, SQL, \
or code — answer as if you already knew the answer. Respond in plain text only — no markdown \
formatting (no **, *, #, backticks, or bullet lists).

You cannot modify, delete, add, or update any data — you can only read and summarize it. If the \
question asks you to change data in any way (delete, update, insert, overwrite, clear, reset, \
etc.), say plainly that you can't do that and that you can only analyze the data as it is — \
never describe a change as if it happened or could happen, even hypothetically."""


def _chat_completion(*, system_prompt: str, user_prompt: str, json_mode: bool) -> str:
    from app.ai.groq_client import get_groq_client

    client = get_groq_client()
    try:
        response = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            response_format={"type": "json_object"} if json_mode else None,
        )
    except Exception as exc:
        logger.error("groq_request_failed", exc_info=True)
        raise AiResponseError("The AI provider request failed.") from exc

    content = response.choices[0].message.content
    if not content:
        raise AiResponseError("The AI provider returned an empty response.")
    return content


def build_query_from_question(question: str, dataset: Dataset) -> DatasetQueryRequest:
    columns_description = "\n".join(
        f"- {col['name']} ({col['dtype']})" for col in (dataset.columns_profile or [])
    )
    user_prompt = (
        f"Dataset columns:\n{columns_description}\n\n"
        f"Total rows: {dataset.row_count}\n\n"
        f"Question: {question}"
    )
    raw = _chat_completion(
        system_prompt=_QUERY_SYSTEM_PROMPT, user_prompt=user_prompt, json_mode=True
    )

    try:
        parsed = json.loads(raw)
        return DatasetQueryRequest.model_validate(parsed)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("ai_query_parse_failed", raw_response=raw)
        raise AiResponseError(
            "Couldn't turn that question into a query. Try rephrasing it."
        ) from exc


def summarize_result(question: str, result: DatasetQueryResult) -> str:
    preview_rows = result.rows[:_MAX_ROWS_FOR_SUMMARY]
    is_preview = result.truncated or len(preview_rows) < result.row_count
    user_prompt = (
        f"Question: {question}\n\n"
        f"Result columns: {result.columns}\n"
        f"Result rows: {preview_rows}\n"
        f"Total matching rows: {result.row_count}"
        f"{' (showing a preview only)' if is_preview else ''}"
    )
    return _chat_completion(
        system_prompt=_ANSWER_SYSTEM_PROMPT, user_prompt=user_prompt, json_mode=False
    ).strip()
