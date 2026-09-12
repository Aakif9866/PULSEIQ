"""Validates AI-generated (or user-typed) SQL before it ever reaches DuckDB.

This is the one place in this codebase that takes a raw SQL string as
input — everywhere else (the structured query engine in
app/analytics/query_engine.py) only ever executes a closed Pydantic
schema. See docs/V2_ROADMAP.md's "Natural Language to SQL" section for why
this needs real parsing rather than a regex/keyword blocklist:

    - A single `SELECT` statement only. Multi-statement input
      (`SELECT 1; DROP TABLE x`), and every non-SELECT statement type
      (INSERT/UPDATE/DELETE/DROP/CREATE/ALTER/ATTACH/COPY/PRAGMA/...), is
      rejected by construction — sqlglot parses each into its own
      expression type, and only exp.Select is ever allowed through.
    - Every table reference must be exactly the single registered view
      name. This also catches function-based table sources
      (`read_csv(...)`, `read_parquet(...)`, an unknown function call) —
      sqlglot parses those as a Table node with an empty `.name`, which
      never matches the allow-listed name, so they're rejected the same
      way an unknown real table would be. CTEs are deliberately not
      supported for the same reason (a CTE alias also shows up as a
      "table" name that isn't the registered one) — a known MVP
      limitation, not an oversight.
    - Every column reference must be a real column in the dataset's
      schema, or an alias defined in this query's own SELECT list.
    - A LIMIT is enforced server-side regardless of what the query itself
      requested.
"""
import sqlglot
from sqlglot import exp

from app.core.exceptions import InvalidQueryError

_DIALECT = "duckdb"


def validate_and_prepare(
    sql: str, *, table_name: str, allowed_columns: set[str], row_limit: int
) -> str:
    """Returns a rewritten, safe-to-execute SQL string, or raises
    InvalidQueryError with a message safe to show the user."""
    try:
        statements = sqlglot.parse(sql, read=_DIALECT)
    except Exception as exc:
        raise InvalidQueryError(f"That query isn't valid SQL: {exc}") from exc

    statements = [s for s in statements if s is not None]
    if len(statements) != 1:
        raise InvalidQueryError("Only a single SELECT statement is allowed.")

    stmt = statements[0]
    if not isinstance(stmt, exp.Select):
        raise InvalidQueryError("Only SELECT statements are allowed.")

    _validate_tables(stmt, table_name)
    _validate_columns(stmt, allowed_columns)

    if stmt.args.get("limit") is None:
        stmt = stmt.limit(row_limit)

    return stmt.sql(dialect=_DIALECT)


def _validate_tables(stmt: exp.Select, table_name: str) -> None:
    tables = list(stmt.find_all(exp.Table))
    if not tables:
        raise InvalidQueryError("Query must select from the dataset.")
    for table in tables:
        if table.name.lower() != table_name.lower():
            raise InvalidQueryError(
                "Query may only reference the dataset itself — no other tables, "
                "files, or functions may be used as a data source."
            )


def _validate_columns(stmt: exp.Select, allowed_columns: set[str]) -> None:
    known = {c.lower() for c in allowed_columns}
    # Aliases defined anywhere in the query (e.g. `SUM(x) AS total` in the
    # outer SELECT, or an inner alias defined inside a subquery and
    # referenced by an enclosing scope) are legitimate to reference even
    # though they aren't real dataset columns. Collected query-wide rather
    # than scope-by-scope — slightly looser than perfectly scope-correct,
    # but this check exists for a clean "unknown column" error message,
    # not as a security boundary (that's _validate_tables, which stays
    # strict); a real mismatch DuckDB itself still catches at execution.
    for select in stmt.find_all(exp.Select):
        for projection in select.expressions:
            if isinstance(projection, exp.Alias):
                known.add(projection.alias.lower())

    for column in stmt.find_all(exp.Column):
        if column.name.lower() not in known:
            raise InvalidQueryError(f"Unknown column: {column.name}")
