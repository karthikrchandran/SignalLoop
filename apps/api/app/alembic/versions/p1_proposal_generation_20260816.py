"""Add governed proposal reviews and email handoffs.

Revision ID: p1_proposal_generation_20260816
Revises: p1_proposal_agent_20260816
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "p1_proposal_generation_20260816"
down_revision = "p1_proposal_agent_20260816"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "proposal_grounding_source",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.String(64), nullable=False),
        sa.Column("reference", sa.String(255), nullable=False),
        sa.Column("source_digest", sa.String(64), nullable=False),
        sa.Column("allowed_claim_types", sa.JSON(), nullable=False),
        sa.Column("allowed_claim_digests", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("published_by", sa.Uuid(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["suite_tenant.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "workspace_id",
            "reference",
            name="uq_proposal_grounding_source_reference",
        ),
    )
    for column in ("tenant_id", "workspace_id", "status"):
        op.create_index(
            f"ix_proposal_grounding_source_{column}",
            "proposal_grounding_source",
            [column],
        )

    op.create_table(
        "proposal_draft_review",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.String(64), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("prompt_version", sa.String(128), nullable=False),
        sa.Column("model_id", sa.String(255), nullable=False),
        sa.Column("draft_digest", sa.String(64), nullable=False),
        sa.Column("evidence_map", sa.JSON(), nullable=False),
        sa.Column("review_state", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["job_id"], ["proposal_generation_job.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["suite_tenant.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", name="uq_proposal_draft_review_job"),
    )
    for column in ("tenant_id", "workspace_id", "job_id", "review_state"):
        op.create_index(
            f"ix_proposal_draft_review_{column}",
            "proposal_draft_review",
            [column],
        )

    op.create_table(
        "proposal_email_handoff",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.String(64), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("email_deployment_id", sa.Uuid(), nullable=False),
        sa.Column("version_id", sa.String(255), nullable=False),
        sa.Column("content_digest", sa.String(64), nullable=False),
        sa.Column("approval_id", sa.String(255), nullable=False),
        sa.Column("approved_by", sa.String(255), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["email_deployment_id"], ["agent_deployment.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["job_id"], ["proposal_generation_job.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["suite_tenant.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "job_id", "version_id", name="uq_proposal_email_handoff_version"
        ),
    )
    for column in (
        "tenant_id",
        "workspace_id",
        "job_id",
        "email_deployment_id",
        "status",
    ):
        op.create_index(
            f"ix_proposal_email_handoff_{column}",
            "proposal_email_handoff",
            [column],
        )


def downgrade() -> None:
    op.drop_table("proposal_email_handoff")
    op.drop_table("proposal_draft_review")
    op.drop_table("proposal_grounding_source")
