"""A rich, on-demand data profile computed from the FULL dataset — the
foundation of the hybrid AI Analyst (docs/AI_ANALYTICS.md's redesign):
the LLM is never handed a dataframe preview to reason about directly: it
gets this profile (or the output of a specific tool call) instead, and
every number in it is a real Python/Polars computation, never a guess.

Distinct from app.analytics.profiling.profile_dataframe (which computes a
lighter, persisted per-column profile stored on the Dataset row at upload
time for the dataset explorer UI). This module computes a deeper,
semantic profile on demand — column "kind" (numeric/categorical/datetime/
boolean/text) rather than a raw Polars dtype string, quantiles, duplicate
*key* detection, and temporal ranges — none of which the upload-time
profile stores. Nothing here is dataset-schema-specific: column kind and
"looks like a key/date" are inferred generically from dtype and simple,
broadly-applicable heuristics, not from any fixed (e.g. ecommerce) schema.
"""
import datetime as dt
from dataclasses import dataclass
from typing import Any, Literal, cast

import polars as pl

ColumnKind = Literal["numeric", "categorical", "datetime", "boolean", "text"]

_NUMERIC_DTYPES = (pl.Int64, pl.Int32, pl.Int16, pl.Int8, pl.Float64, pl.Float32)
_MAX_TOP_VALUES = 8
_MAX_CORRELATION_PAIRS = 30
_CATEGORICAL_MAX_UNIQUE_RATIO = 0.5
_CATEGORICAL_MAX_ABSOLUTE_UNIQUE = 20
# A string column is "categorical" if it has few distinct values in
# absolute terms (a "region" column stays categorical even at 10,000 rows)
# OR few relative to row count (works even when absolute cardinality is
# higher but still clearly not free text/an identifier). Otherwise "text".
_KEY_NAME_HINTS = ("id", "code", "number", "no", "key", "ref", "sku")
_DATE_NAME_HINTS = ("date", "time", "day", "month", "year", "week")


@dataclass
class DataProfile:
    row_count: int
    column_count: int
    columns: dict[str, dict[str, Any]]
    duplicates: dict[str, Any]
    outliers: dict[str, dict[str, Any]]
    correlations: list[dict[str, Any]]
    temporal: dict[str, dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset": {"rows": self.row_count, "columns": self.column_count},
            "columns": self.columns,
            "duplicates": self.duplicates,
            "outliers": self.outliers,
            "correlations": self.correlations,
            "temporal": self.temporal,
        }


def classify_column_kind(name: str, dtype: pl.DataType, series: pl.Series) -> ColumnKind:
    if dtype == pl.Boolean:
        return "boolean"
    if dtype in _NUMERIC_DTYPES:
        return "numeric"
    if dtype in (pl.Date, pl.Datetime):
        return "datetime"
    if dtype == pl.Utf8:
        non_null = series.drop_nulls()
        if non_null.len() == 0:
            return "text"
        if _looks_like_date_name(name) and _parses_as_dates(non_null):
            return "datetime"
        unique_count = non_null.n_unique()
        unique_ratio = unique_count / non_null.len()
        is_categorical = (
            unique_count <= _CATEGORICAL_MAX_ABSOLUTE_UNIQUE
            or unique_ratio <= _CATEGORICAL_MAX_UNIQUE_RATIO
        )
        return "categorical" if is_categorical else "text"
    return "text"


def _looks_like_date_name(name: str) -> bool:
    lname = name.lower()
    return any(hint in lname for hint in _DATE_NAME_HINTS)


def _parses_as_dates(series: pl.Series) -> bool:
    try:
        parsed = series.str.to_date(strict=False)
    except Exception:  # noqa: BLE001 - purely a heuristic probe
        return False
    return parsed.null_count() < series.len()  # at least one real date


def _looks_like_key(name: str, dtype: pl.DataType, series: pl.Series) -> bool:
    lname = name.lower()
    if any(hint in lname for hint in _KEY_NAME_HINTS):
        return True
    non_null = series.drop_nulls()
    if dtype == pl.Utf8 and non_null.len() > 0:
        return (non_null.n_unique() / non_null.len()) > 0.9
    return False


def build_data_profile(df: pl.DataFrame) -> DataProfile:
    columns: dict[str, dict[str, Any]] = {}
    outliers: dict[str, dict[str, Any]] = {}
    temporal: dict[str, dict[str, Any]] = {}
    key_columns: list[str] = []

    for name, dtype in df.schema.items():
        series = df[name]
        non_null = series.drop_nulls()
        null_count = series.null_count()
        kind = classify_column_kind(name, dtype, series)

        col_info: dict[str, Any] = {
            "dtype": kind,
            "raw_dtype": str(dtype),
            "missing_count": null_count,
            "missing_pct": round(null_count / df.height * 100, 2) if df.height else 0.0,
            "unique_count": non_null.n_unique() if non_null.len() else 0,
        }

        if kind == "numeric" and non_null.len() > 0:
            numeric = non_null.cast(pl.Float64, strict=False)
            q1, median, q3 = numeric.quantile(0.25), numeric.quantile(0.5), numeric.quantile(0.75)
            col_info.update(
                {
                    "min": numeric.min(),
                    "max": numeric.max(),
                    "mean": round(float(numeric.mean()), 4),  # type: ignore[arg-type]
                    "median": median,
                    "std": round(float(numeric.std()), 4)  # type: ignore[arg-type]
                    if numeric.len() > 1
                    else 0.0,
                    "q1": q1,
                    "q3": q3,
                }
            )
            outlier_info = _iqr_outliers(numeric, q1, q3)
            if outlier_info is not None:
                outliers[name] = outlier_info
        elif kind == "categorical" and non_null.len() > 0:
            col_info["top_values"] = _top_values(non_null)
        elif kind == "datetime":
            dates = non_null.cast(pl.Utf8, strict=False).str.to_date(strict=False).drop_nulls()
            if dates.len() > 0:
                # A Date-dtype series' .min()/.max() are always real
                # datetime.date objects at runtime — cast() tells mypy
                # that directly instead of fighting the stub's broader
                # union type (covering every dtype Polars can hold).
                lo = cast(dt.date, dates.min())
                hi = cast(dt.date, dates.max())
                min_date, max_date = str(lo), str(hi)
                col_info["min_date"] = min_date
                col_info["max_date"] = max_date
                temporal[name] = {
                    "min_date": min_date,
                    "max_date": max_date,
                    "span_days": (hi - lo).days,
                }

        columns[name] = col_info

        if _looks_like_key(name, dtype, series):
            key_columns.append(name)

    return DataProfile(
        row_count=df.height,
        column_count=df.width,
        columns=columns,
        duplicates=_duplicate_summary(df, key_columns),
        outliers=outliers,
        correlations=_pairwise_correlations(df),
        temporal=temporal,
    )


def _iqr_outliers(series: pl.Series, q1: float | None, q3: float | None) -> dict[str, Any] | None:
    if q1 is None or q3 is None:
        return None
    iqr = q3 - q1
    lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    mask = (series < lower) | (series > upper)
    count = int(mask.sum())
    if count == 0:
        return None
    return {
        "method": "iqr",
        "count": count,
        "pct": round(count / series.len() * 100, 2),
        "lower_bound": lower,
        "upper_bound": upper,
    }


def _top_values(series: pl.Series) -> list[dict[str, Any]]:
    counts = series.value_counts(sort=True).head(_MAX_TOP_VALUES)
    name = series.name
    return [{"value": row[name], "count": row["count"]} for row in counts.iter_rows(named=True)]


def _duplicate_summary(df: pl.DataFrame, key_columns: list[str]) -> dict[str, Any]:
    duplicate_row_count = int(df.is_duplicated().sum()) if df.height > 0 else 0
    duplicate_key_counts: dict[str, int] = {}
    for key in key_columns:
        col = df[key].drop_nulls()
        if col.len() == 0:
            continue
        dup_count = col.len() - col.n_unique()
        if dup_count > 0:
            duplicate_key_counts[key] = dup_count
    return {
        "duplicate_rows": duplicate_row_count,
        "duplicate_row_pct": round(duplicate_row_count / df.height * 100, 2) if df.height else 0.0,
        "key_columns_checked": key_columns,
        "duplicate_key_counts": duplicate_key_counts,
    }


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
