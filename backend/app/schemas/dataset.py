from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ColumnProfile(BaseModel):
    name: str
    dtype: str
    null_count: int


class DatasetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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
