"""create monitors and anomalies tables

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-12

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
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
        "monitors",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("dataset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("metric_column", sa.String(length=255), nullable=False),
        sa.Column("aggregation", sa.String(length=16), nullable=False),
        sa.Column("time_column", sa.String(length=255), nullable=False),
        sa.Column("baseline_strategy", sa.String(length=32), nullable=False),
        sa.Column("baseline_window", sa.Integer(), nullable=False, server_default="7"),
        sa.Column("threshold_percent", sa.Float(), nullable=True),
        sa.Column("zscore_threshold", sa.Float(), nullable=True),
        sa.Column("check_frequency", sa.String(length=16), nullable=False, server_default="daily"),
        sa.Column("notify_email", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_status", sa.String(length=32), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        *_timestamp_columns(),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["dataset_id"], ["datasets.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_monitors_owner_id", "monitors", ["owner_id"])
    op.create_index("ix_monitors_dataset_id", "monitors", ["dataset_id"])

    op.create_table(
        "anomalies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("monitor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("dataset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("metric_column", sa.String(length=255), nullable=False),
        sa.Column("period_label", sa.String(length=64), nullable=False),
        sa.Column("observed_value", sa.Float(), nullable=False),
        sa.Column("baseline_value", sa.Float(), nullable=True),
        sa.Column("change_percent", sa.Float(), nullable=True),
        sa.Column("direction", sa.String(length=16), nullable=False),
        sa.Column("detection_method", sa.String(length=32), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("alert_sent", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("alert_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("alert_error", sa.Text(), nullable=True),
        *_timestamp_columns(),
        sa.ForeignKeyConstraint(["monitor_id"], ["monitors.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["dataset_id"], ["datasets.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_anomalies_monitor_id", "anomalies", ["monitor_id"])
    op.create_index("ix_anomalies_owner_id", "anomalies", ["owner_id"])
    op.create_index("ix_anomalies_dataset_id", "anomalies", ["dataset_id"])


def downgrade() -> None:
    op.drop_index("ix_anomalies_dataset_id", table_name="anomalies")
    op.drop_index("ix_anomalies_owner_id", table_name="anomalies")
    op.drop_index("ix_anomalies_monitor_id", table_name="anomalies")
    op.drop_table("anomalies")
    op.drop_index("ix_monitors_dataset_id", table_name="monitors")
    op.drop_index("ix_monitors_owner_id", table_name="monitors")
    op.drop_table("monitors")
