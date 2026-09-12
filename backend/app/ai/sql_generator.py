"""Turns a natural-language question into a candidate SQL SELECT statement.

Reuses the existing Groq infrastructure — no new AI provider. Unlike
app.ai.analyst's structured-query generation (JSON mode, since the output
is a JSON object), this is plain-text completion, because the output is
SQL text. That means a stricter, more careful validation step matters
more here than it does for the JSON path — see
app.analytics.sql_validator, which every string this module returns must
pass through before it's ever executed. This module's own job is only to
ask the model for SQL; it has no opinion on whether that SQL is safe.
"""
import re

import polars as pl

from app.core.config import settings
from app.core.exceptions import AiResponseError
from app.core.logging import get_logger
from app.models.dataset import Dataset

logger = get_logger(__name__)

_TABLE_NAME = "dataset"
# Columns with at most this many distinct values get their actual values
# shown to the model — this is what makes "compare profit margins across
# categories" answerable, since the model needs to know what a category
# column actually contains, not just that it exists (see
# docs/V2_ROADMAP.md's "how schema context should be generated").
_MAX_SAMPLE_VALUES = 20

_SQL_SYSTEM_PROMPT = """You are a data analyst assistant that writes DuckDB SQL. Given a table \
named "{table}" with the columns listed below, write ONE SELECT statement that answers the \
user's question.

Rules:
- Output ONLY the raw SQL. No markdown fences, no prose, no explanation, no trailing semicolon.
- Exactly one SELECT statement. Never DDL/DML (no INSERT/UPDATE/DELETE/DROP/CREATE/ALTER).
- Only reference the table "{table}" — no other tables, files, or functions as a data source.
- Only reference column names that are actually listed below.
- Use standard SQL aggregate functions (SUM/AVG/MIN/MAX/COUNT) and GROUP BY/ORDER \
BY/WHERE as needed.

Columns:
{columns}"""


def _describe_columns(dataset: Dataset, df: pl.DataFrame) -> str:
    lines = []
    for col in dataset.columns_profile or []:
        name = col["name"]
        dtype = col["dtype"]
        line = f"- {name} ({dtype})"
        if name in df.columns and df.schema.get(name) == pl.Utf8:
            distinct = df[name].drop_nulls().unique()
            if 0 < distinct.len() <= _MAX_SAMPLE_VALUES:
                values = ", ".join(str(v) for v in distinct.to_list())
                line += f" — example values: {values}"
        lines.append(line)
    return "\n".join(lines)


def _strip_markdown_fence(text: str) -> str:
    """Defensive only — the prompt already asks for raw SQL, but models
    sometimes wrap output in ```sql fences anyway."""
    stripped = text.strip()
    match = re.match(r"^```(?:sql)?\s*(.*?)\s*```$", stripped, re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else stripped


def build_sql_from_question(question: str, dataset: Dataset, df: pl.DataFrame) -> str:
    from app.ai.groq_client import get_groq_client

    system_prompt = _SQL_SYSTEM_PROMPT.format(
        table=_TABLE_NAME, columns=_describe_columns(dataset, df)
    )

    client = get_groq_client()
    try:
        response = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question},
            ],
            temperature=0.1,
        )
    except Exception as exc:
        logger.error("sql_generation_request_failed", exc_info=True)
        raise AiResponseError("The AI provider request failed.") from exc

    content = response.choices[0].message.content
    if not content:
        raise AiResponseError("The AI provider returned an empty response.")
    return _strip_markdown_fence(content)
