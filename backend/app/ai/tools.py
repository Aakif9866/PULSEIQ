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


# ------------------------------------------------- change / contribution ----

_TRUNCATE_UNITS = {"day": "1d", "week": "1w", "month": "1mo", "quarter": "1q", "year": "1y"}
_ADDITIVE_OPS = {"sum", "count"}
_MAX_AUTO_DIMENSIONS = 4
_MAX_DIMENSION_CARDINALITY = 50
_SMALL_GROUP_ROWS = 5
_MAX_CATEGORY_LABEL_CHARS = 30
_CAUSAL_CAVEAT = (
    "Contribution shows where the change happened, not why it happened; "
    "it is not proof of cause."
)


def period_label(period: str, freq: str) -> str:
    """A bucket's start date ("2024-03-01") as people say it for its
    granularity: 2024-03-01 for a day, "week of 2024-03-04", 2024-03 for a
    month, 2024-Q1, 2024. Slicing to the month for everything made two
    consecutive days read as "2024-01 vs 2024-01"."""
    if freq == "day":
        return period[:10]
    if freq == "week":
        return f"week of {period[:10]}"
    if freq == "month":
        return period[:7]
    if freq == "quarter":
        return f"{period[:4]}-Q{(int(period[5:7]) - 1) // 3 + 1}"
    return period[:4]


def _with_period(df: pl.DataFrame, date_column: str, freq: str) -> pl.DataFrame:
    """Adds a __period column (the date truncated to `freq`), dropping rows
    whose date can't be parsed. Accepts real date/datetime columns as-is."""
    col = pl.col(date_column)
    if df.schema[date_column] in (pl.Date, pl.Datetime):
        as_date = col.cast(pl.Date)
    else:
        as_date = col.cast(pl.Utf8, strict=False).str.to_date(strict=False)
    unit = _TRUNCATE_UNITS[freq]
    try:
        return (
            df.with_columns(as_date.alias("__date"))
            .drop_nulls("__date")
            .with_columns(pl.col("__date").dt.truncate(unit).alias("__period"))
        )
    except pl.exceptions.ComputeError:
        # Polars raises (rather than returning nulls) when no date format
        # fits the text at all; callers treat an empty frame as unparsable.
        return df.clear().with_columns(
            pl.lit(None, pl.Date).alias("__date"), pl.lit(None, pl.Date).alias("__period")
        )


def _metric_expr(op: str, metric_column: str | None) -> pl.Expr:
    if op == "count":
        return pl.len().cast(pl.Float64).alias("value")
    value = pl.col(metric_column).cast(pl.Float64, strict=False)
    return {"sum": value.sum(), "avg": value.mean()}[op].alias("value")


def _mean_nonblank_length(series: pl.Series) -> float:
    """Average length of the non-empty values: a mostly blank notes column
    is still free text."""
    lengths = series.drop_nulls().str.strip_chars().str.len_chars()
    return lengths.filter(lengths > 0).mean() or 0.0


def _auto_dimensions(df: pl.DataFrame, exclude: set[str]) -> list[str]:
    """Low-cardinality text/boolean columns: the ones a change can
    meaningfully be broken down by. IDs and free text (too many distinct
    values) and numbers are never chosen."""
    candidates: list[tuple[bool, int, str]] = []
    for name, dtype in df.schema.items():
        if name in exclude or name.startswith("__"):
            continue
        if dtype not in (pl.Utf8, pl.Categorical, pl.Boolean):
            continue
        distinct = df.get_column(name).n_unique()
        # More than half the rows having their own value means an ID or
        # free text, even when the dataset is small enough to stay under
        # the cardinality cap.
        looks_like_id = distinct > df.height / 2
        # Sentences (notes, comments, descriptions) are free text, not
        # categories: never a dimension, and never echoed back to the model
        # as a "segment" (they can carry instructions planted in the data).
        free_text = dtype == pl.Utf8 and (
            _mean_nonblank_length(df.get_column(name)) > _MAX_CATEGORY_LABEL_CHARS
        )
        if 2 <= distinct <= _MAX_DIMENSION_CARDINALITY and not looks_like_id and not free_text:
            named_like_id = name.lower() == "id" or name.lower().endswith(("_id", "id"))
            # Segment-like columns (few values) first; ID-named ones last.
            candidates.append((named_like_id, distinct, name))
    return [name for *_, name in sorted(candidates)[:_MAX_AUTO_DIMENSIONS]]


def _resolve_period(label: str | None, available: list[str], default: str) -> str | None:
    """Matches a user-supplied period ("2024-03", "2024-03-01", "2024") to
    a bucket by prefix; None when nothing matches (never a guess)."""
    if label is None:
        return default
    matches = [p for p in available if p.startswith(str(label).strip())]
    return matches[0] if len(matches) == 1 else None


def _round(value: float | None) -> float | None:
    return None if value is None else round(value, 2)


def explain_change(
    df: pl.DataFrame,
    date_column: str,
    metric_column: str | None = None,
    op: str = "sum",
    freq: str = "month",
    current_period: str | None = None,
    previous_period: str | None = None,
    dimensions: list[str] | None = None,
    top_n: int = 5,
) -> dict[str, Any]:
    """How a metric changed between two periods, and which segments of
    which dimensions account for that change (contribution analysis).

    For additive metrics (sum, count) each segment's share of the total
    change is reported; shares of offsetting segments can exceed 100% or
    be negative, which is mathematically correct, not an error. Averages
    aren't additive, so for "avg" only per-segment changes are reported."""
    _require_column(df, date_column)
    if op not in ("sum", "count", "avg"):
        return {"error": "op must be one of: sum, count, avg."}
    if op != "count":
        if not metric_column:
            return {"error": f"metric_column is required for op '{op}'."}
        _require_column(df, metric_column)
    if freq not in _TRUNCATE_UNITS:
        return {"error": f"freq must be one of: {', '.join(_TRUNCATE_UNITS)}."}
    top_n = max(1, min(int(top_n), 10))

    data = _with_period(df, date_column, freq)
    if data.height == 0:
        return {"error": f"Could not parse '{date_column}' as dates."}
    periods = [str(p) for p in data.get_column("__period").unique().sort().to_list()]
    if len(periods) < 2:
        return {
            "error": f"Need at least two {freq}s of data to compare; found {len(periods)}.",
            "available_periods": periods,
        }

    current = _resolve_period(current_period, periods, periods[-1])
    if current is None:
        return {
            "error": f"No single {freq} matches '{current_period}'.",
            "available_periods": periods[-24:],
        }
    before = [p for p in periods if p < current]
    default_previous = before[-1] if before else None
    previous = (
        _resolve_period(previous_period, periods, default_previous)
        if default_previous or previous_period
        else None
    )
    if previous is None or previous >= current:
        return {
            "error": "Could not establish a valid earlier period to compare against.",
            "available_periods": periods[-24:],
        }

    def total(period: str) -> tuple[float | None, int]:
        rows = data.filter(pl.col("__period").cast(pl.Utf8) == period)
        return rows.select(_metric_expr(op, metric_column)).item(), rows.height

    prev_value, prev_rows = total(previous)
    cur_value, cur_rows = total(current)
    prev_value = prev_value or 0.0
    cur_value = cur_value or 0.0
    change = cur_value - prev_value
    pct = None if prev_value == 0 else change / abs(prev_value) * 100

    caveats = [_CAUSAL_CAVEAT]
    if prev_value == 0:
        caveats.append("The earlier period's value is zero, so a percentage change is undefined.")
    if metric_column and op == "sum":
        series = df.get_column(metric_column).cast(pl.Float64, strict=False)
        if (series < 0).any():
            caveats.append(
                "The metric has negative values, so segments can offset each other; "
                "read shares together with the absolute changes."
            )
    if op not in _ADDITIVE_OPS:
        caveats.append(
            "Averages are not additive: segment changes are shown, but not as shares of the total."
        )
    if op == "sum" and metric_column:
        for label, period, period_total in (
            ("earlier", previous, prev_value), ("later", current, cur_value)
        ):
            values = data.filter(pl.col("__period").cast(pl.Utf8) == period).get_column(
                metric_column
            ).cast(pl.Float64, strict=False)
            biggest = values.max()
            # With 1-2 rows one of them is always >= 50%: not a signal.
            if period_total and biggest is not None and values.len() >= 3:
                share = biggest / period_total * 100
                if share >= 50:
                    caveats.append(
                        f"A single row makes up {share:.0f}% of the {label} period's total "
                        f"({biggest:,.2f}); the change may reflect one outlier, not a trend."
                    )
    if current == periods[-1]:
        latest_date = data.get_column("__date").max()
        period_end = data.filter(pl.col("__period").cast(pl.Utf8) == current).select(
            pl.col("__period").first().dt.offset_by(_TRUNCATE_UNITS[freq])
        ).item()
        span_days = (period_end - data.filter(
            pl.col("__period").cast(pl.Utf8) == current
        ).get_column("__period").first()).days
        covered_days = (latest_date - data.filter(
            pl.col("__period").cast(pl.Utf8) == current
        ).get_column("__period").first()).days + 1
        if span_days and covered_days / span_days < 0.6:
            caveats.append(
                f"The latest {freq} may be incomplete: the data ends on {latest_date}, "
                f"{covered_days} of {span_days} days in."
            )

    exclude = {date_column, *([metric_column] if metric_column else [])}
    if dimensions:
        for d in dimensions:
            _require_column(df, d)
        dims = [d for d in dimensions if d not in exclude][:_MAX_AUTO_DIMENSIONS]
    else:
        dims = _auto_dimensions(df, exclude)

    breakdowns = []
    for dim in dims:
        window = data.filter(pl.col("__period").cast(pl.Utf8).is_in([previous, current]))
        grouped = (
            window.group_by(dim, pl.col("__period").cast(pl.Utf8).alias("__p"))
            .agg(_metric_expr(op, metric_column), pl.len().alias("rows"))
        )
        by_segment: dict[Any, dict[str, Any]] = {}
        for row in grouped.to_dicts():
            seg = by_segment.setdefault(row[dim], {"segment": row[dim]})
            key = "current" if row["__p"] == current else "previous"
            seg[key] = row["value"] or 0.0
            seg[f"{key}_rows"] = row["rows"]
        segments = []
        for seg in by_segment.values():
            p, c = seg.get("previous", 0.0), seg.get("current", 0.0)
            pr, cr = seg.get("previous_rows", 0), seg.get("current_rows", 0)
            delta = c - p
            item: dict[str, Any] = {
                "segment": seg["segment"],
                "previous": _round(p),
                "current": _round(c),
                "change": _round(delta),
            }
            if op in _ADDITIVE_OPS and change != 0:
                item["share_of_change_pct"] = _round(delta / change * 100)
            flags = []
            if pr == 0:
                flags.append("new")
            if cr == 0:
                flags.append("dropped")
            if max(pr, cr) < _SMALL_GROUP_ROWS:
                flags.append("small_group")
            if flags:
                item["flags"] = flags
            segments.append(item)
        segments.sort(key=lambda s: abs(s["change"] or 0), reverse=True)
        moved = sum(abs(s["change"] or 0) for s in segments)
        top = segments[0] if segments else None
        breakdowns.append(
            {
                "dimension": dim,
                "segment_count": len(segments),
                # How concentrated the movement is in the single biggest
                # segment: a high value means this dimension "explains"
                # the change well.
                "top_segment_share_of_movement_pct": _round(
                    abs(top["change"]) / moved * 100 if top and moved else None
                ),
                "top_contributors": segments[:top_n],
            }
        )
    breakdowns.sort(key=lambda b: b["top_segment_share_of_movement_pct"] or 0, reverse=True)
    if dims and any(
        "small_group" in s.get("flags", []) for b in breakdowns for s in b["top_contributors"]
    ):
        caveats.append("Some segments have fewer than 5 rows; their changes may be noise.")
    if not dims:
        caveats.append(
            "No suitable dimension (2-50 distinct text values) to break the change down by."
        )

    return {
        "metric": {"column": metric_column, "op": op},
        "date_column": date_column,
        "freq": freq,
        "previous_period": previous,
        "current_period": current,
        "previous_value": _round(prev_value),
        "current_value": _round(cur_value),
        "change": _round(change),
        "pct_change": _round(pct),
        "previous_rows": prev_rows,
        "current_rows": cur_rows,
        "dataset_rows": df.height,
        "breakdowns": breakdowns,
        "caveats": caveats,
    }
