"""Deterministic dataset briefing: what's in a dataset and what's worth
asking about it, computed straight from the data (no LLM, no quota).

Every number comes from Polars over the full dataset, or from the
profile already computed at upload; the column roles (date, metric,
dimension, ID) are detected from the real schema and values, never
assumed. Sections that don't apply (no date column, no numeric column)
are simply omitted rather than filled in.
"""

from typing import Any

import polars as pl

from app.ai.tools import _auto_dimensions, _with_period, explain_change, period_label

_MAX_METRICS = 3
_MAX_SERIES_POINTS = 60
_MAX_SEGMENTS = 8
_STRONG_CORRELATION = 0.5
_DATE_PARSE_SAMPLE = 200
# Generic business-metric words, used only to *order* numeric columns
# (a "revenue" column is a likelier headline than "customer_age"); every
# numeric non-ID column is still eligible.
_METRIC_HINTS = (
    "revenue",
    "sales",
    "amount",
    "total",
    "profit",
    "price",
    "cost",
    "value",
    "spend",
    "quantity",
    "units",
    "qty",
)


# Quantities where a total means nothing (adding up prices or ages): these
# are summarized by their average and never used as the headline metric.
_NON_ADDITIVE_HINTS = (
    "price",
    "rate",
    "pct",
    "percent",
    "ratio",
    "age",
    "score",
    "rating",
    "avg",
    "mean",
)


def _is_additive(name: str) -> bool:
    return not any(h in name.lower() for h in _NON_ADDITIVE_HINTS)


def _is_numeric(dtype: pl.DataType) -> bool:
    return dtype.is_numeric() and dtype != pl.Boolean


def _looks_like_id(df: pl.DataFrame, name: str) -> bool:
    lowered = name.lower()
    if lowered == "id" or lowered.endswith(("_id", "id")):
        return True
    # Uniqueness only marks *text* as an ID (order numbers, emails...):
    # continuous numbers like revenue are naturally unique per row.
    if df.schema[name] != pl.Utf8:
        return False
    return df.get_column(name).n_unique() > df.height * 0.9


def _date_columns(df: pl.DataFrame) -> list[str]:
    found = []
    for name, dtype in df.schema.items():
        if dtype in (pl.Date, pl.Datetime):
            found.append(name)
        elif dtype == pl.Utf8:
            sample = df.get_column(name).drop_nulls().head(_DATE_PARSE_SAMPLE)
            if sample.len() == 0:
                continue
            try:
                parsed = sample.str.to_date(strict=False)
            except pl.exceptions.ComputeError:
                continue  # Polars raises when no date format fits at all
            if parsed.null_count() <= sample.len() * 0.1:
                found.append(name)
    return found


def _metric_columns(df: pl.DataFrame) -> list[str]:
    numeric = [n for n, t in df.schema.items() if _is_numeric(t) and not _looks_like_id(df, n)]

    def rank(name: str) -> tuple[int, int]:
        hint = next(
            (i for i, h in enumerate(_METRIC_HINTS) if h in name.lower()), len(_METRIC_HINTS)
        )
        return hint, numeric.index(name)

    return sorted(numeric, key=rank)[:_MAX_METRICS]


def _freq_for(df: pl.DataFrame, date_column: str) -> str:
    dated = _with_period(df, date_column, "day")
    span = (dated.get_column("__date").max() - dated.get_column("__date").min()).days
    return "month" if span >= 180 else "week" if span >= 21 else "day"


def _num(value: Any) -> float | None:
    return None if value is None else round(float(value), 2)


def build_briefing(
    df: pl.DataFrame,
    *,
    columns_profile: list[dict[str, Any]] | None,
    correlations: list[dict[str, Any]] | None,
    duplicate_row_count: int | None,
    data_quality_score: float | None,
) -> dict[str, Any]:
    dates = _date_columns(df)
    metrics = _metric_columns(df)
    ids = [n for n in df.columns if n not in dates and _looks_like_id(df, n)]
    dimensions = _auto_dimensions(df, exclude={*dates, *metrics, *ids})

    briefing: dict[str, Any] = {
        "overview": {
            "rows": df.height,
            "columns": df.width,
            "data_quality_score": data_quality_score,
            "duplicate_rows": duplicate_row_count,
            "date_columns": dates,
            "metric_columns": metrics,
            "dimension_columns": dimensions,
            "id_columns": ids,
        },
        "metrics": [],
        "trend": None,
        "segments": None,
        "quality": [],
        "relationships": [],
        "suggested_questions": [],
    }

    for name in metrics:
        col = df.get_column(name).cast(pl.Float64, strict=False)
        briefing["metrics"].append(
            {
                "column": name,
                "sum": _num(col.sum()),
                "mean": _num(col.mean()),
                "min": _num(col.min()),
                "max": _num(col.max()),
                "null_count": col.null_count(),
                "additive": _is_additive(name),
            }
        )

    # A total-based trend/segment view only makes sense for an additive
    # metric; with none (only prices, ages...), those sections are omitted.
    headline = next((m for m in metrics if _is_additive(m)), None)
    if dates and headline:
        date_col = dates[0]
        freq = _freq_for(df, date_col)
        series = (
            _with_period(df, date_col, freq)
            .group_by("__period")
            .agg(pl.col(headline).cast(pl.Float64, strict=False).sum().alias("value"))
            .sort("__period")
            .tail(_MAX_SERIES_POINTS)
        )
        points = [
            {"period": str(r["__period"]), "value": _num(r["value"])} for r in series.to_dicts()
        ]
        change = explain_change(df, date_col, headline, freq=freq, dimensions=dimensions or None)
        latest: dict[str, Any] | None = None
        if "error" not in change:
            top = next(
                (
                    {"dimension": b["dimension"], **b["top_contributors"][0]}
                    for b in change["breakdowns"]
                    if b["top_contributors"]
                ),
                None,
            )
            latest = {
                "previous_period": change["previous_period"],
                "current_period": change["current_period"],
                "previous_label": period_label(change["previous_period"], freq),
                "current_label": period_label(change["current_period"], freq),
                "previous_value": change["previous_value"],
                "current_value": change["current_value"],
                "change": change["change"],
                "pct_change": change["pct_change"],
                "top_contributor": top,
                "caveats": [c for c in change["caveats"] if "not proof of cause" not in c],
            }
        briefing["trend"] = {
            "metric": headline,
            "date_column": date_col,
            "freq": freq,
            "series": points,
            "latest_change": latest,
        }

    if headline and dimensions:
        dim = dimensions[0]
        grouped = (
            df.group_by(dim)
            .agg(pl.col(headline).cast(pl.Float64, strict=False).sum().alias("value"))
            .sort("value", descending=True, nulls_last=True)
        )
        total = grouped.get_column("value").sum()
        groups = [
            {"group": r[dim], "value": _num(r["value"])}
            for r in grouped.head(_MAX_SEGMENTS).to_dicts()
        ]
        briefing["segments"] = {
            "dimension": dim,
            "metric": headline,
            "op": "sum",
            "groups": groups,
            "top_share_pct": _num(groups[0]["value"] / total * 100) if groups and total else None,
            "group_count": grouped.height,
        }

    for col in columns_profile or []:
        if col.get("null_count"):
            briefing["quality"].append(
                {
                    "kind": "missing",
                    "column": col["name"],
                    "count": col["null_count"],
                    "pct": col.get("null_percentage"),
                }
            )
        if col.get("outlier_count"):
            briefing["quality"].append(
                {"kind": "outliers", "column": col["name"], "count": col["outlier_count"]}
            )
    if duplicate_row_count:
        briefing["quality"].append(
            {"kind": "duplicates", "column": None, "count": duplicate_row_count}
        )
    briefing["quality"].sort(key=lambda q: q["count"], reverse=True)

    strong = [
        c
        for c in correlations or []
        if abs(c.get("correlation") or 0) >= _STRONG_CORRELATION
        and c["column_a"] not in ids
        and c["column_b"] not in ids
    ]
    strong.sort(key=lambda c: abs(c["correlation"]), reverse=True)
    briefing["relationships"] = [
        {**c, "direction": "positive" if c["correlation"] > 0 else "negative"} for c in strong[:3]
    ]

    briefing["suggested_questions"] = _suggest(briefing)
    return briefing


def _suggest(b: dict[str, Any]) -> list[str]:
    """Schema-grounded starting questions: each names real columns and is
    one the analyst's tools can actually answer."""
    out: list[str] = []
    trend, seg = b["trend"], b["segments"]
    if trend and trend["latest_change"]:
        lc = trend["latest_change"]
        out.append(
            f"Why did {trend['metric']} change in {lc['current_label']} compared with "
            f"{lc['previous_label']}?"
        )
    if trend:
        out.append(f"How has {trend['metric']} trended over time by {trend['freq']}?")
    if seg:
        out.append(f"Which {seg['dimension']} has the highest total {seg['metric']}?")
        dims = b["overview"]["dimension_columns"]
        if len(dims) > 1:
            out.append(f"Compare {seg['metric']} across {dims[1]}.")
    if b["quality"]:
        q = b["quality"][0]
        if q["kind"] == "outliers":
            out.append(f"Are the outliers in {q['column']} errors or legitimate values?")
        elif q["kind"] == "missing":
            out.append(f"How much data is missing in {q['column']}, and does it matter?")
        else:
            out.append("Which rows are duplicated, and should they be removed?")
    if b["relationships"]:
        r = b["relationships"][0]
        out.append(f"What is the relationship between {r['column_a']} and {r['column_b']}?")
    if not out:
        out.append("Summarize this dataset and its most important columns.")
    return out[:6]
