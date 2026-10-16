"""insights can be saved from /analyze answers

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-17

/analyze answers come from several tool calls (or none), not one
structured query, so query_request/row_count become optional and the
answer's verified findings are stored instead. Additive: existing rows
keep their values.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("insights", "query_request", nullable=True)
    op.alter_column("insights", "row_count", nullable=True)
    op.add_column(
        "insights", sa.Column("findings", postgresql.JSONB(astext_type=sa.Text()), nullable=True)
    )


def downgrade() -> None:
    # Rows saved from /analyze have no query to restore; drop them first.
    op.execute("DELETE FROM insights WHERE query_request IS NULL")
    op.drop_column("insights", "findings")
    op.alter_column("insights", "row_count", nullable=False)
    op.alter_column("insights", "query_request", nullable=False)
