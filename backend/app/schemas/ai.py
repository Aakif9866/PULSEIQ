from pydantic import BaseModel, Field

from app.schemas.dataset_query import DatasetQueryRequest, DatasetQueryResult


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


class AskResponse(BaseModel):
    question: str
    answer: str
    query: DatasetQueryRequest
    result: DatasetQueryResult
