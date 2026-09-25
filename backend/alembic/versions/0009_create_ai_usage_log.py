"""create ai_usage_log table

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-25

docs/PHASES.md Phase 8 step 4: per-user daily token quotas and a usage
page both need a persisted record of what each AI request actually cost.
Additive only — no existing table is altered.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_usage_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        # SET NULL, not CASCADE: deleting a dataset must not erase the
        # record of tokens already spent on it — that would let a user
        # reset their own quota by deleting and re-uploading.
        sa.Column("dataset_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("cache_hit", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("llm_calls", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completion_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("estimated_cost_usd", sa.Numeric(12, 6), nullable=True),
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
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["dataset_id"], ["datasets.id"], ondelete="SET NULL"),
    )
    # The quota check runs on every AI request: "sum this user's tokens
    # since the start of today" — this index is exactly that query.
    op.create_index(
        "ix_ai_usage_log_owner_id_created_at", "ai_usage_log", ["owner_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_ai_usage_log_owner_id_created_at", table_name="ai_usage_log")
    op.drop_table("ai_usage_log")
