"""Add durable autonomous lead preparation jobs.

Revision ID: p1_lead_preparation_jobs_20260816
Revises: p1_lead_preparation_agent_20260816
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "p1_lead_preparation_jobs_20260816"
down_revision = "p1_lead_preparation_agent_20260816"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lead_preparation_job",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.String(64), nullable=False),
        sa.Column("deployment_id", sa.Uuid(), nullable=False),
        sa.Column("contact_id", sa.Uuid(), nullable=False),
        sa.Column("policy_id", sa.Uuid(), nullable=False),
        sa.Column("event_key", sa.String(255), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_token", sa.Uuid(), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("usage_reservation_id", sa.Uuid(), nullable=True),
        sa.Column("score_version_id", sa.Uuid(), nullable=True),
        sa.Column("package_id", sa.Uuid(), nullable=True),
        sa.Column("last_error_code", sa.String(64), nullable=True),
        sa.Column("last_error_detail", sa.String(1000), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["deployment_id"], ["agent_deployment.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["package_id"], ["lead_preparation_package.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["policy_id"], ["lead_scoring_policy.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["score_version_id"], ["lead_score_version.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["suite_tenant.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["usage_reservation_id"], ["agent_usage_ledger.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "workspace_id", "event_key", name="uq_lead_preparation_job_event"
        ),
    )
    for column in (
        "tenant_id",
        "workspace_id",
        "deployment_id",
        "contact_id",
        "status",
        "available_at",
        "lease_token",
        "lease_expires_at",
        "usage_reservation_id",
        "score_version_id",
        "package_id",
    ):
        op.create_index(f"ix_lead_preparation_job_{column}", "lead_preparation_job", [column])
    op.create_index(
        "ix_lead_preparation_job_poll",
        "lead_preparation_job",
        ["status", "available_at", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("lead_preparation_job")
