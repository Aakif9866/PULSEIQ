"""add dataset data-quality columns

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-12

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("datasets", sa.Column("duplicate_row_count", sa.Integer(), nullable=True))
    op.add_column("datasets", sa.Column("data_quality_score", sa.Float(), nullable=True))
    op.add_column("datasets", sa.Column("correlations", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("datasets", "correlations")
    op.drop_column("datasets", "data_quality_score")
    op.drop_column("datasets", "duplicate_row_count")
