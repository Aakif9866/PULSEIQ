import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.dataset import Dataset


class DatasetRepository:
    """Data-access layer for datasets. Keeps ORM/session details out of services."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def create(
        self,
        *,
        owner_id: uuid.UUID,
        original_filename: str,
        content_type: str,
        size_bytes: int,
        storage_key: str,
    ) -> Dataset:
        dataset = Dataset(
            owner_id=owner_id,
            original_filename=original_filename,
            content_type=content_type,
            size_bytes=size_bytes,
            storage_key=storage_key,
        )
        self._db.add(dataset)
        self._db.commit()
        self._db.refresh(dataset)
        return dataset

    def get_owned(self, dataset_id: uuid.UUID, owner_id: uuid.UUID) -> Dataset | None:
        stmt = select(Dataset).where(Dataset.id == dataset_id, Dataset.owner_id == owner_id)
        return self._db.execute(stmt).scalar_one_or_none()

    def list_for_owner(self, owner_id: uuid.UUID) -> list[Dataset]:
        stmt = (
            select(Dataset).where(Dataset.owner_id == owner_id).order_by(Dataset.created_at.desc())
        )
        return list(self._db.execute(stmt).scalars())

    def mark_profiled(
        self,
        dataset: Dataset,
        *,
        row_count: int,
        column_count: int,
        columns_profile: list[dict[str, Any]],
    ) -> Dataset:
        dataset.row_count = row_count
        dataset.column_count = column_count
        dataset.columns_profile = columns_profile
        dataset.status = "profiled"
        self._db.add(dataset)
        self._db.commit()
        self._db.refresh(dataset)
        return dataset

    def mark_profiling_failed(self, dataset: Dataset) -> Dataset:
        dataset.status = "profiling_failed"
        self._db.add(dataset)
        self._db.commit()
        self._db.refresh(dataset)
        return dataset

    def delete(self, dataset: Dataset) -> None:
        self._db.delete(dataset)
        self._db.commit()
