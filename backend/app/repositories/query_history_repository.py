import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.history import QueryHistory


class QueryHistoryRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def create(
        self,
        *,
        owner_id: uuid.UUID,
        dataset_id: uuid.UUID,
        question: str | None,
        sql_text: str | None,
        result_meta: dict[str, Any],
        source: str,
    ) -> QueryHistory:
        entry = QueryHistory(
            owner_id=owner_id,
            dataset_id=dataset_id,
            question=question,
            sql_text=sql_text,
            result_meta=result_meta,
            source=source,
        )
        self._db.add(entry)
        self._db.commit()
        self._db.refresh(entry)
        return entry

    def list_for_owner(
        self, owner_id: uuid.UUID, *, dataset_id: uuid.UUID | None = None, limit: int = 100
    ) -> list[QueryHistory]:
        stmt = select(QueryHistory).where(QueryHistory.owner_id == owner_id)
        if dataset_id is not None:
            stmt = stmt.where(QueryHistory.dataset_id == dataset_id)
        stmt = stmt.order_by(QueryHistory.created_at.desc()).limit(limit)
        return list(self._db.execute(stmt).scalars().all())
