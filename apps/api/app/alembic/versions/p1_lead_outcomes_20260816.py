"""Add immutable lead outcome observations.

Revision ID: p1_lead_outcomes_20260816
Revises: p1_lead_preparation_jobs_20260816
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "p1_lead_outcomes_20260816"
down_revision = "p1_lead_preparation_jobs_20260816"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lead_outcome_observation",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.String(64), nullable=False),
        sa.Column("contact_id", sa.Uuid(), nullable=False),
        sa.Column("policy_id", sa.Uuid(), nullable=False),
        sa.Column("policy_version", sa.Integer(), nullable=False),
        sa.Column("outcome_type", sa.String(64), nullable=False),
        sa.Column("outcome_reference", sa.String(255), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["policy_id"], ["lead_scoring_policy.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id"], ["suite_tenant.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "workspace_id", "idempotency_key", name="uq_lead_outcome_observation_key"
        ),
    )
    for column in ("tenant_id", "workspace_id", "contact_id", "policy_id", "outcome_type"):
        op.create_index(
            f"ix_lead_outcome_observation_{column}", "lead_outcome_observation", [column]
        )


def downgrade() -> None:
    op.drop_table("lead_outcome_observation")
