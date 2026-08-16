"""Add durable lead-policy evaluation and approval evidence.

Revision ID: p1_lead_governance_20260816
Revises: p1_calendar_lifecycle_20260816
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "p1_lead_governance_20260816"
down_revision = "p1_calendar_lifecycle_20260816"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "lead_scoring_policy", sa.Column("created_by", sa.Uuid(), nullable=True)
    )
    op.create_index(
        "ix_lead_scoring_policy_created_by", "lead_scoring_policy", ["created_by"]
    )
    op.create_table(
        "lead_policy_evaluation_evidence",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.String(64), nullable=False),
        sa.Column("contact_id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("policy_digest", sa.String(64), nullable=False),
        sa.Column("input_digest", sa.String(64), nullable=False),
        sa.Column("result_digest", sa.String(64), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["suite_tenant.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("tenant_id", "workspace_id", "contact_id", "actor_id", "policy_digest"):
        op.create_index(
            f"ix_lead_policy_evaluation_evidence_{column}",
            "lead_policy_evaluation_evidence",
            [column],
        )
    op.create_table(
        "lead_policy_change_evidence",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.String(64), nullable=False),
        sa.Column("policy_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("from_status", sa.String(32), nullable=True),
        sa.Column("to_status", sa.String(32), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("actor_role", sa.String(64), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("policy_digest", sa.String(64), nullable=False),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["policy_id"], ["lead_scoring_policy.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["suite_tenant.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "workspace_id",
            "policy_id",
            "action",
            "idempotency_key",
            name="uq_lead_policy_change_evidence_key",
        ),
    )
    for column in ("tenant_id", "workspace_id", "policy_id", "action", "actor_id"):
        op.create_index(
            f"ix_lead_policy_change_evidence_{column}",
            "lead_policy_change_evidence",
            [column],
        )


def downgrade() -> None:
    op.drop_table("lead_policy_change_evidence")
    op.drop_table("lead_policy_evaluation_evidence")
    op.drop_index("ix_lead_scoring_policy_created_by", table_name="lead_scoring_policy")
    op.drop_column("lead_scoring_policy", "created_by")
