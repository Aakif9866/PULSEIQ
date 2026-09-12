import polars as pl
import pytest

from app.analytics.sql_engine import execute_sql
from app.analytics.sql_validator import validate_and_prepare
from app.core.exceptions import InvalidQueryError

_DF = pl.DataFrame(
    {
        "region": ["east", "east", "west"],
        "revenue": [100, 30, 5],
    }
)
_COLUMNS = {"region", "revenue"}


def _run(sql: str) -> object:
    safe = validate_and_prepare(
        sql, table_name="dataset", allowed_columns=_COLUMNS, row_limit=10_000
    )
    return execute_sql(_DF, safe)


def test_execute_sql_returns_expected_aggregation():
    result = _run(
        "SELECT region, SUM(revenue) AS total FROM dataset GROUP BY region ORDER BY region"
    )
    assert result.columns == ["region", "total"]
    assert result.rows == [["east", 130], ["west", 5]]
    assert result.row_count == 2


def test_execute_sql_raw_row_select():
    result = _run("SELECT * FROM dataset WHERE region = 'west'")
    assert result.row_count == 1
    assert result.rows == [["west", 5]]


def test_execute_sql_respects_injected_limit():
    safe = validate_and_prepare(
        "SELECT * FROM dataset", table_name="dataset", allowed_columns=_COLUMNS, row_limit=2
    )
    result = execute_sql(_DF, safe)
    assert result.row_count == 2


def test_execute_sql_wraps_duckdb_errors_without_leaking_internals():
    # Passes parsing and validation (real table, real columns) but is a
    # genuine type error DuckDB only catches at execution/bind time
    # (adding a string column to a numeric one).
    safe = validate_and_prepare(
        "SELECT region + revenue FROM dataset",
        table_name="dataset", allowed_columns=_COLUMNS, row_limit=10_000,
    )
    with pytest.raises(InvalidQueryError):
        execute_sql(_DF, safe)
