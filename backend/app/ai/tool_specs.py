"""JSON tool schemas (OpenAI/Groq-compatible `tools=[...]` format) plus the
dispatcher that actually calls the matching app.ai.tools function against
the full in-memory dataset. This is the only place a tool *name* the LLM
can request is mapped to a real Python callable — an unknown name is
rejected here, never executed.
"""
from collections.abc import Callable
from typing import Any

import polars as pl

from app.ai import tools

_STRING_ARRAY = {"type": "array", "items": {"type": "string"}}


def _spec(
    name: str, description: str, properties: dict[str, Any], required: list[str]
) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {"type": "object", "properties": properties, "required": required},
        },
    }


TOOL_SPECS: list[dict[str, Any]] = [
    _spec(
        "get_dataset_profile",
        "Get the full dataset profile: row/column counts, per-column stats, "
        "duplicates, outliers, correlations, and temporal ranges. Call this "
        "first for any broad question about the dataset as a whole.",
        {},
        [],
    ),
    _spec(
        "get_column_statistics",
        "Get detailed statistics for one specific column.",
        {"column": {"type": "string"}},
        ["column"],
    ),
    _spec(
        "get_missing_values",
        "Get missing-value counts and percentages for every column.",
        {},
        [],
    ),
    _spec(
        "get_duplicates",
        "Find duplicate rows, or duplicate values in one specific column "
        "(e.g. a duplicated order/customer ID).",
        {
            "column": {
                "type": "string",
                "description": "Optional — omit to check whole-row duplicates.",
            }
        },
        [],
    ),
    _spec(
        "get_unique_values",
        "List the distinct values in a column, with counts.",
        {"column": {"type": "string"}, "limit": {"type": "integer"}},
        ["column"],
    ),
    _spec(
        "group_by_aggregate",
        "Aggregate a numeric column, grouped by one or more other columns "
        "(e.g. total revenue per category).",
        {
            "group_by": _STRING_ARRAY,
            "column": {"type": "string", "description": "Omit only if op is 'count'."},
            "op": {"type": "string", "enum": ["sum", "avg", "min", "max", "count"]},
        },
        ["group_by", "op"],
    ),
    _spec(
        "filter_rows",
        "Count and sample rows matching a single condition on one column.",
        {
            "column": {"type": "string"},
            "op": {"type": "string", "enum": ["eq", "ne", "gt", "gte", "lt", "lte", "contains"]},
            "value": {},
            "limit": {"type": "integer"},
        },
        ["column", "op", "value"],
    ),
    _spec(
        "detect_outliers",
        "Detect statistical outliers in a numeric column using the IQR method. "
        "A statistical outlier is not automatically an error — it may be a "
        "legitimate extreme value.",
        {"column": {"type": "string"}},
        ["column"],
    ),
    _spec(
        "detect_logical_violations",
        "Find values that violate common-sense bounds for columns whose name "
        "suggests a bounded meaning (e.g. age, rating, a percentage/score). "
        "This IS a rule violation, unlike a statistical outlier.",
        {},
        [],
    ),
    _spec(
        "detect_anomalies",
        "Get a combined summary of outliers, logical violations, duplicates, "
        "and missing data across the whole dataset — a good starting point "
        "for an open-ended 'find anomalies' question.",
        {},
        [],
    ),
    _spec(
        "calculate_correlation",
        "Calculate the Pearson correlation between two numeric columns.",
        {"column_a": {"type": "string"}, "column_b": {"type": "string"}},
        ["column_a", "column_b"],
    ),
    _spec(
        "time_series_analysis",
        "Aggregate a numeric metric over time, bucketed by day/week/month, "
        "with a simple trend direction.",
        {
            "date_column": {"type": "string"},
            "metric_column": {"type": "string"},
            "freq": {"type": "string", "enum": ["day", "week", "month"]},
        },
        ["date_column", "metric_column"],
    ),
    _spec(
        "compare_groups",
        "Compare a metric across the values of a grouping column (e.g. "
        "compare average revenue between two channels).",
        {
            "group_column": {"type": "string"},
            "metric_column": {"type": "string"},
            "op": {"type": "string", "enum": ["sum", "avg", "min", "max"]},
        },
        ["group_column", "metric_column"],
    ),
    _spec(
        "validate_formula",
        "Check whether a column's actual values match an arithmetic formula "
        "over other real columns (e.g. 'units * unit_price * (1 - "
        "discount_pct / 100)'). Use this for business-rule / revenue-"
        "integrity questions instead of guessing.",
        {
            "target_column": {"type": "string"},
            "formula": {
                "type": "string",
                "description": "An arithmetic expression using only real column names.",
            },
            "tolerance_pct": {"type": "number"},
        },
        ["target_column", "formula"],
    ),
    _spec(
        "get_top_records",
        "Get the N rows with the highest values in a column.",
        {"column": {"type": "string"}, "n": {"type": "integer"}},
        ["column"],
    ),
    _spec(
        "get_bottom_records",
        "Get the N rows with the lowest values in a column.",
        {"column": {"type": "string"}, "n": {"type": "integer"}},
        ["column"],
    ),
]

_DISPATCH: dict[str, Callable[..., dict[str, Any]]] = {
    "get_dataset_profile": tools.get_dataset_profile,
    "get_column_statistics": tools.get_column_statistics,
    "get_missing_values": tools.get_missing_values,
    "get_duplicates": tools.get_duplicates,
    "get_unique_values": tools.get_unique_values,
    "group_by_aggregate": tools.group_by_aggregate,
    "filter_rows": tools.filter_rows,
    "detect_outliers": tools.detect_outliers,
    "detect_logical_violations": tools.detect_logical_violations,
    "detect_anomalies": tools.detect_anomalies,
    "calculate_correlation": tools.calculate_correlation,
    "time_series_analysis": tools.time_series_analysis,
    "compare_groups": tools.compare_groups,
    "validate_formula": tools.validate_formula,
    "get_top_records": tools.get_top_records,
    "get_bottom_records": tools.get_bottom_records,
}


def call_tool(name: str, df: pl.DataFrame, arguments: dict[str, Any]) -> dict[str, Any]:
    """Executes a tool the LLM requested by name. An unknown tool name, a
    missing/wrong-typed argument, or an internal error is always turned
    into a small {"error": "..."} dict — the calling loop feeds that back
    to the model as the tool's result (so it can adjust and try again),
    never lets an exception escape and abort the whole analysis."""
    func = _DISPATCH.get(name)
    if func is None:
        return {"error": f"Unknown tool: {name}"}
    try:
        return func(df, **arguments)
    except TypeError as exc:
        return {"error": f"Invalid arguments for {name}: {exc}"}
    except Exception as exc:  # noqa: BLE001 - a tool must never crash the analysis loop
        return {"error": f"{name} failed: {exc}"}
