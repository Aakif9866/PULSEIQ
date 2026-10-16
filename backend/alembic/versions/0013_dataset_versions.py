"""dataset versions: refresh a dataset without losing its history

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-17

Additive. Every dataset gets a version number (existing ones start at 1)
and every uploaded file a dataset_versions row; existing datasets are
backfilled as their version 1 so history is complete from day one.
Insights record the version they were computed on (existing ones: 1).
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "datasets", sa.Column("version", sa.Integer(), nullable=False, server_default="1")
    )
    op.create_table(
        "dataset_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "dataset_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("datasets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=True),
        sa.Column("row_count", sa.Integer(), nullable=True),
        sa.Column("column_count", sa.Integer(), nullable=True),
        sa.Column("columns", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("schema_changes", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("dataset_id", "version"),
    )
    op.create_index("ix_dataset_versions_dataset_id", "dataset_versions", ["dataset_id"])
    # Every existing dataset becomes its own version 1.
    op.execute(
        """
        INSERT INTO dataset_versions (id, dataset_id, version, original_filename, size_bytes,
            storage_key, row_count, column_count, columns, created_at, updated_at)
        SELECT gen_random_uuid(), d.id, 1, d.original_filename, d.size_bytes, d.storage_key,
            d.row_count, d.column_count,
            (SELECT jsonb_agg(jsonb_build_object('name', c->>'name', 'dtype', c->>'dtype'))
               FROM jsonb_array_elements(COALESCE(d.columns_profile, '[]'::jsonb)) AS c),
            d.created_at, d.created_at
        FROM datasets d
        """
    )
    op.add_column("insights", sa.Column("dataset_version", sa.Integer(), nullable=True))
    op.execute("UPDATE insights SET dataset_version = 1")


def downgrade() -> None:
    op.drop_column("insights", "dataset_version")
    op.drop_index("ix_dataset_versions_dataset_id", table_name="dataset_versions")
    op.drop_table("dataset_versions")
    op.drop_column("datasets", "version")
