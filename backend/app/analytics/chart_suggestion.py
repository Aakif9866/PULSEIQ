"""Suggests a chart type for a query result — deterministic rules, not an
AI call. See docs/V2_ROADMAP.md's "AI Visualization Intelligence": a
DatasetQueryRequest's own shape already implies the right chart type in
the common case (a date-typed group-by -> line over time; a categorical
group-by -> bar; no group-by at all -> a single KPI number), so this is
ordinary, fully testable code rather than a third free-form model call —
deliberately avoiding the harder, less reliable AI-first version of this
feature described in the roadmap.
"""
from app.schemas.dashboard import ChartType
from app.schemas.dataset_query import DatasetQueryRequest

_DATE_NAME_HINTS = ("date", "time", "day", "month", "year", "week")
_DATE_DTYPES = {"date", "datetime"}


def suggest_chart_type(request: DatasetQueryRequest, column_dtypes: dict[str, str]) -> ChartType:
    """Only ever called with a *validated, already-executed* request —
    this never decides whether the request itself is valid, only what to
    render it as."""
    if not request.aggregations:
        # No summarization happened — this is a raw, filtered row preview.
        return "table"

    if not request.group_by:
        # A single aggregate over the whole dataset (e.g. SUM(revenue)) —
        # exactly the "one headline number" case the dataviz skill calls
        # a stat tile, not a chart.
        return "kpi"

    if len(request.group_by) == 1:
        if _looks_like_date(request.group_by[0], column_dtypes):
            return "line"
        return "bar"

    # Multiple group-by columns don't fit a single 2D chart well — a
    # table stays honest rather than guessing at a misleading chart.
    return "table"


def _looks_like_date(column_name: str, column_dtypes: dict[str, str]) -> bool:
    dtype = column_dtypes.get(column_name, "").lower()
    if dtype in _DATE_DTYPES:
        return True
    name = column_name.lower()
    return any(hint in name for hint in _DATE_NAME_HINTS)
