import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.analytics.loader import load_dataframe
from app.core.email import send_email
from app.core.exceptions import (
    AiResponseError,
    ColumnNotFoundError,
    DatasetNotFoundError,
    DatasetNotReadyError,
    MonitorNotFoundError,
)
from app.core.logging import get_logger
from app.models.dataset import Dataset
from app.models.monitor import Anomaly, Monitor
from app.monitoring.detection import DetectionResult, detect
from app.repositories.anomaly_repository import AnomalyRepository
from app.repositories.dataset_repository import DatasetRepository
from app.repositories.monitor_repository import MonitorRepository
from app.repositories.user_repository import UserRepository
from app.schemas.monitor import (
    AnomalyRead,
    MonitorCreate,
    MonitorRead,
    MonitorRunResult,
    MonitorUpdate,
)
from app.storage.base import StorageProvider

logger = get_logger(__name__)

_FREQUENCY_INTERVALS = {"hourly": timedelta(hours=1), "daily": timedelta(days=1)}
_DELETED_DATASET_LABEL = "(dataset no longer exists)"


class MonitorService:
    """Orchestrates the Monitor -> Detect -> Explain -> Alert pipeline
    (docs/V2_ROADMAP.md). Deliberately thin: the actual anomaly-or-not
    decision lives entirely in app.monitoring.detection (deterministic, no
    AI); this class wires that decision to persistence, an optional AI
    explanation, and an optional email alert — and makes sure a failure in
    either of the latter two never undoes the former."""

    def __init__(self, db: Session, storage: StorageProvider) -> None:
        self._db = db
        self._storage = storage
        self._monitors = MonitorRepository(db)
        self._anomalies = AnomalyRepository(db)
        self._datasets = DatasetRepository(db)

    # ---- CRUD (owner-scoped, HTTP-reachable) ----

    def create(self, owner_id: uuid.UUID, payload: MonitorCreate) -> MonitorRead:
        dataset = self._get_owned_dataset(payload.dataset_id, owner_id)
        self._validate_columns(
            dataset, payload.metric_column, payload.time_column, payload.aggregation
        )

        monitor = self._monitors.create(
            owner_id=owner_id,
            dataset_id=payload.dataset_id,
            name=payload.name,
            metric_column=payload.metric_column,
            aggregation=payload.aggregation,
            time_column=payload.time_column,
            baseline_strategy=payload.baseline_strategy,
            baseline_window=payload.baseline_window,
            threshold_percent=payload.threshold_percent,
            zscore_threshold=payload.zscore_threshold,
            check_frequency=payload.check_frequency,
            notify_email=payload.notify_email,
        )
        return self._to_read(monitor, dataset.original_filename)

    def list_for_owner(self, owner_id: uuid.UUID) -> list[MonitorRead]:
        monitors = self._monitors.list_for_owner(owner_id)
        return [self._to_read(m, self._dataset_filename(m.dataset_id, owner_id)) for m in monitors]

    def get(self, monitor_id: uuid.UUID, owner_id: uuid.UUID) -> MonitorRead:
        monitor = self._get_owned_monitor(monitor_id, owner_id)
        return self._to_read(monitor, self._dataset_filename(monitor.dataset_id, owner_id))

    def update(
        self, monitor_id: uuid.UUID, owner_id: uuid.UUID, payload: MonitorUpdate
    ) -> MonitorRead:
        monitor = self._get_owned_monitor(monitor_id, owner_id)
        updates = payload.model_dump(exclude_unset=True)
        monitor = self._monitors.update_fields(monitor, updates)
        return self._to_read(monitor, self._dataset_filename(monitor.dataset_id, owner_id))

    def delete(self, monitor_id: uuid.UUID, owner_id: uuid.UUID) -> None:
        monitor = self._get_owned_monitor(monitor_id, owner_id)
        self._monitors.delete(monitor)

    def list_anomalies(
        self, owner_id: uuid.UUID, *, monitor_id: uuid.UUID | None = None
    ) -> list[AnomalyRead]:
        if monitor_id is not None:
            self._get_owned_monitor(monitor_id, owner_id)  # 404s cleanly if not owned
        anomalies = self._anomalies.list_for_owner(owner_id, monitor_id=monitor_id)
        names = {m.id: m.name for m in self._monitors.list_for_owner(owner_id)}
        return [
            self._anomaly_to_read(a, names.get(a.monitor_id, "(deleted monitor)"))
            for a in anomalies
        ]

    def run_monitor(self, monitor_id: uuid.UUID, owner_id: uuid.UUID) -> MonitorRunResult:
        monitor = self._get_owned_monitor(monitor_id, owner_id)
        return self._evaluate(monitor)

    # ---- scheduler entrypoint (NOT owner-scoped; system-only, see
    # app/workers/anomaly_runner.py — never exposed over HTTP) ----

    def run_due_monitors(self) -> list[tuple[uuid.UUID, MonitorRunResult]]:
        now = datetime.now(UTC)
        results: list[tuple[uuid.UUID, MonitorRunResult]] = []
        for monitor in self._monitors.list_enabled():
            if not self._is_due(monitor, now):
                continue
            results.append((monitor.id, self._evaluate(monitor)))
        return results

    # ---- internals ----

    def _is_due(self, monitor: Monitor, now: datetime) -> bool:
        if monitor.last_checked_at is None:
            return True
        interval = _FREQUENCY_INTERVALS.get(monitor.check_frequency)
        if interval is None:  # "manual" (or anything unrecognized) is never auto-due
            return False
        last_checked = monitor.last_checked_at
        if last_checked.tzinfo is None:
            last_checked = last_checked.replace(tzinfo=UTC)
        return (now - last_checked) >= interval

    def _evaluate(self, monitor: Monitor) -> MonitorRunResult:
        now = datetime.now(UTC)
        dataset = self._datasets.get_owned(monitor.dataset_id, monitor.owner_id)
        if dataset is None or dataset.status != "profiled":
            message = "Dataset is not available or not profiled."
            self._monitors.mark_checked(monitor, status="ERROR", checked_at=now, error=message)
            return MonitorRunResult(status="ERROR", message=message)

        try:
            df = load_dataframe(self._storage, dataset)
        except Exception as exc:
            logger.error("monitor_dataset_load_failed", monitor_id=str(monitor.id), exc_info=True)
            self._monitors.mark_checked(monitor, status="ERROR", checked_at=now, error=str(exc))
            return MonitorRunResult(status="ERROR", message="Could not load the dataset.")

        result: DetectionResult = detect(
            df,
            metric_column=monitor.metric_column,
            time_column=monitor.time_column,
            aggregation=monitor.aggregation,
            baseline_strategy=monitor.baseline_strategy,
            baseline_window=monitor.baseline_window,
            threshold_percent=monitor.threshold_percent,
            zscore_threshold=monitor.zscore_threshold,
        )

        self._monitors.mark_checked(
            monitor,
            status=result.status,
            checked_at=now,
            error=result.message if result.status == "ERROR" else None,
        )

        if result.status != "ANOMALY_DETECTED":
            return MonitorRunResult(status=result.status, message=result.message)

        assert result.period_label is not None
        existing = self._anomalies.get_by_monitor_and_period(monitor.id, result.period_label)
        if existing is not None:
            # Same monitor, same data period already recorded — re-running
            # against unchanged data (e.g. two scheduler ticks before new
            # data arrives) returns the existing event instead of creating
            # a duplicate row or sending a second alert.
            return MonitorRunResult(
                status="ANOMALY_DETECTED",
                message="Anomaly for this period was already recorded.",
                anomaly=self._anomaly_to_read(existing, monitor.name),
            )

        anomaly = self._persist_anomaly(monitor, result)
        return MonitorRunResult(
            status="ANOMALY_DETECTED", anomaly=self._anomaly_to_read(anomaly, monitor.name)
        )

    def _persist_anomaly(self, monitor: Monitor, result: DetectionResult) -> Anomaly:
        # observed_value/direction/severity/period_label are always set by
        # app.monitoring.detection whenever status == ANOMALY_DETECTED —
        # asserted here rather than silently coalesced, so a future engine
        # bug that breaks this invariant fails loudly instead of writing a
        # half-populated row.
        assert result.observed_value is not None
        assert result.direction is not None
        assert result.severity is not None
        assert result.period_label is not None

        anomaly = self._anomalies.create(
            monitor_id=monitor.id,
            owner_id=monitor.owner_id,
            dataset_id=monitor.dataset_id,
            metric_column=monitor.metric_column,
            period_label=result.period_label,
            observed_value=result.observed_value,
            baseline_value=result.baseline_value,
            change_percent=result.change_percent,
            direction=result.direction,
            detection_method=result.method,
            severity=result.severity,
        )

        explanation = self._try_explain(monitor, result)
        if explanation is not None:
            anomaly = self._anomalies.set_explanation(anomaly, explanation)

        if monitor.notify_email:
            self._try_send_alert(monitor, anomaly)

        return anomaly

    def _try_explain(self, monitor: Monitor, result: DetectionResult) -> str | None:
        """AI explanation is best-effort: any failure here must never
        affect the already-persisted anomaly (tested explicitly in
        tests/test_monitors.py)."""
        from app.ai.anomaly_explainer import explain_anomaly, is_available

        if not is_available():
            return None
        context: dict[str, object] = {
            "monitor_name": monitor.name,
            "metric": monitor.metric_column,
            "aggregation": monitor.aggregation,
            "period": result.period_label,
            "observed_value": result.observed_value,
            "baseline_value": result.baseline_value,
            "change_percent": result.change_percent,
            "direction": result.direction,
            "severity": result.severity,
        }
        try:
            return explain_anomaly(context)
        except AiResponseError:
            logger.warning("anomaly_explanation_unavailable", monitor_id=str(monitor.id))
            return None
        except Exception:
            logger.error(
                "anomaly_explanation_unexpected_failure", monitor_id=str(monitor.id), exc_info=True
            )
            return None

    def _try_send_alert(self, monitor: Monitor, anomaly: Anomaly) -> None:
        """Email is best-effort: a failure here must never roll back or
        otherwise corrupt the already-persisted anomaly."""
        user = UserRepository(self._db).get_by_id(monitor.owner_id)
        if user is None:
            self._anomalies.mark_alert_result(
                anomaly, sent=False, sent_at=None, error="Monitor owner account no longer exists."
            )
            return

        try:
            send_email(
                to=user.email,
                subject=f"PulseIQ Alert: {monitor.name} anomaly detected",
                body_text=_build_alert_body(monitor, anomaly),
            )
        except Exception as exc:
            logger.warning(
                "anomaly_alert_email_failed", monitor_id=str(monitor.id), error=str(exc)
            )
            self._anomalies.mark_alert_result(anomaly, sent=False, sent_at=None, error=str(exc))
            return

        self._anomalies.mark_alert_result(anomaly, sent=True, sent_at=datetime.now(UTC), error=None)

    def _validate_columns(
        self, dataset: Dataset, metric_column: str, time_column: str, aggregation: str
    ) -> None:
        if dataset.status != "profiled" or not dataset.columns_profile:
            raise DatasetNotReadyError(dataset.status)
        known = {c["name"] for c in dataset.columns_profile}
        if time_column not in known:
            raise ColumnNotFoundError(time_column)
        if aggregation != "count" and metric_column not in known:
            raise ColumnNotFoundError(metric_column)

    def _get_owned_dataset(self, dataset_id: uuid.UUID, owner_id: uuid.UUID) -> Dataset:
        dataset = self._datasets.get_owned(dataset_id, owner_id)
        if dataset is None:
            raise DatasetNotFoundError(dataset_id)
        return dataset

    def _get_owned_monitor(self, monitor_id: uuid.UUID, owner_id: uuid.UUID) -> Monitor:
        monitor = self._monitors.get_owned(monitor_id, owner_id)
        if monitor is None:
            raise MonitorNotFoundError(monitor_id)
        return monitor

    def _dataset_filename(self, dataset_id: uuid.UUID, owner_id: uuid.UUID) -> str:
        dataset = self._datasets.get_owned(dataset_id, owner_id)
        return dataset.original_filename if dataset else _DELETED_DATASET_LABEL

    def _to_read(self, monitor: Monitor, dataset_filename: str) -> MonitorRead:
        return MonitorRead(
            id=monitor.id,
            dataset_id=monitor.dataset_id,
            dataset_filename=dataset_filename,
            name=monitor.name,
            metric_column=monitor.metric_column,
            aggregation=monitor.aggregation,  # type: ignore[arg-type]
            time_column=monitor.time_column,
            baseline_strategy=monitor.baseline_strategy,  # type: ignore[arg-type]
            baseline_window=monitor.baseline_window,
            threshold_percent=monitor.threshold_percent,
            zscore_threshold=monitor.zscore_threshold,
            check_frequency=monitor.check_frequency,  # type: ignore[arg-type]
            notify_email=monitor.notify_email,
            is_enabled=monitor.is_enabled,
            last_checked_at=monitor.last_checked_at,
            last_status=monitor.last_status,  # type: ignore[arg-type]
            last_error=monitor.last_error,
            created_at=monitor.created_at,
        )

    def _anomaly_to_read(self, anomaly: Anomaly, monitor_name: str) -> AnomalyRead:
        return AnomalyRead(
            id=anomaly.id,
            monitor_id=anomaly.monitor_id,
            monitor_name=monitor_name,
            dataset_id=anomaly.dataset_id,
            metric_column=anomaly.metric_column,
            period_label=anomaly.period_label,
            observed_value=anomaly.observed_value,
            baseline_value=anomaly.baseline_value,
            change_percent=anomaly.change_percent,
            direction=anomaly.direction,  # type: ignore[arg-type]
            detection_method=anomaly.detection_method,  # type: ignore[arg-type]
            severity=anomaly.severity,  # type: ignore[arg-type]
            explanation=anomaly.explanation,
            alert_sent=anomaly.alert_sent,
            alert_sent_at=anomaly.alert_sent_at,
            alert_error=anomaly.alert_error,
            created_at=anomaly.created_at,
        )


def _build_alert_body(monitor: Monitor, anomaly: Anomaly) -> str:
    direction_word = "increased" if anomaly.direction == "increase" else "decreased"
    if anomaly.change_percent is not None:
        change = f"{abs(anomaly.change_percent):.1f}%"
    else:
        change = "an amount that couldn't be expressed as a percentage"
    baseline_text = anomaly.baseline_value if anomaly.baseline_value is not None else "n/a"
    lines = [
        f"{monitor.metric_column} {direction_word} by {change} on {anomaly.period_label}.",
        "",
        f"Observed value: {anomaly.observed_value}",
        f"Baseline value: {baseline_text}",
        f"Severity: {anomaly.severity}",
        "",
    ]
    if anomaly.explanation:
        lines.append(anomaly.explanation)
        lines.append("")
    lines.append(f"Detected: {anomaly.created_at.strftime('%d %B %Y')}")
    return "\n".join(lines)
