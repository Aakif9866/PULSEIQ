"""Unit tests for app.ai.tools — the deterministic Python/Polars layer the
hybrid AI Analyst calls into. These run with no LLM/network involved at
all: every tool is a pure function over a real, FULL in-memory DataFrame,
so this is the part of docs/AI_ANALYTICS.md's redesign that's directly
and cheaply testable without mocking an AI provider.
"""
import polars as pl
import pytest

from app.ai import tool_specs, tools
from app.core.exceptions import ColumnNotFoundError


def _ecommerce_df() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "order_id": [
                "ORD001", "ORD001", "ORD002", "ORD003",
                "ORD004", "ORD005", "ORD006", "ORD008",
            ],
            "customer_age": [25, 25, 34, 101, -5, 40, 29, 33],
            "units": [1, 1, 2, 3, 1, 50, 2, 1],
            "unit_price_inr": [500, 500, 250, 100, 300, 5802, 400, 350],
            "discount_pct": [0, 0, 10, 0, 5, 0, 0, 0],
            "revenue_inr": [500.0, 500.0, 450.0, 300.0, 285.0, 290100.0, 800.0, 0.0],
            "category": [
                "Electronics", "Electronics", "Beauty", "Home",
                "Home", "Electronics", "Beauty", "Home",
            ],
            "order_date": [
                "2024-01-01", "2024-01-01", "2024-01-02", "2024-01-03",
                "2024-01-04", "2024-01-05", "2024-01-06", "2024-01-07",
            ],
        }
    )


def test_get_dataset_profile_covers_full_dataset():
    df = _ecommerce_df()
    profile = tools.get_dataset_profile(df)
    assert profile["dataset"]["rows"] == df.height


def test_get_missing_values_reports_zero_on_clean_data():
    df = _ecommerce_df()
    result = tools.get_missing_values(df)
    assert result["row_count"] == df.height
    assert result["columns_with_missing_values"] == {}


def test_get_missing_values_reports_actual_nulls():
    df = _ecommerce_df().with_columns(pl.Series("units", [1, None, 2, 3, 1, 50, 2, 1]))
    result = tools.get_missing_values(df)
    assert result["columns_with_missing_values"]["units"]["missing_count"] == 1


def test_get_duplicates_by_column_finds_the_real_duplicate_id():
    df = _ecommerce_df()
    result = tools.get_duplicates(df, column="order_id")
    assert result["duplicate_value_count"] == 1
    values = {row["order_id"] for row in result["duplicate_values"]}
    assert "ORD001" in values


def test_get_duplicates_whole_row_uses_profile_summary():
    df = _ecommerce_df()
    result = tools.get_duplicates(df)
    assert "duplicate_rows" in result


def test_get_duplicates_rejects_unknown_column():
    df = _ecommerce_df()
    with pytest.raises(ColumnNotFoundError):
        tools.get_duplicates(df, column="does_not_exist")


def test_detect_outliers_flags_the_extreme_unit_price():
    df = _ecommerce_df()
    result = tools.detect_outliers(df, column="unit_price_inr")
    assert result["count"] >= 1
    assert any(row["unit_price_inr"] == 5802 for row in result["sample_rows"])


def test_detect_outliers_rejects_non_numeric_column():
    df = _ecommerce_df()
    result = tools.detect_outliers(df, column="category")
    assert "error" in result


def test_detect_logical_violations_flags_out_of_range_age_but_not_outlier_price():
    df = _ecommerce_df()
    result = tools.detect_logical_violations(df)
    assert "customer_age" in result["violations"]
    # unit_price_inr has no bounded-semantics name hint, so a large but
    # real price is never mistaken for a logical violation.
    assert "unit_price_inr" not in result["violations"]


def test_detect_anomalies_combines_all_signal_types():
    df = _ecommerce_df()
    result = tools.detect_anomalies(df)
    assert set(result) == {
        "outliers", "logical_violations", "duplicates", "columns_with_missing_values",
    }


def test_calculate_correlation_between_units_and_revenue():
    df = _ecommerce_df()
    result = tools.calculate_correlation(df, column_a="units", column_b="revenue_inr")
    assert result["correlation"] is not None
    assert -1.0 <= result["correlation"] <= 1.0


def test_group_by_aggregate_sums_revenue_per_category():
    df = _ecommerce_df()
    result = tools.group_by_aggregate(df, group_by=["category"], column="revenue_inr", op="sum")
    rows = {row[0]: row[1] for row in result["rows"]}
    assert rows["Electronics"] == pytest.approx(500.0 + 500.0 + 290100.0)


def test_validate_formula_finds_the_one_real_mismatch():
    df = _ecommerce_df()
    result = tools.validate_formula(
        df,
        target_column="revenue_inr",
        formula="units * unit_price_inr * (1 - discount_pct / 100)",
        tolerance_pct=1.0,
    )
    # ORD008 has revenue_inr = 0 but units*price implies 350 — a genuine
    # mismatch. The mathematically-consistent-but-extreme ORD005 row
    # (50 * 5802 = 290100, matches exactly) must NOT be flagged.
    mismatched_ids = {row["order_id"] for row in result["sample_mismatches"]}
    assert "ORD008" in mismatched_ids
    assert "ORD005" not in mismatched_ids


def test_validate_formula_rejects_unknown_column_in_formula():
    df = _ecommerce_df()
    result = tools.validate_formula(
        df, target_column="revenue_inr", formula="units * not_a_real_column"
    )
    assert "error" in result


def test_get_top_and_bottom_records():
    df = _ecommerce_df()
    top = tools.get_top_records(df, column="revenue_inr", n=1)
    bottom = tools.get_bottom_records(df, column="revenue_inr", n=1)
    assert top["rows"][0]["order_id"] == "ORD005"
    assert bottom["rows"][0]["order_id"] == "ORD008"


def test_call_tool_dispatches_known_tool():
    df = _ecommerce_df()
    result = tool_specs.call_tool("get_missing_values", df, {})
    assert result["row_count"] == df.height


def test_call_tool_rejects_unknown_tool_name_without_raising():
    df = _ecommerce_df()
    result = tool_specs.call_tool("not_a_real_tool", df, {})
    assert "error" in result


def test_call_tool_never_raises_on_bad_arguments():
    df = _ecommerce_df()
    result = tool_specs.call_tool("get_column_statistics", df, {"column": "does_not_exist"})
    assert "error" in result


def test_all_dispatch_entries_have_a_matching_tool_spec():
    spec_names = {spec["function"]["name"] for spec in tool_specs.TOOL_SPECS}
    assert spec_names == set(tool_specs._DISPATCH)
