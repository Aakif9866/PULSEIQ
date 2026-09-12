"""create query_history and saved_queries tables

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-12

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamp_columns() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "query_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("dataset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("question", sa.Text(), nullable=True),
        sa.Column("sql_text", sa.Text(), nullable=True),
        sa.Column("result_meta", postgresql.JSONB(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        *_timestamp_columns(),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["dataset_id"], ["datasets.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_query_history_owner_id", "query_history", ["owner_id"])
    op.create_index("ix_query_history_dataset_id", "query_history", ["dataset_id"])

    op.create_table(
        "saved_queries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("dataset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("sql_text", sa.Text(), nullable=False),
        *_timestamp_columns(),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["dataset_id"], ["datasets.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_saved_queries_owner_id", "saved_queries", ["owner_id"])
    op.create_index("ix_saved_queries_dataset_id", "saved_queries", ["dataset_id"])


def downgrade() -> None:
    op.drop_index("ix_saved_queries_dataset_id", table_name="saved_queries")
    op.drop_index("ix_saved_queries_owner_id", table_name="saved_queries")
    op.drop_table("saved_queries")
    op.drop_index("ix_query_history_dataset_id", table_name="query_history")
    op.drop_index("ix_query_history_owner_id", table_name="query_history")
    op.drop_table("query_history")
