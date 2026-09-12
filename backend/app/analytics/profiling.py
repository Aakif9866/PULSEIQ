"""Computes the column-level profile shown in the dataset explorer, plus
a lightweight data-quality view (V2 — docs/V2_ROADMAP.md's "Data Profiling
and Data Quality"): missing-value percentage, duplicate rows, numeric
distributions and outliers, categorical top values, pairwise numeric
correlation, and a simple, transparent (not black-box) quality score.
Everything here is plain Polars aggregation — no DuckDB, no AI, no new
dependency.
"""
from dataclasses import dataclass, field
from typing import Any

import polars as pl

_NUMERIC_DTYPES = (pl.Int64, pl.Int32, pl.Float64, pl.Float32)
_MAX_TOP_VALUES = 5
_MAX_CORRELATION_PAIRS = 20  # caps cost on very wide datasets


@dataclass
class DatasetProfile:
    row_count: int
    column_count: int
    columns: list[dict[str, Any]]  # see _profile_column for the per-column shape
    duplicate_row_count: int
    data_quality_score: float  # 0-100, transparent weighted score — see _quality_score
    correlations: list[dict[str, Any]] = field(default_factory=list)


def profile_dataframe(df: pl.DataFrame) -> DatasetProfile:
    null_counts = df.null_count().row(0, named=True)
    duplicate_row_count = int(df.is_duplicated().sum()) if df.height > 0 else 0

    columns = [
        _profile_column(df, name, dtype, null_counts[name]) for name, dtype in df.schema.items()
    ]

    return DatasetProfile(
        row_count=df.height,
        column_count=df.width,
        columns=columns,
        duplicate_row_count=duplicate_row_count,
        data_quality_score=_quality_score(df, null_counts, duplicate_row_count),
        correlations=_pairwise_correlations(df),
    )


def _profile_column(
    df: pl.DataFrame, name: str, dtype: pl.DataType, null_count: int
) -> dict[str, Any]:
    info: dict[str, Any] = {
        "name": name,
        "dtype": str(dtype),
        "null_count": null_count,
        "null_percentage": round(null_count / df.height * 100, 2) if df.height else 0.0,
    }

    non_null = df[name].drop_nulls()
    if non_null.len() == 0:
        return info

    if dtype in _NUMERIC_DTYPES:
        info.update(_numeric_stats(non_null))
    elif dtype == pl.Utf8:
        info["top_values"] = _top_values(non_null)

    return info


def _numeric_stats(series: pl.Series) -> dict[str, Any]:
    stats: dict[str, Any] = {
        "min": series.min(),
        "max": series.max(),
        "mean": round(float(series.mean()), 4),  # type: ignore[arg-type]
    }
    q1, q3 = series.quantile(0.25), series.quantile(0.75)
    if q1 is not None and q3 is not None:
        iqr = q3 - q1
        lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        stats["outlier_count"] = int(((series < lower) | (series > upper)).sum())
    return stats


def _top_values(series: pl.Series) -> list[dict[str, Any]]:
    counts = series.value_counts(sort=True).head(_MAX_TOP_VALUES)
    name = series.name
    return [{"value": row[name], "count": row["count"]} for row in counts.iter_rows(named=True)]


def _pairwise_correlations(df: pl.DataFrame) -> list[dict[str, Any]]:
    numeric_cols = [name for name, dtype in df.schema.items() if dtype in _NUMERIC_DTYPES]
    if len(numeric_cols) < 2 or df.height < 2:
        return []

    pairs: list[dict[str, Any]] = []
    for i, col_a in enumerate(numeric_cols):
        for col_b in numeric_cols[i + 1 :]:
            if len(pairs) >= _MAX_CORRELATION_PAIRS:
                return pairs
            value = df.select(pl.corr(col_a, col_b)).item()
            if value is not None:
                pairs.append({"column_a": col_a, "column_b": col_b, "correlation": round(value, 4)})
    return pairs


def _quality_score(
    df: pl.DataFrame, null_counts: dict[str, int], duplicate_row_count: int
) -> float:
    """A simple, explainable weighted score — deliberately not a fitted or
    black-box model (see docs/V2_ROADMAP.md's reasoning: a portfolio
    project benefits more from a score you can explain in one sentence
    than a more "sophisticated" one you can't)."""
    if df.height == 0 or df.width == 0:
        return 0.0
    total_cells = df.height * df.width
    missing_ratio = sum(null_counts.values()) / total_cells if total_cells else 0.0
    duplicate_ratio = duplicate_row_count / df.height if df.height else 0.0
    score = 100 - (missing_ratio * 50) - (duplicate_ratio * 30)
    return round(max(0.0, min(100.0, score)), 1)
