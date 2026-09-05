"""Applies a DatasetQueryRequest to an in-memory DataFrame.

Requests are a small structured shape (group_by/aggregations/filters), never
a raw query string — the frontend builds these from dropdowns, so there's no
user-authored SQL/expression syntax to sandbox against.
"""
import polars as pl

from app.core.exceptions import ColumnNotFoundError, InvalidQueryError
from app.schemas.dataset_query import (
    Aggregation,
    DatasetQueryRequest,
    DatasetQueryResult,
    QueryFilter,
)

_FILTER_OPS = {
    "eq": lambda col, value: col == value,
    "ne": lambda col, value: col != value,
    "gt": lambda col, value: col > value,
    "gte": lambda col, value: col >= value,
    "lt": lambda col, value: col < value,
    "lte": lambda col, value: col <= value,
    "contains": lambda col, value: col.cast(pl.Utf8).str.contains(str(value), literal=True),
}

_AGG_BUILDERS = {
    "sum": lambda col, alias: pl.col(col).sum().alias(alias),
    "avg": lambda col, alias: pl.col(col).mean().alias(alias),
    "min": lambda col, alias: pl.col(col).min().alias(alias),
    "max": lambda col, alias: pl.col(col).max().alias(alias),
}


def _require_columns(df: pl.DataFrame, columns: list[str]) -> None:
    unknown = [c for c in columns if c not in df.columns]
    if unknown:
        raise ColumnNotFoundError(", ".join(unknown))


def _apply_filters(df: pl.DataFrame, filters: list[QueryFilter]) -> pl.DataFrame:
    for f in filters:
        _require_columns(df, [f.column])
        try:
            df = df.filter(_FILTER_OPS[f.op](pl.col(f.column), f.value))
        except pl.exceptions.PolarsError as exc:
            raise InvalidQueryError(f"Filter on '{f.column}' could not be applied: {exc}") from exc
    return df


def _aggregation_alias(agg: Aggregation) -> str:
    if agg.alias:
        return agg.alias
    return "count" if agg.op == "count" else f"{agg.column}_{agg.op}"


def _build_agg_expr(agg: Aggregation) -> pl.Expr:
    alias = _aggregation_alias(agg)
    if agg.op == "count":
        return pl.len().alias(alias)
    if agg.column is None:
        raise InvalidQueryError(f"Aggregation '{agg.op}' requires a column.")
    return _AGG_BUILDERS[agg.op](agg.column, alias)


def run_query(
    df: pl.DataFrame, request: DatasetQueryRequest, *, row_limit: int
) -> DatasetQueryResult:
    if request.group_by and not request.aggregations:
        raise InvalidQueryError("group_by requires at least one aggregation.")

    _require_columns(df, request.group_by)
    for agg in request.aggregations:
        if agg.column is not None:
            _require_columns(df, [agg.column])

    result = _apply_filters(df, request.filters)

    if request.aggregations:
        agg_exprs = [_build_agg_expr(agg) for agg in request.aggregations]
        try:
            result = (
                result.group_by(request.group_by, maintain_order=True).agg(agg_exprs)
                if request.group_by
                else result.select(agg_exprs)
            )
        except pl.exceptions.PolarsError as exc:
            raise InvalidQueryError(f"Could not compute the requested aggregation: {exc}") from exc

    if request.sort_by:
        _require_columns(result, [request.sort_by])
        result = result.sort(request.sort_by, descending=request.sort_desc)

    total_rows = result.height
    effective_limit = min(request.limit, row_limit) if request.limit else row_limit
    result = result.head(effective_limit)

    return DatasetQueryResult(
        columns=result.columns,
        rows=[list(row) for row in result.rows()],
        row_count=result.height,
        truncated=total_rows > effective_limit,
    )
