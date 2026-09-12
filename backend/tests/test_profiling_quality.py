"""Pure unit tests for the data-quality extensions to profile_dataframe()
(docs/V2_ROADMAP.md's "Data Profiling and Data Quality"). The pre-existing
row/column/dtype/null_count behavior already has coverage elsewhere; this
file targets what V2 actually added."""
import polars as pl

from app.analytics.profiling import profile_dataframe


def test_duplicate_row_count():
    df = pl.DataFrame({"a": [1, 1, 2], "b": ["x", "x", "y"]})
    profile = profile_dataframe(df)
    assert profile.duplicate_row_count == 2  # both rows of the duplicate pair count


def test_no_duplicates_is_zero():
    df = pl.DataFrame({"a": [1, 2, 3]})
    profile = profile_dataframe(df)
    assert profile.duplicate_row_count == 0


def test_null_percentage_is_computed_per_column():
    df = pl.DataFrame({"a": [1, None, None, 4]})
    profile = profile_dataframe(df)
    col = profile.columns[0]
    assert col["null_count"] == 2
    assert col["null_percentage"] == 50.0


def test_numeric_column_gets_min_max_mean():
    df = pl.DataFrame({"revenue": [10, 20, 30]})
    profile = profile_dataframe(df)
    col = profile.columns[0]
    assert col["min"] == 10
    assert col["max"] == 30
    assert col["mean"] == 20.0


def test_numeric_outlier_is_detected():
    df = pl.DataFrame({"revenue": [10, 12, 11, 13, 12, 1000]})
    profile = profile_dataframe(df)
    col = profile.columns[0]
    assert col["outlier_count"] == 1


def test_no_outliers_in_uniform_data():
    df = pl.DataFrame({"revenue": [10, 11, 12, 11, 10]})
    profile = profile_dataframe(df)
    col = profile.columns[0]
    assert col["outlier_count"] == 0


def test_categorical_column_gets_top_values():
    df = pl.DataFrame({"region": ["east", "east", "west", "east", "south"]})
    profile = profile_dataframe(df)
    col = profile.columns[0]
    top = {v["value"]: v["count"] for v in col["top_values"]}
    assert top["east"] == 3
    assert top["west"] == 1


def test_correlation_computed_for_two_numeric_columns():
    df = pl.DataFrame({"a": [1, 2, 3, 4], "b": [10, 20, 30, 40]})
    profile = profile_dataframe(df)
    assert len(profile.correlations) == 1
    assert profile.correlations[0]["correlation"] == 1.0


def test_no_correlation_with_fewer_than_two_numeric_columns():
    df = pl.DataFrame({"region": ["a", "b"], "amount": [1, 2]})
    profile = profile_dataframe(df)
    assert profile.correlations == []


def test_quality_score_is_100_for_perfect_data():
    df = pl.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
    profile = profile_dataframe(df)
    assert profile.data_quality_score == 100.0


def test_quality_score_drops_with_missing_values_and_duplicates():
    df = pl.DataFrame({"a": [1, None, 1], "b": ["x", None, "x"]})
    profile = profile_dataframe(df)
    assert profile.data_quality_score < 100.0
    assert profile.data_quality_score >= 0.0


def test_empty_dataframe_does_not_crash():
    df = pl.DataFrame({"a": [], "b": []}, schema={"a": pl.Int64, "b": pl.Utf8})
    profile = profile_dataframe(df)
    assert profile.row_count == 0
    assert profile.duplicate_row_count == 0
    assert profile.data_quality_score == 0.0
