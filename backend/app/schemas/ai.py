from pydantic import BaseModel, Field

from app.schemas.dashboard import ChartType
from app.schemas.dataset_query import DatasetQueryRequest, DatasetQueryResult


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


class AskResponse(BaseModel):
    question: str
    answer: str
    query: DatasetQueryRequest
    result: DatasetQueryResult
    # Deterministic (app.analytics.chart_suggestion), never AI-decided —
    # see docs/V2_ROADMAP.md's "AI Visualization Intelligence". Always a
    # suggestion the user can override, never applied silently.
    suggested_chart_type: ChartType


class AskSqlResponse(BaseModel):
    """The Natural Language to SQL path (docs/V2_ROADMAP.md) — a sibling
    to AskResponse, not a replacement. generated_sql is always the exact,
    validated SQL that was actually run, shown to the user for
    transparency and reuse (e.g. copying it into the SQL Explorer)."""

    question: str
    answer: str
    generated_sql: str
    result: DatasetQueryResult
