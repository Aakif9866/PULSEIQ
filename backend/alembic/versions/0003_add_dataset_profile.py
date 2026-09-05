"""add dataset profiling columns

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-05

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("datasets", sa.Column("row_count", sa.Integer(), nullable=True))
    op.add_column("datasets", sa.Column("column_count", sa.Integer(), nullable=True))
    # One entry per column: {"name": str, "dtype": str, "null_count": int}.
    op.add_column("datasets", sa.Column("columns_profile", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("datasets", "columns_profile")
    op.drop_column("datasets", "column_count")
    op.drop_column("datasets", "row_count")
