import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.history import SavedQuery


class SavedQueryRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def create(
        self, *, owner_id: uuid.UUID, dataset_id: uuid.UUID, name: str, sql_text: str
    ) -> SavedQuery:
        query = SavedQuery(owner_id=owner_id, dataset_id=dataset_id, name=name, sql_text=sql_text)
        self._db.add(query)
        self._db.commit()
        self._db.refresh(query)
        return query

    def list_for_owner(
        self, owner_id: uuid.UUID, *, dataset_id: uuid.UUID | None = None
    ) -> list[SavedQuery]:
        stmt = select(SavedQuery).where(SavedQuery.owner_id == owner_id)
        if dataset_id is not None:
            stmt = stmt.where(SavedQuery.dataset_id == dataset_id)
        stmt = stmt.order_by(SavedQuery.created_at.desc())
        return list(self._db.execute(stmt).scalars().all())

    def get_owned(self, query_id: uuid.UUID, owner_id: uuid.UUID) -> SavedQuery | None:
        stmt = select(SavedQuery).where(SavedQuery.id == query_id, SavedQuery.owner_id == owner_id)
        return self._db.execute(stmt).scalar_one_or_none()

    def delete(self, query: SavedQuery) -> None:
        self._db.delete(query)
        self._db.commit()
