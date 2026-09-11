import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class Monitor(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A user-configured 'watch this metric' definition. Evaluated either
    on demand (POST /monitors/{id}/run) or by the periodic scheduler
    (app/workers/anomaly_runner.py) — see docs/V2_ARCHITECTURE.md for why
    there's no background-worker process, only a CLI entrypoint meant to be
    invoked externally (e.g. Railway's native cron-scheduled service)."""

    __tablename__ = "monitors"

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
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    metric_column: Mapped[str] = mapped_column(String(255), nullable=False)
    # "sum" | "avg" | "min" | "max" | "count" — same vocabulary as
    # app.schemas.dataset_query.AggregationOp, stored as a plain string the
    # same way DashboardChart.chart_type already is.
    aggregation: Mapped[str] = mapped_column(String(16), nullable=False)
    time_column: Mapped[str] = mapped_column(String(255), nullable=False)

    # "previous_period" | "moving_average" | "zscore"
    baseline_strategy: Mapped[str] = mapped_column(String(32), nullable=False)
    # Periods of history the baseline is computed over. Unused by
    # "previous_period" (always exactly one prior period).
    baseline_window: Mapped[int] = mapped_column(Integer, nullable=False, default=7)
    # Used by "previous_period" and "moving_average".
    threshold_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Used by "zscore".
    zscore_threshold: Mapped[float | None] = mapped_column(Float, nullable=True)

    # "hourly" | "daily" | "manual" — informational, and used by the
    # scheduler to throttle re-checks against last_checked_at. "manual"
    # monitors are never picked up by run_due_monitors(), only by an
    # explicit POST /monitors/{id}/run.
    check_frequency: Mapped[str] = mapped_column(String(16), nullable=False, default="daily")

    notify_email: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Mirrors the MonitorStatus values the detection engine returns
    # (NO_ANOMALY / ANOMALY_DETECTED / INSUFFICIENT_DATA / ERROR) — the
    # monitor's own last-check outcome, independent of whether that
    # outcome was ever persisted as an Anomaly row (only actual detected
    # anomalies get their own row — see Anomaly below).
    last_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - debug aid only
        return f"Monitor(id={self.id}, name={self.name!r})"


class Anomaly(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One detected anomaly event. Only ANOMALY_DETECTED outcomes get a row
    here — a routine NO_ANOMALY/INSUFFICIENT_DATA/ERROR check only updates
    Monitor.last_status, keeping this table a clean, browsable history of
    events that actually mattered (see docs/V2_DATABASE_PLAN.md)."""

    __tablename__ = "anomalies"

    monitor_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("monitors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Denormalized (also reachable via monitor_id -> Monitor.owner_id /
    # dataset_id) so every ownership check is a direct, single-table filter
    # — the same convention DashboardChart already follows for dataset_id.
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

    metric_column: Mapped[str] = mapped_column(String(255), nullable=False)
    # Human-readable label for the time bucket that triggered the anomaly
    # (e.g. "2026-09-11") — distinct from created_at (TimestampMixin),
    # which is when the check ran, not the data period it evaluated.
    period_label: Mapped[str] = mapped_column(String(64), nullable=False)

    observed_value: Mapped[float] = mapped_column(Float, nullable=False)
    baseline_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    change_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    # "increase" | "decrease"
    direction: Mapped[str] = mapped_column(String(16), nullable=False)
    # "percentage_change" | "moving_average" | "zscore"
    detection_method: Mapped[str] = mapped_column(String(32), nullable=False)
    # "low" | "medium" | "high"
    severity: Mapped[str] = mapped_column(String(16), nullable=False)

    # AI-generated (Groq). Nullable: an AI failure must never block
    # persisting the deterministic anomaly itself — see
    # app/services/monitor_service.py.
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)

    alert_sent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    alert_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Set when an alert was attempted but failed (or email wasn't
    # configured) — never blocks or rolls back this row.
    alert_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - debug aid only
        return f"Anomaly(id={self.id}, metric_column={self.metric_column!r})"
