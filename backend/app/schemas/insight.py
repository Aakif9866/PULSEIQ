from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.analysis import Finding
from app.schemas.dataset_query import DatasetQueryRequest


class InsightCreate(BaseModel):
    dataset_id: UUID
    question: str = Field(min_length=1, max_length=2000)
    answer: str = Field(min_length=1, max_length=8000)
    # Present for /ask answers (one structured query); absent for /analyze.
    query: DatasetQueryRequest | None = None
    row_count: int | None = None
    findings: list[Finding] = Field(default_factory=list, max_length=50)


class InsightRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    dataset_id: UUID
    dataset_filename: str
    question: str
    answer: str
    query_request: DatasetQueryRequest | None
    row_count: int | None
    findings: list[Finding]
    created_at: datetime
