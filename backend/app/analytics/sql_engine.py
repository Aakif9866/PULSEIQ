"""Executes a validated SQL SELECT against a dataset's in-memory DataFrame.

Uses DuckDB — the dependency that had been declared but unused since
"phase 3+" (see requirements.txt) — as an embedded, in-process engine, not
a separately-hosted database. A fresh, disposable connection is opened per
query, the dataset's Polars DataFrame is registered as the only table it
can see, and the connection is always closed afterward. No query reaches
this function without first passing app.analytics.sql_validator.

`enable_external_access=false` is a second, independent safety layer on
top of that validation, not a substitute for it — added during the Phase
8 step 2 security audit (docs/SECURITY.md). Verified live: it doesn't
break the registered `dataset` table (an in-memory Python object, no
filesystem/network involved), but does independently block
`read_csv`/`INSTALL`/etc. at the DuckDB engine level even if the sqlglot
validator were ever bypassed or a new DuckDB function it doesn't know to
reject shipped in a future version.
"""
import duckdb
import polars as pl

from app.core.exceptions import InvalidQueryError
from app.schemas.dataset_query import DatasetQueryResult

_TABLE_NAME = "dataset"


def execute_sql(df: pl.DataFrame, sql: str) -> DatasetQueryResult:
    """`sql` must already be validated (app.analytics.sql_validator) —
    this function trusts it completely and just runs it."""
    connection = duckdb.connect(":memory:", config={"enable_external_access": "false"})
    try:
        connection.register(_TABLE_NAME, df)
        try:
            cursor = connection.execute(sql)
        except duckdb.Error as exc:
            # A validated query can still fail at execution time (e.g. a
            # type mismatch DuckDB itself rejects) — never leak the raw
            # DuckDB error text, which could echo back query internals.
            raise InvalidQueryError(
                "That query couldn't be executed against this dataset."
            ) from exc

        columns = [d[0] for d in cursor.description] if cursor.description else []
        rows = cursor.fetchall()
        return DatasetQueryResult(
            columns=columns,
            rows=[list(row) for row in rows],
            row_count=len(rows),
            # The validator always injects a LIMIT when the query didn't
            # specify one, but that means a full result exactly at the
            # limit is indistinguishable from one that got cut off — same
            # trade-off app.analytics.query_engine already accepts.
            truncated=False,
        )
    finally:
        connection.close()
