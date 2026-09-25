"""Validates AI-generated (or user-typed) SQL before it ever reaches DuckDB.

This is the one place in this codebase that takes a raw SQL string as
input — everywhere else (the structured query engine in
app/analytics/query_engine.py) only ever executes a closed Pydantic
schema. See docs/V2_ROADMAP.md's "Natural Language to SQL" section for why
this needs real parsing rather than a regex/keyword blocklist, and
docs/SECURITY.md's "Natural Language to SQL / SQL Explorer" section for
the full, audited threat model this implements:

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
    - Every function call must be a standard SQL function sqlglot itself
      recognizes (SUM, COUNT, LOWER, ROUND, CASE, COALESCE, STRFTIME,
      EXTRACT, ...) — never an unrecognized/DuckDB-specific one. Found
      live during the Phase 8 step 2 security audit (docs/BUGS.md): the
      table/column checks above have *no* coverage at all for a bare
      function call like `version()`, `current_database()`,
      `current_setting('x')` — none of those are an exp.Table or
      exp.Column node, so `SELECT version() FROM dataset` sailed through
      validation and DuckDB executed it, disclosing the engine version
      and in-memory DB name. sqlglot happens to represent every standard
      SQL function as its own named class (exp.Sum, exp.Lower, ...) and
      falls back to the generic exp.Anonymous for anything it doesn't
      recognize by name — which is exactly true of every DuckDB-specific
      or extension-provided function found during the audit
      (`version`, `current_database`, `current_setting`, the table
      function `read_text` when coerced into scalar position). Blocking
      exp.Anonymous outright closes this with no allowlist to maintain
      by hand — see `_validate_functions`.
    - A LIMIT is enforced server-side regardless of what the query itself
      requested — including *clamping down* an oversized one the query
      already specified, not just injecting one when absent (the
      audit found `SELECT * FROM dataset LIMIT 999999999` sailed through
      unclamped under the original `if ... is None` check).
    - The DuckDB connection itself is opened with
      `enable_external_access=false` (app/analytics/sql_engine.py) as a
      second, independent layer — even a function this validator hasn't
      anticipated can't touch the filesystem or network if DuckDB's own
      engine-level permission for that is off. Verified live: it doesn't
      break the registered `dataset` table (an in-memory Python object,
      not a file), but does independently block `read_csv`/`INSTALL`
      even if this validator were bypassed.
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
    _validate_functions(stmt)

    existing_limit = stmt.args.get("limit")
    requested = _literal_limit_value(existing_limit)
    # requested is None both when there's no LIMIT at all, and when there
    # is one but it isn't a plain integer literal (e.g. `LIMIT 5+5`) — an
    # unparseable limit is treated the same as "unbounded" and clamped,
    # never trusted, fail-safe rather than fail-open.
    if requested is None or requested > row_limit:
        stmt.set("limit", None)
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


def _validate_functions(stmt: exp.Select) -> None:
    """Rejects any function call sqlglot couldn't map to one of its own
    named expression classes (exp.Sum, exp.Lower, exp.Extract, ...) — see
    this module's docstring for exactly what this closes. No hand-
    maintained allowlist: sqlglot's own parser *is* the allowlist, since
    every standard SQL function it knows about already gets a specific
    class, and everything else — every DuckDB-specific or extension
    function, known or not yet discovered — falls back to exp.Anonymous."""
    for call in stmt.find_all(exp.Anonymous):
        name = call.this if isinstance(call.this, str) else call.sql_name()
        raise InvalidQueryError(f"Function not allowed: {name}")


def _literal_limit_value(limit: exp.Limit | None) -> int | None:
    if limit is None:
        return None
    expression = limit.expression
    if not isinstance(expression, exp.Literal) or not expression.is_int:
        return None
    try:
        return int(expression.this)
    except (TypeError, ValueError):
        return None
