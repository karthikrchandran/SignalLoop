"""add_contact_events_and_routing_decisions

Revision ID: b1c2d3e4f5a6
Revises: a0b1c2d3e4f5
Create Date: 2026-05-02 00:00:00.000000

Adds:
  - contact_events (immutable event store for contact lifecycle)
  - routing_decisions (automated routing decisions for explainability)
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

revision: str = "b1c2d3e4f5a6"
down_revision: str | None = "a0b1c2d3e4f5"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    existing = inspect(bind).get_table_names()

    if "contact_events" not in existing:
        op.create_table(
            "contact_events",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("contact_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("workspace_id", sa.String(64), nullable=False),
            sa.Column("event_type", sa.String(128), nullable=False),
            sa.Column("channel", sa.String(32), nullable=True),
            sa.Column("actor", sa.String(128), nullable=True),
            sa.Column("outcome", sa.String(128), nullable=True),
            sa.Column("reason_code", sa.String(255), nullable=True),
            sa.Column("rule_ref", sa.String(255), nullable=True),
            sa.Column("template_ref", sa.String(255), nullable=True),
            sa.Column("confidence_tier", sa.String(32), nullable=True),
            sa.Column("metadata", sa.JSON(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"]),
            sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("idx_ce_contact_campaign", "contact_events", ["contact_id", "campaign_id"])
        op.create_index("idx_ce_workspace_type", "contact_events", ["workspace_id", "event_type"])
        op.create_index("idx_ce_created_at", "contact_events", ["created_at"])

    if "routing_decisions" not in existing:
        op.create_table(
            "routing_decisions",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("contact_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("workspace_id", sa.String(64), nullable=False),
            sa.Column("decision_type", sa.String(128), nullable=False),
            sa.Column("outcome", sa.String(128), nullable=True),
            sa.Column("reason_code", sa.String(255), nullable=True),
            sa.Column("rule_name", sa.String(255), nullable=True),
            sa.Column("rule_condition", sa.Text(), nullable=True),
            sa.Column("signal_summary", sa.Text(), nullable=True),
            sa.Column("confidence_tier", sa.String(32), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"]),
            sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("idx_rd_contact_campaign", "routing_decisions", ["contact_id", "campaign_id"])
        op.create_index("idx_rd_workspace", "routing_decisions", ["workspace_id"])
        op.create_index("idx_rd_created_at", "routing_decisions", ["created_at"])


def downgrade() -> None:
    op.drop_index("idx_rd_created_at", table_name="routing_decisions")
    op.drop_index("idx_rd_workspace", table_name="routing_decisions")
    op.drop_index("idx_rd_contact_campaign", table_name="routing_decisions")
    op.drop_table("routing_decisions")

    op.drop_index("idx_ce_created_at", table_name="contact_events")
    op.drop_index("idx_ce_workspace_type", table_name="contact_events")
    op.drop_index("idx_ce_contact_campaign", table_name="contact_events")
    op.drop_table("contact_events")
