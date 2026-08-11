"""add durable RevenueOS outcomes and operator transitions

Revision ID: p1_revenue_outcomes_20260811
Revises: p1_revenue_action_payload_20260810
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "p1_revenue_outcomes_20260811"
down_revision: str | None = "p1_revenue_action_payload_20260810"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    """Persist idempotent operator decisions and append-only intervention outcomes."""
    op.create_table(
        "revenue_intervention_transition",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("intervention_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("actor_id", sa.String(length=255), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["suite_tenant.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["intervention_id"], ["revenue_intervention_record.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "idempotency_key", name="uq_revenue_transition_tenant_key"
        ),
    )
    op.create_index(
        "ix_revenue_intervention_transition_tenant_id",
        "revenue_intervention_transition",
        ["tenant_id"],
    )
    op.create_index(
        "ix_revenue_intervention_transition_intervention_id",
        "revenue_intervention_transition",
        ["intervention_id"],
    )
    op.create_table(
        "revenue_intervention_outcome",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("intervention_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("evidence_refs", sa.JSON(), nullable=False),
        sa.Column("actor_id", sa.String(length=255), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["suite_tenant.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["intervention_id"], ["revenue_intervention_record.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "idempotency_key", name="uq_revenue_outcome_tenant_key"
        ),
    )
    op.create_index(
        "ix_revenue_intervention_outcome_tenant_id",
        "revenue_intervention_outcome",
        ["tenant_id"],
    )
    op.create_index(
        "ix_revenue_intervention_outcome_intervention_id",
        "revenue_intervention_outcome",
        ["intervention_id"],
    )


def downgrade() -> None:
    """Remove durable intervention outcomes and operator decisions."""
    op.drop_index(
        "ix_revenue_intervention_outcome_intervention_id",
        table_name="revenue_intervention_outcome",
    )
    op.drop_index(
        "ix_revenue_intervention_outcome_tenant_id",
        table_name="revenue_intervention_outcome",
    )
    op.drop_table("revenue_intervention_outcome")
    op.drop_index(
        "ix_revenue_intervention_transition_intervention_id",
        table_name="revenue_intervention_transition",
    )
    op.drop_index(
        "ix_revenue_intervention_transition_tenant_id",
        table_name="revenue_intervention_transition",
    )
    op.drop_table("revenue_intervention_transition")
