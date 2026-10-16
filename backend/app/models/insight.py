import uuid
from typing import Any

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class Insight(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A user-saved question + AI-generated answer about one of their
    datasets. When the answer came from one structured query, it's kept
    alongside so the insight stays reproducible. Answers from the /analyze
    engine (several tool calls, or none) have no single query; they keep
    their verified findings instead."""

    __tablename__ = "insights"

    owner_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("datasets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    # Which dataset version the answer was computed on, so a result is never
    # silently presented as current after the dataset is refreshed.
    dataset_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # User-editable; None means "show the question" (insights before 0012).
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    # The DatasetQueryRequest that was run to ground the answer, if one was.
    query_request: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # /analyze findings (claim, value, verified, ...) as returned to the user.
    findings: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)
    # The computations behind the answer (tool, arguments, result), so a
    # saved insight can be reopened and reported with its real evidence.
    tool_calls: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - debug aid only
        return f"Insight(id={self.id}, question={self.question!r})"
