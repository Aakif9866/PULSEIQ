import uuid
from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class AiUsageLog(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One row per AI request that reached the model (or was served from
    the answer cache) — the persisted record behind per-user daily token
    quotas and the usage page (docs/PHASES.md Phase 8 step 4). Tokens are
    Groq's own reported numbers, never estimated; cost is null unless the
    operator configured real per-token pricing (see
    app/ai/providers/usage_tracking.py)."""

    __tablename__ = "ai_usage_log"

    owner_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    # SET NULL on dataset delete — see migration 0009: deleting a dataset
    # must never erase tokens already spent against the owner's quota.
    dataset_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("datasets.id", ondelete="SET NULL"),
        nullable=True,
    )
    # "ai_deep_analysis" today — the only path that reports real token
    # usage (see app/services/usage_service.py for why /ask and /ask-sql
    # don't yet).
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    cache_hit: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    llm_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)
