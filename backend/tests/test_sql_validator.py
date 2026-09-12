import pytest

from app.analytics.sql_validator import validate_and_prepare
from app.core.exceptions import InvalidQueryError

COLUMNS = {"region", "revenue", "orders"}


def test_valid_select_passes_through():
    sql = validate_and_prepare(
        "SELECT region, SUM(revenue) AS total FROM dataset GROUP BY region",
        table_name="dataset", allowed_columns=COLUMNS, row_limit=10_000,
    )
    assert "SELECT" in sql.upper()
    assert "LIMIT" in sql.upper()  # injected since the query had none


def test_existing_limit_is_preserved_not_duplicated():
    sql = validate_and_prepare(
        "SELECT region FROM dataset LIMIT 5",
        table_name="dataset", allowed_columns=COLUMNS, row_limit=10_000,
    )
    assert sql.upper().count("LIMIT") == 1
    assert "LIMIT 5" in sql


def test_select_list_alias_is_allowed_when_referenced_later():
    # "total" isn't a real column — it's an alias defined in this same
    # query's SELECT list, and must be allowed in ORDER BY.
    sql = validate_and_prepare(
        "SELECT region, SUM(revenue) AS total FROM dataset GROUP BY region ORDER BY total DESC",
        table_name="dataset", allowed_columns=COLUMNS, row_limit=10_000,
    )
    assert "total" in sql


def test_multi_statement_is_rejected():
    with pytest.raises(InvalidQueryError):
        validate_and_prepare(
            "SELECT * FROM dataset; DROP TABLE dataset",
            table_name="dataset", allowed_columns=COLUMNS, row_limit=10_000,
        )


@pytest.mark.parametrize(
    "sql",
    [
        "DROP TABLE dataset",
        "DELETE FROM dataset",
        "INSERT INTO dataset (region) VALUES ('east')",
        "UPDATE dataset SET revenue = 0",
        "CREATE TABLE evil (x int)",
        "ATTACH 'x.db' AS y",
        "PRAGMA table_info(dataset)",
    ],
)
def test_non_select_statements_are_rejected(sql):
    with pytest.raises(InvalidQueryError):
        validate_and_prepare(
            sql, table_name="dataset", allowed_columns=COLUMNS, row_limit=10_000
        )


def test_references_to_another_table_are_rejected():
    with pytest.raises(InvalidQueryError):
        validate_and_prepare(
            "SELECT * FROM other_table",
            table_name="dataset", allowed_columns=COLUMNS, row_limit=10_000,
        )


def test_subquery_referencing_another_table_is_rejected():
    with pytest.raises(InvalidQueryError):
        validate_and_prepare(
            "SELECT * FROM dataset WHERE revenue > (SELECT AVG(revenue) FROM other_table)",
            table_name="dataset", allowed_columns=COLUMNS, row_limit=10_000,
        )


def test_function_based_table_source_is_rejected():
    with pytest.raises(InvalidQueryError):
        validate_and_prepare(
            "SELECT * FROM read_csv('/etc/passwd')",
            table_name="dataset", allowed_columns=COLUMNS, row_limit=10_000,
        )


def test_cte_is_rejected_as_an_unknown_table_reference():
    # A documented MVP limitation, not an oversight — see
    # app/analytics/sql_validator.py's module docstring.
    with pytest.raises(InvalidQueryError):
        validate_and_prepare(
            "WITH recent AS (SELECT * FROM dataset) SELECT * FROM recent",
            table_name="dataset", allowed_columns=COLUMNS, row_limit=10_000,
        )


def test_alias_defined_in_a_subquery_is_allowed_in_the_enclosing_scope():
    # A real AI-generated pattern for a multi-step question ("high revenue
    # but low profit margin") — the inner alias "product_rev" is only
    # ever a real column inside the derived table, never in the dataset
    # itself, but referencing it from the enclosing scope is valid SQL.
    sql = validate_and_prepare(
        """SELECT product FROM dataset GROUP BY product
        HAVING SUM(revenue) > (
            SELECT AVG(product_rev) FROM (
                SELECT SUM(revenue) AS product_rev FROM dataset GROUP BY product
            ) AS sub
        )""",
        table_name="dataset", allowed_columns={"product", "revenue"}, row_limit=10_000,
    )
    assert "product_rev" in sql


def test_unknown_column_is_rejected():
    with pytest.raises(InvalidQueryError, match="not_a_real_column"):
        validate_and_prepare(
            "SELECT not_a_real_column FROM dataset",
            table_name="dataset", allowed_columns=COLUMNS, row_limit=10_000,
        )


def test_invalid_sql_syntax_is_rejected_cleanly():
    with pytest.raises(InvalidQueryError):
        validate_and_prepare(
            "SELECT FROM WHERE ???",
            table_name="dataset", allowed_columns=COLUMNS, row_limit=10_000,
        )


def test_empty_statement_is_rejected():
    with pytest.raises(InvalidQueryError):
        validate_and_prepare(
            "", table_name="dataset", allowed_columns=COLUMNS, row_limit=10_000
        )
