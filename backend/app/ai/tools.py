"""The analytical tool layer the hybrid AI Analyst calls into.

Every function here takes the FULL in-memory dataset (a Polars
DataFrame) and returns a plain JSON-serializable dict — never prose. This
is the actual "source of truth" layer described in docs/AI_ANALYTICS.md's
redesign: the LLM decides *which* tool answers a question, but every
number in the final answer must trace back to one of these functions
actually running against the real data — the LLM never computes a
statistic itself. Reuses existing, already-tested infrastructure
wherever the same computation already exists elsewhere in the codebase
(the structured query engine, the SQL validator/engine) rather than
reimplementing it.
"""
from typing import Any

import polars as pl

from app.analytics.data_profile import build_data_profile
from app.analytics.query_engine import run_query
from app.analytics.sql_engine import execute_sql
from app.analytics.sql_validator import validate_and_prepare
from app.core.exceptions import ColumnNotFoundError, InvalidQueryError
from app.schemas.dataset_query import Aggregation, DatasetQueryRequest, QueryFilter

_MAX_SAMPLE_ROWS = 15
_ROW_LIMIT = 10_000

# Common bounded-semantics columns, matched by substring in the column
# name — deliberately small and generic (not tied to any one dataset's
# schema). Only used to flag genuinely implausible values (e.g. a rating
# of -1, an age of 200) as logical_violation candidates; the LLM still
# decides how to phrase/classify the finding, but the detection itself is
# deterministic, never invented.
_RANGE_RULES: dict[str, tuple[float, float]] = {
    "rating": (1, 5),
    "age": (0, 120),
    "percent": (0, 100),
    "pct": (0, 100),
    "score": (0, 100),
    "probability": (0, 1),
}


def _row_sample(df: pl.DataFrame, limit: int = _MAX_SAMPLE_ROWS) -> list[dict[str, Any]]:
    return df.head(limit).to_dicts()


def _require_column(df: pl.DataFrame, column: str) -> None:
    if column not in df.columns:
        raise ColumnNotFoundError(column)


# ---------------------------------------------------------------- tools ----


def get_dataset_profile(df: pl.DataFrame) -> dict[str, Any]:
    return build_data_profile(df).to_dict()


def get_column_statistics(df: pl.DataFrame, column: str) -> dict[str, Any]:
    _require_column(df, column)
    profile = build_data_profile(df)
    return {"column": column, **profile.columns[column]}


def get_missing_values(df: pl.DataFrame) -> dict[str, Any]:
    profile = build_data_profile(df)
    missing = {
        name: {"missing_count": info["missing_count"], "missing_pct": info["missing_pct"]}
        for name, info in profile.columns.items()
        if info["missing_count"] > 0
    }
    return {"row_count": df.height, "columns_with_missing_values": missing}


def get_duplicates(df: pl.DataFrame, column: str | None = None) -> dict[str, Any]:
    if column is not None:
        _require_column(df, column)
        col = df[column].drop_nulls()
        dup_count = col.len() - col.n_unique() if col.len() else 0
        value_counts = col.value_counts(sort=True)
        dup_values = value_counts.filter(pl.col("count") > 1).head(_MAX_SAMPLE_ROWS).to_dicts()
        duplicated_values = col.filter(col.is_duplicated())
        sample_rows = (
            df.filter(pl.col(column).is_in(duplicated_values)).head(_MAX_SAMPLE_ROWS).to_dicts()
        )
        return {
            "column": column,
            "duplicate_value_count": dup_count,
            "duplicate_values": dup_values,
            "sample_duplicate_rows": sample_rows,
        }
    profile = build_data_profile(df)
    return profile.duplicates


def get_unique_values(df: pl.DataFrame, column: str, limit: int = 20) -> dict[str, Any]:
    _require_column(df, column)
    values = df[column].drop_nulls().unique().to_list()
    return {
        "column": column,
        "unique_count": len(values),
        "values": values[:limit],
        "truncated": len(values) > limit,
    }


def group_by_aggregate(
    df: pl.DataFrame, group_by: list[str], column: str | None, op: str
) -> dict[str, Any]:
    aggregations = [Aggregation(op=op, column=column, alias="value")]  # type: ignore[arg-type]
    request = DatasetQueryRequest(
        group_by=group_by, aggregations=aggregations, sort_by="value", sort_desc=True
    )
    try:
        result = run_query(df, request, row_limit=_ROW_LIMIT)
    except (ColumnNotFoundError, InvalidQueryError) as exc:
        return {"error": str(exc)}
    return {"columns": result.columns, "rows": result.rows, "row_count": result.row_count}


def filter_rows(
    df: pl.DataFrame, column: str, op: str, value: object, limit: int = 20
) -> dict[str, Any]:
    query_filter = QueryFilter(column=column, op=op, value=value)  # type: ignore[arg-type]
    request = DatasetQueryRequest(filters=[query_filter], limit=limit)
    try:
        result = run_query(df, request, row_limit=_ROW_LIMIT)
    except (ColumnNotFoundError, InvalidQueryError) as exc:
        return {"error": str(exc)}
    return {
        "matched_row_count": result.row_count,
        "total_row_count": df.height,
        "columns": result.columns,
        "sample_rows": result.rows[:limit],
    }


def detect_outliers(df: pl.DataFrame, column: str, method: str = "iqr") -> dict[str, Any]:
    _require_column(df, column)
    profile = build_data_profile(df)
    col_info = profile.columns.get(column, {})
    if col_info.get("dtype") != "numeric":
        return {"error": f"'{column}' is not numeric; outlier detection needs a numeric column."}
    outlier_info = profile.outliers.get(column)
    if outlier_info is None:
        return {"column": column, "method": method, "count": 0, "pct": 0.0, "sample_rows": []}
    lower, upper = outlier_info["lower_bound"], outlier_info["upper_bound"]
    sample = df.filter((pl.col(column) < lower) | (pl.col(column) > upper)).head(_MAX_SAMPLE_ROWS)
    return {"column": column, **outlier_info, "sample_rows": sample.to_dicts()}


def detect_logical_violations(df: pl.DataFrame) -> dict[str, Any]:
    """Deterministic, rule-based — never an LLM guess about what's
    'plausible'. Only fires for columns whose name matches a small,
    generic set of bounded-semantics hints (see _RANGE_RULES)."""
    violations: dict[str, Any] = {}
    for name, dtype in df.schema.items():
        if dtype not in (pl.Int64, pl.Int32, pl.Float64, pl.Float32):
            continue
        rule = next((bounds for hint, bounds in _RANGE_RULES.items() if hint in name.lower()), None)
        if rule is None:
            continue
        low, high = rule
        mask = (pl.col(name) < low) | (pl.col(name) > high)
        matched = df.filter(mask)
        if matched.height > 0:
            violations[name] = {
                "rule": f"expected between {low} and {high}",
                "violation_count": matched.height,
                "violation_pct": round(matched.height / df.height * 100, 2),
                "sample_rows": matched.head(_MAX_SAMPLE_ROWS).to_dicts(),
            }
    return {"violations": violations}


def detect_anomalies(df: pl.DataFrame) -> dict[str, Any]:
    """A combined signal summary — outliers + logical violations +
    duplicates + missing data — for open-ended "find anomalies"
    questions. Every number here is one of the other deterministic tools'
    output, just gathered in one place."""
    profile = build_data_profile(df)
    logical = detect_logical_violations(df)
    return {
        "outliers": profile.outliers,
        "logical_violations": logical["violations"],
        "duplicates": profile.duplicates,
        "columns_with_missing_values": {
            name: info["missing_count"]
            for name, info in profile.columns.items()
            if info["missing_count"] > 0
        },
    }


def calculate_correlation(df: pl.DataFrame, column_a: str, column_b: str) -> dict[str, Any]:
    _require_column(df, column_a)
    _require_column(df, column_b)
    value = df.select(pl.corr(column_a, column_b)).item()
    sample = df.select([column_a, column_b]).drop_nulls().head(_MAX_SAMPLE_ROWS).to_dicts()
    return {
        "column_a": column_a,
        "column_b": column_b,
        "correlation": round(value, 4) if value is not None else None,
        "sample_points": sample,
    }


def time_series_analysis(
    df: pl.DataFrame, date_column: str, metric_column: str, freq: str = "day"
) -> dict[str, Any]:
    _require_column(df, date_column)
    _require_column(df, metric_column)
    truncate_unit = {"day": "1d", "week": "1w", "month": "1mo"}.get(freq, "1d")
    parsed = df.with_columns(
        pl.col(date_column).cast(pl.Utf8, strict=False).str.to_date(strict=False).alias("__period")
    ).drop_nulls("__period")
    if parsed.height == 0:
        return {"error": f"Could not parse '{date_column}' as dates."}
    series = (
        parsed.with_columns(pl.col("__period").dt.truncate(truncate_unit).alias("__bucket"))
        .group_by("__bucket")
        .agg(pl.col(metric_column).cast(pl.Float64, strict=False).sum().alias("value"))
        .sort("__bucket")
    )
    rows = [{"period": str(r["__bucket"]), "value": r["value"]} for r in series.to_dicts()]
    trend = None
    if len(rows) >= 2 and rows[0]["value"]:
        pct_change = (rows[-1]["value"] - rows[0]["value"]) / abs(rows[0]["value"]) * 100
        trend = {
            "direction": "increase" if pct_change > 0 else "decrease",
            "pct_change": round(pct_change, 2),
        }
    return {
        "date_column": date_column,
        "metric_column": metric_column,
        "freq": freq,
        "series": rows,
        "trend": trend,
    }


def compare_groups(
    df: pl.DataFrame, group_column: str, metric_column: str, op: str = "avg"
) -> dict[str, Any]:
    _require_column(df, group_column)
    _require_column(df, metric_column)
    request = DatasetQueryRequest(
        group_by=[group_column],
        aggregations=[Aggregation(op=op, column=metric_column, alias="value")],  # type: ignore[arg-type]
        sort_by="value",
        sort_desc=True,
    )
    result = run_query(df, request, row_limit=_ROW_LIMIT)
    overall = df.select(pl.col(metric_column).cast(pl.Float64, strict=False)).to_series()
    overall_by_op = {
        "sum": overall.sum(),
        "avg": overall.mean(),
        "min": overall.min(),
        "max": overall.max(),
    }
    overall_value = overall_by_op.get(op)
    return {
        "group_column": group_column,
        "metric_column": metric_column,
        "op": op,
        "groups": [{"group": row[0], "value": row[1]} for row in result.rows],
        "overall": overall_value,
    }


def validate_formula(
    df: pl.DataFrame, target_column: str, formula: str, tolerance_pct: float = 1.0
) -> dict[str, Any]:
    """Checks target_column against an arithmetic expression over other
    real columns (e.g. "units * unit_price * (1 - discount_pct / 100)")
    — reuses the exact same SQL validation + DuckDB execution pipeline
    the SQL Explorer and Natural Language to SQL paths use, so this is
    just as safe against a malformed/malicious formula string as any
    other AI-generated SQL in this app."""
    _require_column(df, target_column)
    known_columns = set(df.columns) | {"__expected", "__diff", "__pct_diff"}
    sql = (
        f'SELECT *, ({formula}) AS __expected, '
        f'("{target_column}" - ({formula})) AS __diff, '
        f'CASE WHEN ({formula}) = 0 THEN NULL '
        f'ELSE ABS(("{target_column}" - ({formula})) / ({formula})) * 100 END AS __pct_diff '
        f"FROM dataset"
    )
    try:
        safe_sql = validate_and_prepare(
            sql, table_name="dataset", allowed_columns=known_columns, row_limit=_ROW_LIMIT
        )
        result = execute_sql(df, safe_sql)
    except InvalidQueryError as exc:
        return {"error": f"Could not validate that formula: {exc}"}

    pct_idx = result.columns.index("__pct_diff")
    mismatches: list[dict[str, Any]] = [
        dict(zip(result.columns, row, strict=True))
        for row in result.rows
        if row[pct_idx] is not None and abs(row[pct_idx]) > tolerance_pct  # type: ignore[arg-type]
    ]
    return {
        "target_column": target_column,
        "formula": formula,
        "tolerance_pct": tolerance_pct,
        "total_rows": df.height,
        "mismatched_rows": len(mismatches),
        "mismatched_pct": round(len(mismatches) / df.height * 100, 2) if df.height else 0.0,
        "sample_mismatches": sorted(
            mismatches, key=lambda r: abs(r["__diff"] or 0), reverse=True
        )[:_MAX_SAMPLE_ROWS],
    }


def get_top_records(df: pl.DataFrame, column: str, n: int = 10) -> dict[str, Any]:
    _require_column(df, column)
    return {"column": column, "n": n, "rows": df.sort(column, descending=True).head(n).to_dicts()}


def get_bottom_records(df: pl.DataFrame, column: str, n: int = 10) -> dict[str, Any]:
    _require_column(df, column)
    return {"column": column, "n": n, "rows": df.sort(column, descending=False).head(n).to_dicts()}
