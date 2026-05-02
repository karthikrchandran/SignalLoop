"""create_kpi_daily_snapshots

Revision ID: h3c4d5e6f7a8
Revises: g2b3c4d5e6f7, c1d2e3f4a5b6
Create Date: 2026-05-02 00:00:00.000000

Adds:
  - kpi_daily_snapshots: materialized daily KPI aggregation table
    Columns: date, workspace_id, campaign_id, contacts_processed,
             intent_signals, qualified_contacts, bookings_confirmed,
             provider_errors, booking_sla_met, booking_sla_breached
  - Indexes: (workspace_id, date) and (workspace_id, campaign_id, date)
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "h3c4d5e6f7a8"
down_revision: str | tuple[str, ...] | None = ("g2b3c4d5e6f7", "c1d2e3f4a5b6")
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.create_table(
        "kpi_daily_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("workspace_id", sa.String(length=64), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("contacts_processed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("intent_signals", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("qualified_contacts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("bookings_confirmed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("provider_errors", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("booking_sla_met", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("booking_sla_breached", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_kpi_snapshots_workspace_date",
        "kpi_daily_snapshots",
        ["workspace_id", "date"],
    )
    op.create_index(
        "idx_kpi_snapshots_workspace_campaign_date",
        "kpi_daily_snapshots",
        ["workspace_id", "campaign_id", "date"],
    )


def downgrade() -> None:
    op.drop_index("idx_kpi_snapshots_workspace_campaign_date", table_name="kpi_daily_snapshots")
    op.drop_index("idx_kpi_snapshots_workspace_date", table_name="kpi_daily_snapshots")
    op.drop_table("kpi_daily_snapshots")
