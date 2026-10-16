import uuid

from sqlalchemy.orm import Session

from app.core.exceptions import DatasetNotFoundError, InsightNotFoundError
from app.models.insight import Insight
from app.repositories.dataset_repository import DatasetRepository
from app.repositories.insight_repository import InsightRepository
from app.schemas.analysis import Finding
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
            query_request=payload.query.model_dump() if payload.query else None,
            row_count=payload.row_count,
            findings=[f.model_dump() for f in payload.findings] or None,
        )
        return _to_read(insight, dataset.original_filename)

    def list_for_owner(self, owner_id: uuid.UUID) -> list[InsightRead]:
        return [
            _to_read(insight, dataset_filename)
            for insight, dataset_filename in self._repo.list_for_owner(owner_id)
        ]

    def delete_owned(self, insight_id: uuid.UUID, owner_id: uuid.UUID) -> None:
        insight = self._repo.get_owned(insight_id, owner_id)
        if insight is None:
            raise InsightNotFoundError(insight_id)
        self._repo.delete(insight)


def _to_read(insight: Insight, dataset_filename: str) -> InsightRead:
    return InsightRead(
        id=insight.id,
        dataset_id=insight.dataset_id,
        dataset_filename=dataset_filename,
        question=insight.question,
        answer=insight.answer,
        query_request=(
            DatasetQueryRequest.model_validate(insight.query_request)
            if insight.query_request is not None
            else None
        ),
        row_count=insight.row_count,
        findings=[Finding.model_validate(f) for f in insight.findings or []],
        created_at=insight.created_at,
    )
