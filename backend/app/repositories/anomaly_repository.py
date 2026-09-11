import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.monitor import Anomaly


class AnomalyRepository:
    """Data-access layer for detected anomalies. Every read scopes by
    owner_id — an anomaly is only ever reachable by the user who owns the
    monitor (and, transitively, the dataset) it came from."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def create(
        self,
        *,
        monitor_id: uuid.UUID,
        owner_id: uuid.UUID,
        dataset_id: uuid.UUID,
        metric_column: str,
        period_label: str,
        observed_value: float,
        baseline_value: float | None,
        change_percent: float | None,
        direction: str,
        detection_method: str,
        severity: str,
    ) -> Anomaly:
        anomaly = Anomaly(
            monitor_id=monitor_id,
            owner_id=owner_id,
            dataset_id=dataset_id,
            metric_column=metric_column,
            period_label=period_label,
            observed_value=observed_value,
            baseline_value=baseline_value,
            change_percent=change_percent,
            direction=direction,
            detection_method=detection_method,
            severity=severity,
        )
        self._db.add(anomaly)
        self._db.commit()
        self._db.refresh(anomaly)
        return anomaly

    def set_explanation(self, anomaly: Anomaly, explanation: str) -> Anomaly:
        anomaly.explanation = explanation
        self._db.add(anomaly)
        self._db.commit()
        self._db.refresh(anomaly)
        return anomaly

    def mark_alert_result(
        self, anomaly: Anomaly, *, sent: bool, sent_at: datetime | None, error: str | None
    ) -> Anomaly:
        anomaly.alert_sent = sent
        anomaly.alert_sent_at = sent_at
        anomaly.alert_error = error
        self._db.add(anomaly)
        self._db.commit()
        self._db.refresh(anomaly)
        return anomaly

    def list_for_owner(
        self, owner_id: uuid.UUID, *, monitor_id: uuid.UUID | None = None, limit: int = 100
    ) -> list[Anomaly]:
        stmt = select(Anomaly).where(Anomaly.owner_id == owner_id)
        if monitor_id is not None:
            stmt = stmt.where(Anomaly.monitor_id == monitor_id)
        stmt = stmt.order_by(Anomaly.created_at.desc()).limit(limit)
        return list(self._db.execute(stmt).scalars().all())

    def get_by_monitor_and_period(self, monitor_id: uuid.UUID, period_label: str) -> Anomaly | None:
        """Used to dedupe: re-evaluating a monitor against unchanged data
        (e.g. two scheduler runs before new data arrives) would otherwise
        detect the exact same anomaly again and re-alert on it."""
        stmt = select(Anomaly).where(
            Anomaly.monitor_id == monitor_id, Anomaly.period_label == period_label
        )
        return self._db.execute(stmt).scalar_one_or_none()
