"""Add governance controls tables

Revision ID: d4e5f6a7b8c9
Revises: c3d9f4a8e271
Create Date: 2026-04-01 15:10:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "d4e5f6a7b8c9"
down_revision = "c3d9f4a8e271"
branch_labels = None
depends_on = None


policy_type_enum = postgresql.ENUM(
    "daily_caps",
    "quiet_hours",
    "suppression",
    "approval_rule",
    name="policytype",
    create_type=False,
)
policy_status_enum = postgresql.ENUM(
    "active",
    "inactive",
    name="policystatus",
    create_type=False,
)
approval_status_enum = postgresql.ENUM(
    "pending",
    "approved",
    "rejected",
    name="approvalstatus",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    policy_type_enum.create(bind, checkfirst=True)
    policy_status_enum.create(bind, checkfirst=True)
    approval_status_enum.create(bind, checkfirst=True)

    op.create_table(
        "governance_policies",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", sa.String(length=64), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("scope", sa.String(length=32), nullable=False),
        sa.Column("policy_type", policy_type_enum, nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("status", policy_status_enum, nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_governance_policies_workspace_id"), "governance_policies", ["workspace_id"], unique=False)
    op.create_index(
        "ix_governance_policies_workspace_campaign_status",
        "governance_policies",
        ["workspace_id", "campaign_id", "status"],
        unique=False,
    )

    op.create_table(
        "campaign_policy_bindings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("policy_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"]),
        sa.ForeignKeyConstraint(["policy_id"], ["governance_policies.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_campaign_policy_bindings_campaign_id"), "campaign_policy_bindings", ["campaign_id"], unique=False)
    op.create_index(op.f("ix_campaign_policy_bindings_policy_id"), "campaign_policy_bindings", ["policy_id"], unique=False)

    op.create_table(
        "policy_approval_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", sa.String(length=64), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("requested_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("requested_action", sa.Text(), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("status", approval_status_enum, nullable=False, server_default="pending"),
        sa.Column("approved_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("actor_role", sa.String(length=32), nullable=False, server_default="operator"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_policy_approval_requests_workspace_id"), "policy_approval_requests", ["workspace_id"], unique=False)
    op.create_index(
        "ix_policy_approval_requests_workspace_campaign_status",
        "policy_approval_requests",
        ["workspace_id", "campaign_id", "status"],
        unique=False,
    )

    op.create_table(
        "global_control_state",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", sa.String(length=64), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("paused", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("paused_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("paused_reason", sa.String(length=255), nullable=True),
        sa.Column("paused_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_global_control_state_workspace_id"), "global_control_state", ["workspace_id"], unique=False)
    op.create_index(
        "ix_global_control_state_workspace_campaign_paused",
        "global_control_state",
        ["workspace_id", "campaign_id", "paused"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_global_control_state_workspace_campaign_paused", table_name="global_control_state")
    op.drop_index(op.f("ix_global_control_state_workspace_id"), table_name="global_control_state")
    op.drop_table("global_control_state")

    op.drop_index("ix_policy_approval_requests_workspace_campaign_status", table_name="policy_approval_requests")
    op.drop_index(op.f("ix_policy_approval_requests_workspace_id"), table_name="policy_approval_requests")
    op.drop_table("policy_approval_requests")

    op.drop_index(op.f("ix_campaign_policy_bindings_policy_id"), table_name="campaign_policy_bindings")
    op.drop_index(op.f("ix_campaign_policy_bindings_campaign_id"), table_name="campaign_policy_bindings")
    op.drop_table("campaign_policy_bindings")

    op.drop_index("ix_governance_policies_workspace_campaign_status", table_name="governance_policies")
    op.drop_index(op.f("ix_governance_policies_workspace_id"), table_name="governance_policies")
    op.drop_table("governance_policies")

    approval_status_enum.drop(op.get_bind(), checkfirst=True)
    policy_status_enum.drop(op.get_bind(), checkfirst=True)
    policy_type_enum.drop(op.get_bind(), checkfirst=True)
