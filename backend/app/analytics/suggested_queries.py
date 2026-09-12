"""Schema-derived query suggestions for the SQL Explorer — no AI call, no
row scan; built entirely from a dataset's already-computed column
profile (app.analytics.profiling). See docs/V2_ROADMAP.md's "SQL
Explorer" section.
"""
import re
from typing import Any

from app.schemas.history import SuggestedQuery

_NUMERIC_DTYPES = {"Int64", "Int32", "Float64", "Float32"}
_MAX_CATEGORICAL_SUGGESTIONS = 5
_MAX_NUMERIC_SUGGESTIONS = 5


def _safe_alias(name: str) -> str:
    """A column name is always safely usable quoted (e.g. "my col"), but
    an alias is a bare identifier — sanitize it so the suggested SQL is
    always valid regardless of what characters the real column name has."""
    return re.sub(r"\W+", "_", name).strip("_") or "value"


def build_suggested_queries(columns_profile: list[dict[str, Any]]) -> list[SuggestedQuery]:
    suggestions = [
        SuggestedQuery(label="Preview the first 100 rows", sql="SELECT * FROM dataset LIMIT 100")
    ]

    categorical = [c["name"] for c in columns_profile if c.get("dtype") == "String"]
    for name in categorical[:_MAX_CATEGORICAL_SUGGESTIONS]:
        suggestions.append(
            SuggestedQuery(
                label=f"Count rows by {name}",
                sql=f'SELECT "{name}", COUNT(*) AS count FROM dataset GROUP BY "{name}" '
                f'ORDER BY count DESC',
            )
        )

    numeric = [c["name"] for c in columns_profile if c.get("dtype") in _NUMERIC_DTYPES]
    for name in numeric[:_MAX_NUMERIC_SUGGESTIONS]:
        suggestions.append(
            SuggestedQuery(
                label=f"Total {name}",
                sql=f'SELECT SUM("{name}") AS total_{_safe_alias(name)} FROM dataset',
            )
        )

    return suggestions
