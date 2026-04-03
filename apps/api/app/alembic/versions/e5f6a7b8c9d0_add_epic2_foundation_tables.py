"""add_epic2_foundation_tables

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-04-01 00:00:00.000000

Adds:
  - contacts
  - contact_progression  (state machine state per contact×campaign)
  - contact_state_history (audit trail of state transitions)
  - outbox_events         (transactional outbox for reliable event publishing)
  - action_queue          (work items for the delivery pipeline)
  - provider_credentials  (per-workspace provider API keys, stored encrypted)
  - provider_event_logs   (normalised inbound webhook events from providers)

Also adds missing composite indexes on existing tables:
  - campaigns(workspace_id, status)
  - campaigns(workspace_id, created_by)
  - policy_approval_requests(workspace_id, status)
  - governance_policies(campaign_id)
  - global_control_state(campaign_id)
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: str | None = "d4e5f6a7b8c9"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # contacts
    # ------------------------------------------------------------------
    op.create_table(
        "contacts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.String(64), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("first_name", sa.String(255), nullable=True),
        sa.Column("last_name", sa.String(255), nullable=True),
        sa.Column("company", sa.String(255), nullable=True),
        sa.Column("timezone", sa.String(64), nullable=False, server_default="UTC"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_contacts_workspace_id", "contacts", ["workspace_id"])
    op.create_index("idx_contacts_email", "contacts", ["email"])

    # ------------------------------------------------------------------
    # contact_progression
    # ------------------------------------------------------------------
    op.create_table(
        "contact_progression",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("contact_id", sa.Uuid(), nullable=False),
        sa.Column("campaign_id", sa.Uuid(), nullable=False),
        sa.Column("current_state", sa.String(64), nullable=False),
        sa.Column("last_action_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"]),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "contact_id", "campaign_id",
            name="uq_contact_progression_contact_campaign",
        ),
    )
    op.create_index("idx_contact_prog_contact_id", "contact_progression", ["contact_id"])
    op.create_index("idx_contact_prog_campaign_id", "contact_progression", ["campaign_id"])

    # ------------------------------------------------------------------
    # contact_state_history
    # ------------------------------------------------------------------
    op.create_table(
        "contact_state_history",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("contact_id", sa.Uuid(), nullable=False),
        sa.Column("campaign_id", sa.Uuid(), nullable=False),
        sa.Column("from_state", sa.String(64), nullable=False),
        sa.Column("to_state", sa.String(64), nullable=False),
        sa.Column("reason", sa.String(255), nullable=True),
        sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"]),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_state_history_contact_id", "contact_state_history", ["contact_id"])
    op.create_index("idx_state_history_campaign_id", "contact_state_history", ["campaign_id"])

    # ------------------------------------------------------------------
    # outbox_events
    # ------------------------------------------------------------------
    op.create_table(
        "outbox_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("aggregate_id", sa.Uuid(), nullable=False),
        sa.Column("aggregate_type", sa.String(64), nullable=False),
        sa.Column("event_type", sa.String(128), nullable=False),
        sa.Column("event_data", sa.JSON(), nullable=False),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", name="uq_outbox_idempotency_key"),
    )
    op.create_index("idx_outbox_aggregate_id", "outbox_events", ["aggregate_id"])
    op.create_index("idx_outbox_idempotency_key", "outbox_events", ["idempotency_key"])
    op.create_index(
        "idx_outbox_unpublished",
        "outbox_events",
        ["published_at", "created_at"],
        postgresql_where=sa.text("published_at IS NULL"),
    )

    # ------------------------------------------------------------------
    # action_queue
    # ------------------------------------------------------------------
    op.create_table(
        "action_queue",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("contact_id", sa.Uuid(), nullable=False),
        sa.Column("campaign_id", sa.Uuid(), nullable=False),
        sa.Column("action_type", sa.String(64), nullable=False),
        sa.Column("channel", sa.String(32), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"]),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_action_queue_contact_id", "action_queue", ["contact_id"])
    op.create_index("idx_action_queue_campaign_id", "action_queue", ["campaign_id"])
    op.create_index("idx_action_queue_status", "action_queue", ["status"])
    op.create_index("idx_action_queue_next_retry_at", "action_queue", ["next_retry_at"])

    # ------------------------------------------------------------------
    # provider_credentials
    # ------------------------------------------------------------------
    op.create_table(
        "provider_credentials",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.String(64), nullable=False),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("channel", sa.String(32), nullable=False),
        sa.Column("encrypted_api_key", sa.Text(), nullable=False),
        sa.Column("encrypted_api_secret", sa.Text(), nullable=True),
        sa.Column("config_json", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_provider_cred_workspace_id", "provider_credentials", ["workspace_id"])
    op.create_index(
        "idx_provider_cred_workspace_provider",
        "provider_credentials",
        ["workspace_id", "provider"],
    )

    # ------------------------------------------------------------------
    # provider_event_logs
    # ------------------------------------------------------------------
    op.create_table(
        "provider_event_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.String(64), nullable=False),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("provider_event_id", sa.String(255), nullable=False),
        sa.Column("event_type", sa.String(128), nullable=False),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column("normalized_event", sa.JSON(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_provider_event_workspace_id", "provider_event_logs", ["workspace_id"])
    op.create_index(
        "idx_provider_event_provider_event_id",
        "provider_event_logs",
        ["provider_event_id"],
    )

    # ------------------------------------------------------------------
    # Composite indexes on existing tables
    # ------------------------------------------------------------------
    op.create_index(
        "idx_campaign_workspace_status", "campaigns", ["workspace_id", "status"]
    )
    op.create_index(
        "idx_campaign_workspace_created_by", "campaigns", ["workspace_id", "created_by"]
    )
    op.create_index(
        "idx_approval_workspace_status",
        "policy_approval_requests",
        ["workspace_id", "status"],
    )
    op.create_index(
        "idx_governance_policy_campaign_id", "governance_policies", ["campaign_id"]
    )
    op.create_index(
        "idx_global_control_campaign_id", "global_control_state", ["campaign_id"]
    )


def downgrade() -> None:
    op.drop_index("idx_global_control_campaign_id", "global_control_state")
    op.drop_index("idx_governance_policy_campaign_id", "governance_policies")
    op.drop_index("idx_approval_workspace_status", "policy_approval_requests")
    op.drop_index("idx_campaign_workspace_created_by", "campaigns")
    op.drop_index("idx_campaign_workspace_status", "campaigns")

    op.drop_table("provider_event_logs")

    op.drop_index("idx_provider_cred_workspace_provider", "provider_credentials")
    op.drop_index("idx_provider_cred_workspace_id", "provider_credentials")
    op.drop_table("provider_credentials")

    op.drop_index("idx_action_queue_next_retry_at", "action_queue")
    op.drop_index("idx_action_queue_status", "action_queue")
    op.drop_index("idx_action_queue_campaign_id", "action_queue")
    op.drop_index("idx_action_queue_contact_id", "action_queue")
    op.drop_table("action_queue")

    op.drop_index("idx_outbox_unpublished", "outbox_events")
    op.drop_index("idx_outbox_idempotency_key", "outbox_events")
    op.drop_index("idx_outbox_aggregate_id", "outbox_events")
    op.drop_table("outbox_events")

    op.drop_index("idx_state_history_campaign_id", "contact_state_history")
    op.drop_index("idx_state_history_contact_id", "contact_state_history")
    op.drop_table("contact_state_history")

    op.drop_index("idx_contact_prog_campaign_id", "contact_progression")
    op.drop_index("idx_contact_prog_contact_id", "contact_progression")
    op.drop_table("contact_progression")

    op.drop_index("idx_contacts_email", "contacts")
    op.drop_index("idx_contacts_workspace_id", "contacts")
    op.drop_table("contacts")
