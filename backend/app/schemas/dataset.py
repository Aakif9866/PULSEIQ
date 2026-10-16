from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class TopValue(BaseModel):
    value: object
    count: int


class ColumnProfile(BaseModel):
    name: str
    dtype: str
    null_count: int
    null_percentage: float = 0.0
    # Numeric columns only.
    min: float | int | None = None
    max: float | int | None = None
    mean: float | None = None
    outlier_count: int | None = None
    # Categorical (string) columns only.
    top_values: list[TopValue] | None = None


class Correlation(BaseModel):
    column_a: str
    column_b: str
    correlation: float


class DatasetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    version: int = 1
    id: UUID
    original_filename: str
    content_type: str
    size_bytes: int
    status: str
    created_at: datetime

    # Populated once profiling completes (status == "profiled"); null while
    # "uploaded" or if it failed ("profiling_failed").
    row_count: int | None = None
    column_count: int | None = None
    columns_profile: list[ColumnProfile] | None = None
    # Data quality (V2) — see app.analytics.profiling.
    duplicate_row_count: int | None = None
    data_quality_score: float | None = None
    correlations: list[Correlation] | None = None


class SchemaChanges(BaseModel):
    previous_version: int
    added: list[str] = []
    removed: list[str] = []
    type_changed: list[dict[str, str]] = []
    row_count_change: int | None = None


class DatasetVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    version: int
    original_filename: str
    size_bytes: int
    row_count: int | None
    column_count: int | None
    schema_changes: SchemaChanges | None
    file_kept: bool
    created_at: datetime


class VersionUploadResult(BaseModel):
    dataset: "DatasetRead"
    version: DatasetVersionRead
    # Anomaly checks on this dataset re-run against the new data.
    checks_run: int
    new_anomalies: int
