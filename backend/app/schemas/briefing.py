from typing import Literal

from pydantic import BaseModel


class BriefingOverview(BaseModel):
    rows: int
    columns: int
    data_quality_score: float | None
    duplicate_rows: int | None
    date_columns: list[str]
    metric_columns: list[str]
    dimension_columns: list[str]
    id_columns: list[str]


class BriefingMetric(BaseModel):
    column: str
    sum: float | None
    mean: float | None
    min: float | None
    max: float | None
    null_count: int
    # False for prices, rates, ages...: summarize by mean, not total.
    additive: bool = True


class SeriesPoint(BaseModel):
    period: str
    value: float | None


class TopContributor(BaseModel):
    dimension: str
    segment: str | int | float | bool | None
    previous: float | None
    current: float | None
    change: float | None
    share_of_change_pct: float | None = None
    flags: list[str] = []


class LatestChange(BaseModel):
    previous_period: str
    current_period: str
    # As people say it for the granularity: "2024-03", "2024-03-05", "2024-Q1".
    previous_label: str
    current_label: str
    previous_value: float | None
    current_value: float | None
    change: float | None
    pct_change: float | None
    top_contributor: TopContributor | None
    caveats: list[str]


class BriefingTrend(BaseModel):
    metric: str
    date_column: str
    freq: str
    series: list[SeriesPoint]
    latest_change: LatestChange | None


class SegmentGroup(BaseModel):
    group: str | int | float | bool | None
    value: float | None


class BriefingSegments(BaseModel):
    dimension: str
    metric: str
    op: Literal["sum"]
    groups: list[SegmentGroup]
    top_share_pct: float | None
    group_count: int


class QualityItem(BaseModel):
    kind: Literal["missing", "outliers", "duplicates"]
    column: str | None
    count: int
    pct: float | None = None


class Relationship(BaseModel):
    column_a: str
    column_b: str
    correlation: float
    direction: Literal["positive", "negative"]


class DatasetBriefing(BaseModel):
    overview: BriefingOverview
    metrics: list[BriefingMetric]
    trend: BriefingTrend | None
    segments: BriefingSegments | None
    quality: list[QualityItem]
    relationships: list[Relationship]
    suggested_questions: list[str]
