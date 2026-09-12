import json

import polars as pl

from app.analytics.data_profile import build_data_profile, classify_column_kind


def _sample_df() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "order_id": ["A1", "A1", "A2", "A3", "A4", "A5", "A6", "A7"],
            "customer_age": [25, 25, 34, 101, -5, 40, 29, None],
            "category": ["East", "East", "West", "East", "West", "East", "West", "East"],
            "revenue": [10.0, 10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 5000.0],
            "order_date": [
                "2024-01-01", "2024-01-01", "2024-01-02", "2024-01-03",
                "2024-01-04", "2024-01-05", "2024-01-06", "2024-01-07",
            ],
        }
    )


def test_profile_reports_full_row_and_column_counts():
    df = _sample_df()
    profile = build_data_profile(df)
    assert profile.row_count == df.height
    assert profile.column_count == df.width


def test_profile_detects_missing_values():
    df = _sample_df()
    profile = build_data_profile(df)
    assert profile.columns["customer_age"]["missing_count"] == 1
    assert profile.columns["customer_age"]["missing_pct"] > 0


def test_profile_detects_duplicate_key_column_by_name_and_uniqueness():
    df = _sample_df()
    profile = build_data_profile(df)
    # order_id is key-like by name ("id") and has a duplicated value (A1
    # appears twice), so it must be checked and its duplicate count found.
    assert "order_id" in profile.duplicates["key_columns_checked"]
    assert profile.duplicates["duplicate_key_counts"]["order_id"] == 1


def test_profile_flags_statistical_outlier_in_revenue():
    df = _sample_df()
    profile = build_data_profile(df)
    assert "revenue" in profile.outliers
    assert profile.outliers["revenue"]["count"] >= 1


def test_profile_computes_pairwise_correlation():
    df = _sample_df()
    profile = build_data_profile(df)
    assert isinstance(profile.correlations, list)
    assert any(
        {pair["column_a"], pair["column_b"]} == {"customer_age", "revenue"}
        for pair in profile.correlations
    )


def test_profile_captures_temporal_range():
    df = _sample_df()
    profile = build_data_profile(df)
    assert "order_date" in profile.temporal
    assert profile.temporal["order_date"]["span_days"] == 6


def test_classify_column_kind_numeric_categorical_text():
    ids = pl.Series("id", list(range(30)))
    status = pl.Series("status", ["a", "b"] * 15)
    free_text = pl.Series("free_text", [f"note number {i} with unique detail" for i in range(30)])

    assert classify_column_kind("id", ids.dtype, ids) == "numeric"
    assert classify_column_kind("status", status.dtype, status) == "categorical"
    assert classify_column_kind("free_text", free_text.dtype, free_text) == "text"


def test_profile_to_dict_is_json_serializable():
    df = _sample_df()
    profile = build_data_profile(df)
    dumped = json.dumps(profile.to_dict(), default=str)
    assert "duplicates" in json.loads(dumped)
