import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.dataset import Dataset
from app.models.insight import Insight


class InsightRepository:
    """Data-access layer for insights. Keeps ORM/session details out of services."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def create(
        self,
        *,
        owner_id: uuid.UUID,
        dataset_id: uuid.UUID,
        question: str,
        answer: str,
        query_request: dict[str, Any],
        row_count: int,
    ) -> Insight:
        insight = Insight(
            owner_id=owner_id,
            dataset_id=dataset_id,
            question=question,
            answer=answer,
            query_request=query_request,
            row_count=row_count,
        )
        self._db.add(insight)
        self._db.commit()
        self._db.refresh(insight)
        return insight

    def list_for_owner(self, owner_id: uuid.UUID) -> list[tuple[Insight, str]]:
        """Returns (insight, dataset_filename) pairs, newest first."""
        stmt = (
            select(Insight, Dataset.original_filename)
            .join(Dataset, Dataset.id == Insight.dataset_id)
            .where(Insight.owner_id == owner_id)
            .order_by(Insight.created_at.desc())
        )
        return [(row[0], row[1]) for row in self._db.execute(stmt).all()]

    def get_owned(self, insight_id: uuid.UUID, owner_id: uuid.UUID) -> Insight | None:
        stmt = select(Insight).where(Insight.id == insight_id, Insight.owner_id == owner_id)
        return self._db.execute(stmt).scalar_one_or_none()

    def delete(self, insight: Insight) -> None:
        self._db.delete(insight)
        self._db.commit()
