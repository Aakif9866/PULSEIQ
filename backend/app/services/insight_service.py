import uuid

from sqlalchemy.orm import Session

from app.core.exceptions import DatasetNotFoundError, InsightNotFoundError
from app.repositories.dataset_repository import DatasetRepository
from app.repositories.insight_repository import InsightRepository
from app.schemas.dataset_query import DatasetQueryRequest
from app.schemas.insight import InsightCreate, InsightRead


class InsightService:
    def __init__(self, db: Session) -> None:
        self._repo = InsightRepository(db)
        self._datasets = DatasetRepository(db)

    def save(self, owner_id: uuid.UUID, payload: InsightCreate) -> InsightRead:
        # dataset_id is client-supplied (round-tripped from an /ask response),
        # so re-verify ownership rather than trusting it.
        dataset = self._datasets.get_owned(payload.dataset_id, owner_id)
        if dataset is None:
            raise DatasetNotFoundError(payload.dataset_id)

        insight = self._repo.create(
            owner_id=owner_id,
            dataset_id=payload.dataset_id,
            question=payload.question,
            answer=payload.answer,
            query_request=payload.query.model_dump(),
            row_count=payload.row_count,
        )
        return InsightRead(
            id=insight.id,
            dataset_id=insight.dataset_id,
            dataset_filename=dataset.original_filename,
            question=insight.question,
            answer=insight.answer,
            query_request=payload.query,
            row_count=insight.row_count,
            created_at=insight.created_at,
        )

    def list_for_owner(self, owner_id: uuid.UUID) -> list[InsightRead]:
        return [
            InsightRead(
                id=insight.id,
                dataset_id=insight.dataset_id,
                dataset_filename=dataset_filename,
                question=insight.question,
                answer=insight.answer,
                query_request=DatasetQueryRequest.model_validate(insight.query_request),
                row_count=insight.row_count,
                created_at=insight.created_at,
            )
            for insight, dataset_filename in self._repo.list_for_owner(owner_id)
        ]

    def delete_owned(self, insight_id: uuid.UUID, owner_id: uuid.UUID) -> None:
        insight = self._repo.get_owned(insight_id, owner_id)
        if insight is None:
            raise InsightNotFoundError(insight_id)
        self._repo.delete(insight)
