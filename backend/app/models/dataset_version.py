import uuid
from typing import Any

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class DatasetVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One uploaded file of a dataset. Every version (including the
    current one, which `datasets` mirrors) gets a row, so history and
    schema changes survive a refresh."""

    __tablename__ = "dataset_versions"
    __table_args__ = (UniqueConstraint("dataset_id", "version"),)

    dataset_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    # Kept so older versions remain on record; their files are pruned
    # beyond settings.MAX_DATASET_VERSIONS_KEPT (storage_key then None).
    storage_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    column_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # [{"name", "dtype"}], so the next version's schema can be compared.
    columns: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)
    # Versus the previous version: added/removed/type_changed columns and
    # the row-count change. None for version 1.
    schema_changes: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
