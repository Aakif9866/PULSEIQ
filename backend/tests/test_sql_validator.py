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


# ---- Phase 8 step 2 security audit regressions (docs/SECURITY.md) ----
# Every case below was a real, working bypass verified live against this
# module before the fix — not a hypothetical.


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT version() FROM dataset",
        "SELECT current_database() FROM dataset",
        "SELECT current_setting('data_directory') FROM dataset",
        "SELECT read_text('/etc/passwd') FROM dataset",
        "SELECT region FROM dataset WHERE revenue > (SELECT length(read_text('/etc/passwd')))",
    ],
)
def test_unrecognized_function_calls_are_rejected(sql):
    # Only exp.Table and exp.Column were ever checked — a bare function
    # call in the SELECT list or WHERE clause had no validation at all,
    # so `SELECT version() FROM dataset` executed and returned the real
    # DuckDB version, and current_setting()/read_text() were reachable
    # the same way. sqlglot maps every standard SQL function to its own
    # class and falls back to exp.Anonymous for anything else — which is
    # exactly true of every one of these.
    with pytest.raises(InvalidQueryError, match="Function not allowed"):
        validate_and_prepare(sql, table_name="dataset", allowed_columns=COLUMNS, row_limit=10_000)


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT region, SUM(revenue) AS total FROM dataset GROUP BY region",
        "SELECT COUNT(*) FROM dataset",
        "SELECT UPPER(region) FROM dataset",
        "SELECT ROUND(revenue, 2) FROM dataset",
        "SELECT CASE WHEN revenue > 10 THEN 'x' ELSE 'y' END FROM dataset",
        "SELECT COALESCE(revenue, 0) FROM dataset",
    ],
)
def test_standard_sql_functions_still_pass(sql):
    # The exp.Anonymous check must not become an overzealous allowlist
    # that breaks the ordinary aggregate/string/date/math functions
    # NL-to-SQL and the SQL Explorer both need day to day.
    validate_and_prepare(sql, table_name="dataset", allowed_columns=COLUMNS, row_limit=10_000)


def test_oversized_limit_is_clamped_not_trusted():
    # The original `if stmt.args.get("limit") is None` only ever injected
    # a LIMIT when one was absent — a query that already specified its
    # own (e.g. an oversized one) sailed through completely unclamped.
    sql = validate_and_prepare(
        "SELECT region FROM dataset LIMIT 999999999",
        table_name="dataset", allowed_columns=COLUMNS, row_limit=100,
    )
    assert "LIMIT 100" in sql
    assert "999999999" not in sql


def test_limit_under_the_cap_is_left_alone():
    sql = validate_and_prepare(
        "SELECT region FROM dataset LIMIT 5",
        table_name="dataset", allowed_columns=COLUMNS, row_limit=100,
    )
    assert "LIMIT 5" in sql


def test_non_literal_limit_is_treated_as_unbounded_and_clamped():
    # LIMIT 1+1 is a real, if unusual, valid SQL expression — not an
    # integer literal this module can read directly. Failing safe here
    # means clamping it rather than letting an unparseable limit through
    # unbounded.
    sql = validate_and_prepare(
        "SELECT region FROM dataset LIMIT 1+1",
        table_name="dataset", allowed_columns=COLUMNS, row_limit=100,
    )
    assert "LIMIT 100" in sql
