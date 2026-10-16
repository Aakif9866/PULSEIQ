import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.dataset_version import DatasetVersion


class DatasetVersionRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def create(self, **fields: Any) -> DatasetVersion:
        row = DatasetVersion(**fields)
        self._db.add(row)
        self._db.commit()
        self._db.refresh(row)
        return row

    def list_for_dataset(self, dataset_id: uuid.UUID) -> list[DatasetVersion]:
        """Newest first."""
        stmt = (
            select(DatasetVersion)
            .where(DatasetVersion.dataset_id == dataset_id)
            .order_by(DatasetVersion.version.desc())
        )
        return list(self._db.execute(stmt).scalars())

    def clear_file(self, row: DatasetVersion) -> None:
        row.storage_key = None
        self._db.commit()
