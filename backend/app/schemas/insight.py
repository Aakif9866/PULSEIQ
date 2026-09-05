from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.schemas.dataset_query import DatasetQueryRequest


class InsightCreate(BaseModel):
    dataset_id: UUID
    question: str
    answer: str
    query: DatasetQueryRequest
    row_count: int


class InsightRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    dataset_id: UUID
    dataset_filename: str
    question: str
    answer: str
    query_request: DatasetQueryRequest
    row_count: int
    created_at: datetime
