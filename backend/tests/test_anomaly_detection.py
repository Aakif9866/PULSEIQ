"""Pure unit tests for the deterministic detection engine — no database, no
HTTP, no AI. See app/monitoring/detection.py's module docstring for why
this layer is deliberately AI-free."""
import polars as pl
import pytest

from app.core.exceptions import ColumnNotFoundError
from app.monitoring.detection import (
    build_metric_series,
    detect,
    detect_moving_average,
    detect_percentage_change,
    detect_zscore,
)


def _daily_df(values: list[float], *, start="2026-01-01") -> pl.DataFrame:
    import datetime

    base = datetime.date.fromisoformat(start)
    rows = [
        {"date": str(base + datetime.timedelta(days=i)), "revenue": v} for i, v in enumerate(values)
    ]
    return pl.DataFrame(rows)


# ---------- build_metric_series ----------


def test_build_metric_series_sums_per_day():
    df = pl.DataFrame(
        {
            "date": ["2026-01-01", "2026-01-01", "2026-01-02"],
            "revenue": [100.0, 50.0, 80.0],
        }
    )
    series = build_metric_series(df, metric_column="revenue", time_column="date", aggregation="sum")
    assert series.height == 2
    assert series["__value"].to_list() == [150.0, 80.0]


def test_build_metric_series_unknown_time_column_raises():
    df = pl.DataFrame({"date": ["2026-01-01"], "revenue": [1.0]})
    with pytest.raises(ColumnNotFoundError):
        build_metric_series(df, metric_column="revenue", time_column="missing", aggregation="sum")


def test_build_metric_series_unknown_metric_column_raises():
    df = pl.DataFrame({"date": ["2026-01-01"], "revenue": [1.0]})
    with pytest.raises(ColumnNotFoundError):
        build_metric_series(df, metric_column="missing", time_column="date", aggregation="sum")


def test_build_metric_series_count_ignores_metric_column():
    df = pl.DataFrame({"date": ["2026-01-01", "2026-01-01"], "revenue": [None, None]})
    series = build_metric_series(
        df, metric_column="revenue", time_column="date", aggregation="count"
    )
    assert series["__value"].to_list() == [2]


def test_build_metric_series_drops_unparseable_dates_and_nulls():
    df = pl.DataFrame(
        {"date": ["2026-01-01", "not-a-date", None], "revenue": [10.0, 20.0, 30.0]}
    )
    series = build_metric_series(df, metric_column="revenue", time_column="date", aggregation="sum")
    assert series.height == 1


def test_build_metric_series_empty_dataframe_returns_empty_series():
    df = pl.DataFrame({"date": [], "revenue": []}, schema={"date": pl.Utf8, "revenue": pl.Float64})
    series = build_metric_series(df, metric_column="revenue", time_column="date", aggregation="sum")
    assert series.height == 0


# ---------- detect_percentage_change ----------


def test_percentage_change_normal_metric_is_no_anomaly():
    df = _daily_df([100.0, 102.0])
    series = build_metric_series(df, metric_column="revenue", time_column="date", aggregation="sum")
    result = detect_percentage_change(series, threshold_percent=20.0)
    assert result.status == "NO_ANOMALY"
    assert result.change_percent == pytest.approx(2.0)


def test_percentage_change_large_increase_is_anomaly():
    df = _daily_df([100.0, 150.0])
    series = build_metric_series(df, metric_column="revenue", time_column="date", aggregation="sum")
    result = detect_percentage_change(series, threshold_percent=20.0)
    assert result.status == "ANOMALY_DETECTED"
    assert result.direction == "increase"
    assert result.change_percent == pytest.approx(50.0)
    assert result.severity == "high"  # 50/20 = 2.5x threshold


def test_percentage_change_large_decrease_is_anomaly():
    df = _daily_df([100.0, 60.0])
    series = build_metric_series(df, metric_column="revenue", time_column="date", aggregation="sum")
    result = detect_percentage_change(series, threshold_percent=20.0)
    assert result.status == "ANOMALY_DETECTED"
    assert result.direction == "decrease"
    assert result.change_percent == pytest.approx(-40.0)
    assert result.severity == "high"  # 40/20 = 2.0x threshold


def test_percentage_change_severity_bands():
    # Exactly at threshold ratio 1.0 -> low
    df_low = _daily_df([100.0, 121.0])  # 21% > 20% threshold, ratio 1.05
    series_low = build_metric_series(
        df_low, metric_column="revenue", time_column="date", aggregation="sum"
    )
    assert detect_percentage_change(series_low, threshold_percent=20.0).severity == "low"

    # ratio 2.5 -> high
    df_high = _daily_df([100.0, 150.0])
    series_high = build_metric_series(
        df_high, metric_column="revenue", time_column="date", aggregation="sum"
    )
    assert detect_percentage_change(series_high, threshold_percent=20.0).severity == "high"


def test_percentage_change_insufficient_data():
    df = _daily_df([100.0])
    series = build_metric_series(df, metric_column="revenue", time_column="date", aggregation="sum")
    result = detect_percentage_change(series, threshold_percent=20.0)
    assert result.status == "INSUFFICIENT_DATA"


def test_percentage_change_zero_baseline_nonzero_current_is_anomaly_without_percent():
    df = _daily_df([0.0, 500.0])
    series = build_metric_series(df, metric_column="revenue", time_column="date", aggregation="sum")
    result = detect_percentage_change(series, threshold_percent=20.0)
    assert result.status == "ANOMALY_DETECTED"
    assert result.change_percent is None
    assert result.direction == "increase"


def test_percentage_change_zero_baseline_zero_current_is_no_anomaly():
    df = _daily_df([0.0, 0.0])
    series = build_metric_series(df, metric_column="revenue", time_column="date", aggregation="sum")
    result = detect_percentage_change(series, threshold_percent=20.0)
    assert result.status == "NO_ANOMALY"


# ---------- detect_moving_average ----------


def test_moving_average_anomaly():
    history = [100.0] * 7
    df = _daily_df([*history, 135.0])
    series = build_metric_series(df, metric_column="revenue", time_column="date", aggregation="sum")
    result = detect_moving_average(series, window=7, threshold_percent=20.0)
    assert result.status == "ANOMALY_DETECTED"
    assert result.baseline_value == pytest.approx(100.0)
    assert result.change_percent == pytest.approx(35.0)


def test_moving_average_normal_is_no_anomaly():
    history = [100.0, 105.0, 95.0, 110.0, 90.0, 100.0, 100.0]
    df = _daily_df([*history, 102.0])
    series = build_metric_series(df, metric_column="revenue", time_column="date", aggregation="sum")
    result = detect_moving_average(series, window=7, threshold_percent=20.0)
    assert result.status == "NO_ANOMALY"


def test_moving_average_insufficient_data():
    df = _daily_df([100.0, 100.0, 100.0])
    series = build_metric_series(df, metric_column="revenue", time_column="date", aggregation="sum")
    result = detect_moving_average(series, window=7, threshold_percent=20.0)
    assert result.status == "INSUFFICIENT_DATA"


# ---------- detect_zscore ----------


def test_zscore_anomaly():
    history = [100.0, 102.0, 98.0, 101.0, 99.0, 100.0]
    df = _daily_df([*history, 200.0])
    series = build_metric_series(df, metric_column="revenue", time_column="date", aggregation="sum")
    result = detect_zscore(series, window=6, zscore_threshold=3.0)
    assert result.status == "ANOMALY_DETECTED"
    assert result.direction == "increase"


def test_zscore_normal_is_no_anomaly():
    history = [100.0, 102.0, 98.0, 101.0, 99.0, 100.0]
    df = _daily_df([*history, 103.0])
    series = build_metric_series(df, metric_column="revenue", time_column="date", aggregation="sum")
    result = detect_zscore(series, window=6, zscore_threshold=3.0)
    assert result.status == "NO_ANOMALY"


def test_zscore_insufficient_history_below_minimum_sample_size():
    # window=3 is below the engine's minimum sample size (5), so it should
    # still require 5+1 periods, not just 3+1.
    df = _daily_df([100.0, 100.0, 100.0, 100.0])
    series = build_metric_series(df, metric_column="revenue", time_column="date", aggregation="sum")
    result = detect_zscore(series, window=3, zscore_threshold=3.0)
    assert result.status == "INSUFFICIENT_DATA"


def test_zscore_zero_variance_history_flags_any_deviation():
    df = _daily_df([100.0, 100.0, 100.0, 100.0, 100.0, 150.0])
    series = build_metric_series(df, metric_column="revenue", time_column="date", aggregation="sum")
    result = detect_zscore(series, window=5, zscore_threshold=3.0)
    assert result.status == "ANOMALY_DETECTED"
    assert "zero variance" in (result.message or "")


# ---------- detect() dispatcher ----------


def test_detect_dispatches_to_moving_average():
    history = [100.0] * 7
    df = _daily_df([*history, 200.0])
    result = detect(
        df, metric_column="revenue", time_column="date", aggregation="sum",
        baseline_strategy="moving_average", baseline_window=7,
        threshold_percent=20.0, zscore_threshold=None,
    )
    assert result.status == "ANOMALY_DETECTED"
    assert result.method == "moving_average"


def test_detect_unknown_column_returns_error_not_raise():
    df = _daily_df([100.0, 100.0])
    result = detect(
        df, metric_column="does_not_exist", time_column="date", aggregation="sum",
        baseline_strategy="previous_period", baseline_window=7,
        threshold_percent=20.0, zscore_threshold=None,
    )
    assert result.status == "ERROR"
    assert result.message is not None


def test_detect_missing_values_in_metric_column_does_not_crash():
    # A period whose only rows are null averages to null for "avg" (unlike
    # "sum", which treats an all-null group as 0) — that null period is
    # dropped, leaving only one valid period, which is insufficient rather
    # than a crash or a false anomaly.
    df = pl.DataFrame(
        {
            "date": ["2026-01-01", "2026-01-02"],
            "revenue": [None, 100.0],
        },
        schema={"date": pl.Utf8, "revenue": pl.Float64},
    )
    result = detect(
        df, metric_column="revenue", time_column="date", aggregation="avg",
        baseline_strategy="previous_period", baseline_window=7,
        threshold_percent=20.0, zscore_threshold=None,
    )
    assert result.status == "INSUFFICIENT_DATA"


def test_detect_all_null_period_with_sum_aggregation_is_treated_as_zero():
    # "sum" is the one aggregation where an all-null period legitimately
    # means "nothing recorded that day" = 0, not missing data — documented
    # here so the distinction from the "avg" case above is explicit.
    df = pl.DataFrame(
        {
            "date": ["2026-01-01", "2026-01-02"],
            "revenue": [None, 100.0],
        },
        schema={"date": pl.Utf8, "revenue": pl.Float64},
    )
    result = detect(
        df, metric_column="revenue", time_column="date", aggregation="sum",
        baseline_strategy="previous_period", baseline_window=7,
        threshold_percent=20.0, zscore_threshold=None,
    )
    assert result.status == "ANOMALY_DETECTED"
    assert result.baseline_value == 0.0


def test_detect_empty_dataset_is_insufficient_data():
    df = pl.DataFrame({"date": [], "revenue": []}, schema={"date": pl.Utf8, "revenue": pl.Float64})
    result = detect(
        df, metric_column="revenue", time_column="date", aggregation="sum",
        baseline_strategy="previous_period", baseline_window=7,
        threshold_percent=20.0, zscore_threshold=None,
    )
    assert result.status == "INSUFFICIENT_DATA"


def test_detect_irregular_dates_are_bucketed_correctly():
    df = pl.DataFrame(
        {
            "date": ["2026-01-01", "01/02/2026", "2026-01-03"],
            "revenue": [100.0, 999.0, 105.0],
        }
    )
    # "01/02/2026" won't parse as an ISO date and should simply be dropped,
    # not crash detection.
    result = detect(
        df, metric_column="revenue", time_column="date", aggregation="sum",
        baseline_strategy="previous_period", baseline_window=7,
        threshold_percent=20.0, zscore_threshold=None,
    )
    assert result.status in {"NO_ANOMALY", "ANOMALY_DETECTED"}
    assert result.observed_value == pytest.approx(105.0)
