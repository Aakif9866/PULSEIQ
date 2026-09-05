from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.dataset_query import DatasetQueryRequest

ChartType = Literal["bar", "line"]


class DashboardCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class DashboardRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    chart_count: int
    created_at: datetime


class DashboardChartCreate(BaseModel):
    dataset_id: UUID
    title: str = Field(min_length=1, max_length=255)
    chart_type: ChartType
    query: DatasetQueryRequest


class DashboardChartRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    dataset_id: UUID
    dataset_filename: str
    title: str
    chart_type: ChartType
    query_request: DatasetQueryRequest
    position: int
    created_at: datetime


class DashboardDetail(BaseModel):
    id: UUID
    name: str
    created_at: datetime
    charts: list[DashboardChartRead]


class MoveChartRequest(BaseModel):
    direction: Literal["up", "down"]
