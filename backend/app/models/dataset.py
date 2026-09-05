import uuid
from typing import Any

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class Dataset(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "datasets"

    owner_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(127), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    # Opaque key into whichever StorageProvider is active (see app/storage) —
    # a filesystem-relative path for "local", an object key for "r2".
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)
    # "uploaded" -> "profiled" | "profiling_failed" once app.analytics has run
    # (synchronously, right after upload — see DatasetService.upload).
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="uploaded")

    # Populated by app.analytics.profiling; null until profiling completes.
    row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    column_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    columns_profile: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - debug aid only
        return f"Dataset(id={self.id}, original_filename={self.original_filename!r})"
