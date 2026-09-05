from typing import Literal

from pydantic import BaseModel, Field

AggregationOp = Literal["sum", "avg", "min", "max", "count"]
FilterOp = Literal["eq", "ne", "gt", "gte", "lt", "lte", "contains"]

FilterValue = str | float | int | bool


class QueryFilter(BaseModel):
    column: str
    op: FilterOp
    value: FilterValue


class Aggregation(BaseModel):
    op: AggregationOp
    # Not required for "count", which just counts rows per group.
    column: str | None = None
    alias: str | None = None


class DatasetQueryRequest(BaseModel):
    # Empty aggregations = a raw, filtered/sorted table preview.
    # Non-empty = a grouped summary (group_by may still be empty, meaning
    # "aggregate over the whole dataset").
    group_by: list[str] = Field(default_factory=list)
    aggregations: list[Aggregation] = Field(default_factory=list, max_length=10)
    filters: list[QueryFilter] = Field(default_factory=list)
    sort_by: str | None = None
    sort_desc: bool = False
    limit: int | None = Field(default=None, gt=0)


class DatasetQueryResult(BaseModel):
    columns: list[str]
    rows: list[list[object]]
    row_count: int
    truncated: bool
