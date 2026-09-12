from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.dataset_query import DatasetQueryResult

QuerySource = Literal["ai_sql", "sql_explorer", "ai_structured", "ai_deep_analysis"]


class RunSqlRequest(BaseModel):
    sql: str = Field(min_length=1, max_length=10_000)


class RunSqlResponse(BaseModel):
    sql: str
    result: DatasetQueryResult


class QueryHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    dataset_id: UUID
    question: str | None
    sql_text: str | None
    source: QuerySource
    row_count: int
    columns: list[str]
    truncated: bool
    created_at: datetime


class SavedQueryCreate(BaseModel):
    dataset_id: UUID
    name: str = Field(min_length=1, max_length=255)
    sql_text: str = Field(min_length=1, max_length=10_000)


class SavedQueryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    dataset_id: UUID
    name: str
    sql_text: str
    created_at: datetime


class SuggestedQuery(BaseModel):
    label: str
    sql: str
