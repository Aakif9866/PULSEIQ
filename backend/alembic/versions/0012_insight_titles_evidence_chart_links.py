"""insight titles and evidence; dashboard charts link to their insight

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-17

Additive only: insights gain an editable title and the tool calls behind
the answer (so they can be reopened and reported with real evidence);
dashboard charts gain an optional link to the insight they came from.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("insights", sa.Column("title", sa.String(length=255), nullable=True))
    op.add_column(
        "insights", sa.Column("tool_calls", postgresql.JSONB(astext_type=sa.Text()), nullable=True)
    )
    op.add_column(
        "dashboard_charts",
        sa.Column(
            "insight_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("insights.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("dashboard_charts", "insight_id")
    op.drop_column("insights", "tool_calls")
    op.drop_column("insights", "title")
