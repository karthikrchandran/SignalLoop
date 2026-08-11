"""add durable RevenueOS interventions

Revision ID: p1_revenue_interventions_20260810
Revises: p1_projection_attempts_20260810
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "p1_revenue_interventions_20260810"
down_revision: str | None = "p1_projection_attempts_20260810"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    """Persist signals, governed interventions, and restart-safe dispatch rows."""
    op.create_table(
        "revenue_signal_record",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("signal_type", sa.String(length=128), nullable=False),
        sa.Column("subject_ref", sa.String(length=255), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("evidence_refs", sa.JSON(), nullable=False),
        sa.Column("evidence_hash", sa.String(length=255), nullable=False),
        sa.Column("source", sa.String(length=128), nullable=False),
        sa.Column("consent_verified", sa.Boolean(), nullable=False),
        sa.Column("policy_allowed", sa.Boolean(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["suite_tenant.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "idempotency_key", name="uq_revenue_signal_tenant_key"),
    )
    op.create_index("ix_revenue_signal_record_tenant_id", "revenue_signal_record", ["tenant_id"])
    op.create_table(
        "revenue_intervention_record",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("signal_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("evidence_refs", sa.JSON(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("denial_reason", sa.String(length=255), nullable=True),
        sa.Column("approved_by", sa.String(length=255), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["signal_id"], ["revenue_signal_record.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id"], ["suite_tenant.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "idempotency_key", name="uq_revenue_intervention_tenant_key"),
    )
    op.create_index("ix_revenue_intervention_record_tenant_id", "revenue_intervention_record", ["tenant_id"])
    op.create_index("ix_revenue_intervention_record_signal_id", "revenue_intervention_record", ["signal_id"])
    op.create_index("ix_revenue_intervention_record_status", "revenue_intervention_record", ["status"])
    op.create_table(
        "revenue_intervention_dispatch",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("intervention_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provider", sa.String(length=128), nullable=True),
        sa.Column("provider_receipt", sa.JSON(), nullable=True),
        sa.Column("dead_letter_reason", sa.String(length=1000), nullable=True),
        sa.Column("last_error", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["intervention_id"], ["revenue_intervention_record.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["suite_tenant.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("intervention_id", name="uq_revenue_dispatch_intervention"),
    )
    op.create_index("ix_revenue_intervention_dispatch_tenant_id", "revenue_intervention_dispatch", ["tenant_id"])
    op.create_index("ix_revenue_intervention_dispatch_intervention_id", "revenue_intervention_dispatch", ["intervention_id"])
    op.create_index("ix_revenue_intervention_dispatch_status", "revenue_intervention_dispatch", ["status"])


def downgrade() -> None:
    """Remove durable RevenueOS intervention tables."""
    op.drop_index("ix_revenue_intervention_dispatch_status", table_name="revenue_intervention_dispatch")
    op.drop_index("ix_revenue_intervention_dispatch_intervention_id", table_name="revenue_intervention_dispatch")
    op.drop_index("ix_revenue_intervention_dispatch_tenant_id", table_name="revenue_intervention_dispatch")
    op.drop_table("revenue_intervention_dispatch")
    op.drop_index("ix_revenue_intervention_record_status", table_name="revenue_intervention_record")
    op.drop_index("ix_revenue_intervention_record_signal_id", table_name="revenue_intervention_record")
    op.drop_index("ix_revenue_intervention_record_tenant_id", table_name="revenue_intervention_record")
    op.drop_table("revenue_intervention_record")
    op.drop_index("ix_revenue_signal_record_tenant_id", table_name="revenue_signal_record")
    op.drop_table("revenue_signal_record")
