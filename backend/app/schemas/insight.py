from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.analysis import Finding, ToolCallRecord
from app.schemas.dataset_query import DatasetQueryRequest


class InsightCreate(BaseModel):
    dataset_id: UUID
    question: str = Field(min_length=1, max_length=2000)
    answer: str = Field(min_length=1, max_length=8000)
    # Present for /ask answers (one structured query); absent for /analyze.
    query: DatasetQueryRequest | None = None
    row_count: int | None = None
    findings: list[Finding] = Field(default_factory=list, max_length=50)
    title: str | None = Field(default=None, max_length=255)
    tool_calls: list[ToolCallRecord] = Field(default_factory=list, max_length=12)


class InsightUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=255)


class InsightRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    dataset_id: UUID
    dataset_filename: str
    title: str
    question: str
    answer: str
    query_request: DatasetQueryRequest | None
    row_count: int | None
    findings: list[Finding]
    tool_calls: list[ToolCallRecord]
    # The version it was computed on vs the dataset's version now: when they
    # differ, the insight is a snapshot of older data (never shown as current).
    dataset_version: int | None
    current_dataset_version: int
    created_at: datetime
