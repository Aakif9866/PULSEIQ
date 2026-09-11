from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.dataset_query import AggregationOp

BaselineStrategy = Literal["previous_period", "moving_average", "zscore"]
CheckFrequency = Literal["hourly", "daily", "manual"]
Direction = Literal["increase", "decrease"]
DetectionMethod = Literal["percentage_change", "moving_average", "zscore"]
Severity = Literal["low", "medium", "high"]
# Mirrors app.monitoring.detection.DetectionStatus — the deterministic
# engine's outcome vocabulary, never decided by the AI (see
# docs/V2_ROADMAP.md's "Natural Language to SQL" architectural principle,
# applied here too: the LLM explains, it never decides).
MonitorStatus = Literal["NO_ANOMALY", "ANOMALY_DETECTED", "INSUFFICIENT_DATA", "ERROR"]


class MonitorCreate(BaseModel):
    dataset_id: UUID
    name: str = Field(min_length=1, max_length=255)
    metric_column: str = Field(min_length=1)
    aggregation: AggregationOp = "sum"
    time_column: str = Field(min_length=1)
    baseline_strategy: BaselineStrategy = "moving_average"
    baseline_window: int = Field(default=7, ge=3, le=90)
    threshold_percent: float | None = Field(default=20.0, gt=0)
    zscore_threshold: float | None = Field(default=3.0, gt=0)
    check_frequency: CheckFrequency = "daily"
    notify_email: bool = False


class MonitorUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    baseline_strategy: BaselineStrategy | None = None
    baseline_window: int | None = Field(default=None, ge=3, le=90)
    threshold_percent: float | None = Field(default=None, gt=0)
    zscore_threshold: float | None = Field(default=None, gt=0)
    check_frequency: CheckFrequency | None = None
    notify_email: bool | None = None
    is_enabled: bool | None = None


class MonitorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    dataset_id: UUID
    dataset_filename: str
    name: str
    metric_column: str
    aggregation: AggregationOp
    time_column: str
    baseline_strategy: BaselineStrategy
    baseline_window: int
    threshold_percent: float | None
    zscore_threshold: float | None
    check_frequency: CheckFrequency
    notify_email: bool
    is_enabled: bool
    last_checked_at: datetime | None
    last_status: MonitorStatus | None
    last_error: str | None
    created_at: datetime


class AnomalyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    monitor_id: UUID
    monitor_name: str
    dataset_id: UUID
    metric_column: str
    period_label: str
    observed_value: float
    baseline_value: float | None
    change_percent: float | None
    direction: Direction
    detection_method: DetectionMethod
    severity: Severity
    explanation: str | None
    alert_sent: bool
    alert_sent_at: datetime | None
    alert_error: str | None
    created_at: datetime


class MonitorRunResult(BaseModel):
    status: MonitorStatus
    message: str | None = None
    anomaly: AnomalyRead | None = None
