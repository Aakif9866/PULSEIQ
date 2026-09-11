"""Deterministic anomaly detection.

This module never calls an LLM and never imports anything from app.ai — by
design. Whether a metric is anomalous is decided entirely by ordinary
statistics over data the app itself computed; the AI's only job (in
app.ai.anomaly_explainer) is to put an already-decided anomaly into
readable English. See docs/V2_ROADMAP.md's "AI Anomaly Monitoring" section
for the reasoning.

Every public function here is pure — given a DataFrame and a config, it
returns a DetectionResult. No database session, no HTTP, no side effects.
"""
from dataclasses import dataclass
from typing import Literal

import polars as pl

from app.core.exceptions import ColumnNotFoundError

DetectionStatus = Literal["NO_ANOMALY", "ANOMALY_DETECTED", "INSUFFICIENT_DATA", "ERROR"]
Direction = Literal["increase", "decrease"]
Severity = Literal["low", "medium", "high"]

_PERIOD_COL = "__period"
_VALUE_COL = "__value"

# zscore needs enough samples for a standard deviation to mean anything —
# below this, even if the configured baseline_window is smaller, treat it
# as insufficient history rather than compute a statistically meaningless
# number.
_MIN_ZSCORE_SAMPLES = 5


@dataclass(frozen=True)
class DetectionResult:
    status: DetectionStatus
    method: str
    message: str | None = None
    period_label: str | None = None
    observed_value: float | None = None
    baseline_value: float | None = None
    change_percent: float | None = None
    direction: Direction | None = None
    severity: Severity | None = None


def build_metric_series(
    df: pl.DataFrame, *, metric_column: str, time_column: str, aggregation: str
) -> pl.DataFrame:
    """Buckets df by day (parsed from time_column) and aggregates
    metric_column, returning a DataFrame sorted ascending by period with
    columns [__period, __value]. Rows with an unparseable date, or a
    non-numeric metric value, are excluded rather than raising — a few bad
    rows in real-world data shouldn't crash the whole check.
    """
    if time_column not in df.columns:
        raise ColumnNotFoundError(time_column)
    if aggregation != "count" and metric_column not in df.columns:
        raise ColumnNotFoundError(metric_column)

    parsed = df.with_columns(
        pl.col(time_column).cast(pl.Utf8, strict=False).str.to_date(strict=False).alias(_PERIOD_COL)
    ).drop_nulls(subset=[_PERIOD_COL])

    if parsed.height == 0:
        return parsed.select(pl.col(_PERIOD_COL)).with_columns(
            pl.lit(None, dtype=pl.Float64).alias(_VALUE_COL)
        )

    if aggregation == "count":
        agg_expr = pl.len().alias(_VALUE_COL)
    else:
        metric_expr = pl.col(metric_column).cast(pl.Float64, strict=False)
        agg_by_op = {
            "sum": metric_expr.sum(),
            "avg": metric_expr.mean(),
            "min": metric_expr.min(),
            "max": metric_expr.max(),
        }
        if aggregation not in agg_by_op:
            raise ValueError(f"Unsupported aggregation for monitoring: {aggregation!r}")
        agg_expr = agg_by_op[aggregation].alias(_VALUE_COL)

    return (
        parsed.group_by(_PERIOD_COL)
        .agg(agg_expr)
        .drop_nulls(subset=[_VALUE_COL])
        .sort(_PERIOD_COL)
    )


def _direction(observed: float, baseline: float) -> Direction:
    return "increase" if observed >= baseline else "decrease"


def _severity(ratio_over_threshold: float) -> Severity:
    """ratio_over_threshold: how far past the configured threshold the
    deviation is (1.0 = exactly at the threshold). Simple, explainable
    banding — deliberately not a fitted/learned scale."""
    if ratio_over_threshold >= 2.0:
        return "high"
    if ratio_over_threshold >= 1.3:
        return "medium"
    return "low"


def _pct_change_result(
    *, method: str, period_label: str, observed: float, baseline: float, threshold_percent: float
) -> DetectionResult:
    if baseline == 0:
        if observed == 0:
            return DetectionResult(
                status="NO_ANOMALY", method=method, period_label=period_label,
                observed_value=observed, baseline_value=baseline, change_percent=0.0,
            )
        # A genuine move away from a true zero baseline — a % change isn't
        # mathematically defined, but the move itself is real and worth
        # surfacing rather than silently skipping.
        return DetectionResult(
            status="ANOMALY_DETECTED", method=method, period_label=period_label,
            observed_value=observed, baseline_value=baseline, change_percent=None,
            direction=_direction(observed, baseline), severity="medium",
            message="Baseline was zero; percentage change is undefined, but the "
            "value moved away from zero.",
        )

    change_percent = (observed - baseline) / abs(baseline) * 100
    if abs(change_percent) < threshold_percent:
        return DetectionResult(
            status="NO_ANOMALY", method=method, period_label=period_label,
            observed_value=observed, baseline_value=baseline, change_percent=change_percent,
        )
    return DetectionResult(
        status="ANOMALY_DETECTED", method=method, period_label=period_label,
        observed_value=observed, baseline_value=baseline, change_percent=change_percent,
        direction=_direction(observed, baseline),
        severity=_severity(abs(change_percent) / threshold_percent),
    )


def detect_percentage_change(series: pl.DataFrame, *, threshold_percent: float) -> DetectionResult:
    """Compares the latest period against the single period before it."""
    method = "percentage_change"
    if series.height < 2:
        return DetectionResult(
            status="INSUFFICIENT_DATA", method=method,
            message=f"Need at least 2 periods of history, found {series.height}.",
        )
    current = series.row(-1, named=True)
    previous = series.row(-2, named=True)
    return _pct_change_result(
        method=method,
        period_label=str(current[_PERIOD_COL]),
        observed=float(current[_VALUE_COL]),
        baseline=float(previous[_VALUE_COL]),
        threshold_percent=threshold_percent,
    )


def detect_moving_average(
    series: pl.DataFrame, *, window: int, threshold_percent: float
) -> DetectionResult:
    """Compares the latest period against the mean of the `window` periods
    immediately before it (a rolling baseline, not a fixed prior period)."""
    method = "moving_average"
    if series.height < window + 1:
        return DetectionResult(
            status="INSUFFICIENT_DATA", method=method,
            message=f"Need at least {window + 1} periods of history "
            f"({window}-period baseline + the current period), found {series.height}.",
        )
    current = series.row(-1, named=True)
    history = series.slice(-(window + 1), window)
    # __value is always Float64 (built by build_metric_series) — the stub's
    # broader return type (covering date/time-typed series too) doesn't
    # reflect that.
    baseline = float(history[_VALUE_COL].mean())  # type: ignore[arg-type]
    return _pct_change_result(
        method=method,
        period_label=str(current[_PERIOD_COL]),
        observed=float(current[_VALUE_COL]),
        baseline=baseline,
        threshold_percent=threshold_percent,
    )


def detect_zscore(series: pl.DataFrame, *, window: int, zscore_threshold: float) -> DetectionResult:
    """Compares the latest period's distance from the mean of its history,
    in standard deviations, against zscore_threshold."""
    method = "zscore"
    sample_size = max(window, _MIN_ZSCORE_SAMPLES)
    if series.height < sample_size + 1:
        return DetectionResult(
            status="INSUFFICIENT_DATA", method=method,
            message=f"Need at least {sample_size + 1} periods of history for a reliable "
            f"z-score (minimum sample size {_MIN_ZSCORE_SAMPLES}), found {series.height}.",
        )
    current = series.row(-1, named=True)
    observed = float(current[_VALUE_COL])
    period_label = str(current[_PERIOD_COL])
    history = series.slice(-(sample_size + 1), sample_size)[_VALUE_COL]
    # __value is always Float64 (built by build_metric_series) — the stub's
    # broader return type (covering date/time-typed series too) doesn't
    # reflect that.
    mean = float(history.mean())  # type: ignore[arg-type]
    # sample std (ddof=1); None only if sample_size < 2, which can't happen here
    std_raw = history.std()
    std: float | None = float(std_raw) if std_raw is not None else None  # type: ignore[arg-type]

    if std is None or std == 0:
        if observed == mean:
            return DetectionResult(
                status="NO_ANOMALY", method=method, period_label=period_label,
                observed_value=observed, baseline_value=mean, change_percent=0.0,
            )
        change_percent = ((observed - mean) / abs(mean) * 100) if mean != 0 else None
        return DetectionResult(
            status="ANOMALY_DETECTED", method=method, period_label=period_label,
            observed_value=observed, baseline_value=mean, change_percent=change_percent,
            direction=_direction(observed, mean), severity="medium",
            message="Historical values had zero variance, so a z-score isn't defined; "
            "flagged because the current value differs from that constant history.",
        )

    z = (observed - mean) / std
    change_percent = ((observed - mean) / abs(mean) * 100) if mean != 0 else None
    if abs(z) < zscore_threshold:
        return DetectionResult(
            status="NO_ANOMALY", method=method, period_label=period_label,
            observed_value=observed, baseline_value=mean, change_percent=change_percent,
        )
    return DetectionResult(
        status="ANOMALY_DETECTED", method=method, period_label=period_label,
        observed_value=observed, baseline_value=mean, change_percent=change_percent,
        direction=_direction(observed, mean),
        severity=_severity(abs(z) / zscore_threshold),
    )


def detect(
    df: pl.DataFrame,
    *,
    metric_column: str,
    time_column: str,
    aggregation: str,
    baseline_strategy: str,
    baseline_window: int,
    threshold_percent: float | None,
    zscore_threshold: float | None,
) -> DetectionResult:
    """The single entry point services/tests should call. Dispatches to the
    right strategy and turns any unexpected failure (bad data, an
    unsupported combination, a Polars error) into an ERROR result instead
    of raising — the caller always gets back a status to act on, matching
    the graceful-degradation requirement in docs/V2_ROADMAP.md."""
    method_map = {
        "previous_period": "percentage_change",
        "moving_average": "moving_average",
        "zscore": "zscore",
    }
    method = method_map.get(baseline_strategy)
    if method is None:
        return DetectionResult(
            status="ERROR", method=baseline_strategy,
            message=f"Unknown baseline strategy: {baseline_strategy!r}",
        )

    try:
        series = build_metric_series(
            df, metric_column=metric_column, time_column=time_column, aggregation=aggregation
        )
    except ColumnNotFoundError as exc:
        return DetectionResult(status="ERROR", method=method, message=f"Column not found: {exc}")
    except Exception as exc:  # noqa: BLE001 - deliberately broad, see docstring
        return DetectionResult(
            status="ERROR", method=method, message=f"Could not process data: {exc}"
        )

    if series.height == 0:
        return DetectionResult(
            status="INSUFFICIENT_DATA", method=method,
            message=f"No rows had a parseable date in '{time_column}' with a valid "
            f"'{metric_column}' value.",
        )

    try:
        if baseline_strategy == "previous_period":
            if threshold_percent is None:
                return DetectionResult(
                    status="ERROR", method=method,
                    message="threshold_percent is required for the previous_period strategy.",
                )
            return detect_percentage_change(series, threshold_percent=threshold_percent)
        if baseline_strategy == "moving_average":
            if threshold_percent is None:
                return DetectionResult(
                    status="ERROR", method=method,
                    message="threshold_percent is required for the moving_average strategy.",
                )
            return detect_moving_average(
                series, window=baseline_window, threshold_percent=threshold_percent
            )
        if baseline_strategy == "zscore":
            if zscore_threshold is None:
                return DetectionResult(
                    status="ERROR", method=method,
                    message="zscore_threshold is required for the zscore strategy.",
                )
            return detect_zscore(series, window=baseline_window, zscore_threshold=zscore_threshold)
    except Exception as exc:  # noqa: BLE001 - deliberately broad, see docstring
        return DetectionResult(status="ERROR", method=method, message=f"Detection failed: {exc}")

    return DetectionResult(
        status="ERROR", method=method, message="Unreachable baseline strategy branch."
    )
