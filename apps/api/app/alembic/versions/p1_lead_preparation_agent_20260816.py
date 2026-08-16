"""Add versioned lead preparation policies and outputs.

Revision ID: p1_lead_preparation_agent_20260816
Revises: p1_commercial_agent_catalog_20260816
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "p1_lead_preparation_agent_20260816"
down_revision = "p1_commercial_agent_catalog_20260816"
branch_labels = None
depends_on = None


def _tenant_workspace_columns() -> list[sa.Column]:
    return [
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.String(64), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "lead_scoring_policy",
        sa.Column("id", sa.Uuid(), nullable=False),
        *_tenant_workspace_columns(),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("feature_weights", sa.JSON(), nullable=False),
        sa.Column("band_thresholds", sa.JSON(), nullable=False),
        sa.Column("freshness_windows", sa.JSON(), nullable=False),
        sa.Column("exclusion_rules", sa.JSON(), nullable=False),
        sa.Column("policy_digest", sa.String(64), nullable=False),
        sa.Column("approved_by", sa.Uuid(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["suite_tenant.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "workspace_id", "version", name="uq_lead_scoring_policy_version"
        ),
    )
    op.create_index("ix_lead_scoring_policy_tenant_id", "lead_scoring_policy", ["tenant_id"])
    op.create_index("ix_lead_scoring_policy_workspace_id", "lead_scoring_policy", ["workspace_id"])
    op.create_index("ix_lead_scoring_policy_status", "lead_scoring_policy", ["status"])

    op.create_table(
        "lead_evidence_item",
        sa.Column("id", sa.Uuid(), nullable=False),
        *_tenant_workspace_columns(),
        sa.Column("contact_id", sa.Uuid(), nullable=False),
        sa.Column("source_type", sa.String(64), nullable=False),
        sa.Column("source_reference", sa.String(2048), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("content_digest", sa.String(64), nullable=False),
        sa.Column("sensitivity", sa.String(32), nullable=False),
        sa.Column("freshness", sa.String(32), nullable=False),
        sa.Column("confidence", sa.String(32), nullable=False),
        sa.Column("redacted_excerpt", sa.String(2000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["suite_tenant.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "workspace_id",
            "contact_id",
            "source_type",
            "source_reference",
            "content_digest",
            name="uq_lead_evidence_source_digest",
        ),
    )
    for column in ("tenant_id", "workspace_id", "contact_id"):
        op.create_index(f"ix_lead_evidence_item_{column}", "lead_evidence_item", [column])

    op.create_table(
        "lead_score_version",
        sa.Column("id", sa.Uuid(), nullable=False),
        *_tenant_workspace_columns(),
        sa.Column("agent_deployment_id", sa.Uuid(), nullable=False),
        sa.Column("contact_id", sa.Uuid(), nullable=False),
        sa.Column("policy_id", sa.Uuid(), nullable=False),
        sa.Column("policy_version", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("band", sa.String(32), nullable=False),
        sa.Column("feature_vector", sa.JSON(), nullable=False),
        sa.Column("contributions", sa.JSON(), nullable=False),
        sa.Column("reasons", sa.JSON(), nullable=False),
        sa.Column("negative_factors", sa.JSON(), nullable=False),
        sa.Column("exclusions", sa.JSON(), nullable=False),
        sa.Column("channel_eligibility", sa.JSON(), nullable=False),
        sa.Column("evidence_digest", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["agent_deployment_id"], ["agent_deployment.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["policy_id"], ["lead_scoring_policy.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id"], ["suite_tenant.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "workspace_id", "contact_id", "version", name="uq_lead_score_contact_version"
        ),
    )
    for column in ("tenant_id", "workspace_id", "agent_deployment_id", "contact_id", "band"):
        op.create_index(f"ix_lead_score_version_{column}", "lead_score_version", [column])
    op.create_index(
        "ix_lead_score_workspace_band", "lead_score_version", ["workspace_id", "band"]
    )

    op.create_table(
        "lead_preparation_package",
        sa.Column("id", sa.Uuid(), nullable=False),
        *_tenant_workspace_columns(),
        sa.Column("agent_deployment_id", sa.Uuid(), nullable=False),
        sa.Column("contact_id", sa.Uuid(), nullable=False),
        sa.Column("score_version_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("brief", sa.JSON(), nullable=False),
        sa.Column("next_action", sa.JSON(), nullable=False),
        sa.Column("draft_references", sa.JSON(), nullable=False),
        sa.Column("review_state", sa.String(32), nullable=False),
        sa.Column("content_digest", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["agent_deployment_id"], ["agent_deployment.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["score_version_id"], ["lead_score_version.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id"], ["suite_tenant.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "workspace_id",
            "contact_id",
            "version",
            name="uq_lead_preparation_contact_version",
        ),
    )
    for column in (
        "tenant_id",
        "workspace_id",
        "agent_deployment_id",
        "contact_id",
        "review_state",
    ):
        op.create_index(
            f"ix_lead_preparation_package_{column}", "lead_preparation_package", [column]
        )


def downgrade() -> None:
    op.drop_table("lead_preparation_package")
    op.drop_table("lead_score_version")
    op.drop_table("lead_evidence_item")
    op.drop_table("lead_scoring_policy")
