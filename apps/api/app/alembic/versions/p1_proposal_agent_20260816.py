"""Add durable Proposal Agent orchestration.

Revision ID: p1_proposal_agent_20260816
Revises: p1_lead_outcomes_20260816
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "p1_proposal_agent_20260816"
down_revision = "p1_lead_outcomes_20260816"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "proposal_generation_job",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.String(64), nullable=False),
        sa.Column("deployment_id", sa.Uuid(), nullable=False),
        sa.Column("ecrm_cell_id", sa.String(128), nullable=False),
        sa.Column("client_account_id", sa.String(255), nullable=False),
        sa.Column("proposal_id", sa.String(255), nullable=False),
        sa.Column("mode", sa.String(32), nullable=False),
        sa.Column("command_key", sa.String(255), nullable=False),
        sa.Column("input_digest", sa.String(64), nullable=False),
        sa.Column("source_digest", sa.String(64), nullable=False),
        sa.Column("encrypted_request", sa.Text(), nullable=False),
        sa.Column("command_envelope", sa.JSON(), nullable=True),
        sa.Column("command_digest", sa.String(64), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_token", sa.Uuid(), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("command_attempted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("usage_reservation_id", sa.Uuid(), nullable=True),
        sa.Column("last_error_code", sa.String(64), nullable=True),
        sa.Column("last_error_detail", sa.String(1000), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["deployment_id"], ["agent_deployment.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["suite_tenant.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "workspace_id",
            "command_key",
            name="uq_proposal_job_command",
        ),
    )
    op.create_index(
        "ix_proposal_job_poll",
        "proposal_generation_job",
        ["status", "available_at", "created_at"],
    )
    for column in (
        "tenant_id",
        "workspace_id",
        "deployment_id",
        "ecrm_cell_id",
        "client_account_id",
        "proposal_id",
        "status",
        "available_at",
        "lease_token",
        "lease_expires_at",
        "usage_reservation_id",
    ):
        op.create_index(
            f"ix_proposal_generation_job_{column}",
            "proposal_generation_job",
            [column],
        )

    op.create_table(
        "proposal_generation_evidence",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.String(64), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("source_type", sa.String(64), nullable=False),
        sa.Column("source_reference", sa.String(255), nullable=False),
        sa.Column("source_digest", sa.String(64), nullable=False),
        sa.Column("permitted_use", sa.String(64), nullable=False),
        sa.Column("sensitivity", sa.String(32), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["job_id"], ["proposal_generation_job.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["suite_tenant.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "job_id",
            "source_reference",
            "source_digest",
            name="uq_proposal_evidence_source",
        ),
    )
    for column in ("tenant_id", "workspace_id", "job_id"):
        op.create_index(
            f"ix_proposal_generation_evidence_{column}",
            "proposal_generation_evidence",
            [column],
        )

    op.create_table(
        "proposal_generation_receipt",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.String(64), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("command_key", sa.String(255), nullable=False),
        sa.Column("ecrm_receipt_id", sa.String(255), nullable=False),
        sa.Column("ecrm_cell_id", sa.String(128), nullable=False),
        sa.Column("client_account_id", sa.String(255), nullable=False),
        sa.Column("proposal_id", sa.String(255), nullable=False),
        sa.Column("version_id", sa.String(255), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("content_digest", sa.String(64), nullable=False),
        sa.Column("artifact_digest", sa.String(64), nullable=True),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["job_id"], ["proposal_generation_job.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["suite_tenant.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", name="uq_proposal_receipt_job"),
        sa.UniqueConstraint(
            "workspace_id",
            "ecrm_receipt_id",
            name="uq_proposal_receipt_external",
        ),
    )
    for column in (
        "tenant_id",
        "workspace_id",
        "job_id",
        "command_key",
        "ecrm_cell_id",
        "client_account_id",
        "version_id",
    ):
        op.create_index(
            f"ix_proposal_generation_receipt_{column}",
            "proposal_generation_receipt",
            [column],
        )


def downgrade() -> None:
    op.drop_table("proposal_generation_receipt")
    op.drop_table("proposal_generation_evidence")
    op.drop_table("proposal_generation_job")
