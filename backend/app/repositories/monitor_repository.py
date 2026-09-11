import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.monitor import Monitor


class MonitorRepository:
    """Data-access layer for monitors. Every read reachable from an API
    route scopes by owner_id — the same convention every other repository
    in this project follows."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def create(
        self,
        *,
        owner_id: uuid.UUID,
        dataset_id: uuid.UUID,
        name: str,
        metric_column: str,
        aggregation: str,
        time_column: str,
        baseline_strategy: str,
        baseline_window: int,
        threshold_percent: float | None,
        zscore_threshold: float | None,
        check_frequency: str,
        notify_email: bool,
    ) -> Monitor:
        monitor = Monitor(
            owner_id=owner_id,
            dataset_id=dataset_id,
            name=name,
            metric_column=metric_column,
            aggregation=aggregation,
            time_column=time_column,
            baseline_strategy=baseline_strategy,
            baseline_window=baseline_window,
            threshold_percent=threshold_percent,
            zscore_threshold=zscore_threshold,
            check_frequency=check_frequency,
            notify_email=notify_email,
        )
        self._db.add(monitor)
        self._db.commit()
        self._db.refresh(monitor)
        return monitor

    def get_owned(self, monitor_id: uuid.UUID, owner_id: uuid.UUID) -> Monitor | None:
        stmt = select(Monitor).where(Monitor.id == monitor_id, Monitor.owner_id == owner_id)
        return self._db.execute(stmt).scalar_one_or_none()

    def list_for_owner(self, owner_id: uuid.UUID) -> list[Monitor]:
        stmt = (
            select(Monitor).where(Monitor.owner_id == owner_id).order_by(Monitor.created_at.desc())
        )
        return list(self._db.execute(stmt).scalars().all())

    def update_fields(self, monitor: Monitor, updates: dict[str, object]) -> Monitor:
        for key, value in updates.items():
            setattr(monitor, key, value)
        self._db.add(monitor)
        self._db.commit()
        self._db.refresh(monitor)
        return monitor

    def delete(self, monitor: Monitor) -> None:
        self._db.delete(monitor)
        self._db.commit()

    def mark_checked(
        self, monitor: Monitor, *, status: str, checked_at: datetime, error: str | None
    ) -> Monitor:
        monitor.last_status = status
        monitor.last_checked_at = checked_at
        monitor.last_error = error
        self._db.add(monitor)
        self._db.commit()
        self._db.refresh(monitor)
        return monitor

    def list_enabled(self) -> list[Monitor]:
        """System-level query with no owner scoping — used only by the
        offline scheduler (app/workers/anomaly_runner.py) via
        MonitorService.run_due_monitors, never by an HTTP route."""
        stmt = select(Monitor).where(
            Monitor.is_enabled.is_(True), Monitor.check_frequency != "manual"
        )
        return list(self._db.execute(stmt).scalars().all())
