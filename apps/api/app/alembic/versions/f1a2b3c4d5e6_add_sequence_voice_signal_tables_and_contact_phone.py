"""add_sequence_voice_signal_tables_and_contact_phone

Revision ID: f1a2b3c4d5e6
Revises: e5f6a7b8c9d0
Create Date: 2026-04-02 00:00:00.000000

Adds:
  - phone column to contacts
  - email_sequences
  - sequence_steps
  - contact_sequence_state
  - send_requests
  - email_events
  - voice_scripts
  - call_requests
  - call_sessions
  - signal_events
  - email_suppressions
  - scheduling_requests
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f1a2b3c4d5e6"
down_revision: str | None = "e5f6a7b8c9d0"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # contacts — add phone column
    # ------------------------------------------------------------------
    op.add_column(
        "contacts",
        sa.Column("phone", sa.String(32), nullable=True),
    )

    # ------------------------------------------------------------------
    # email_sequences
    # ------------------------------------------------------------------
    op.create_table(
        "email_sequences",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("campaign_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_seq_campaign", "email_sequences", ["campaign_id"])

    # ------------------------------------------------------------------
    # sequence_steps
    # ------------------------------------------------------------------
    op.create_table(
        "sequence_steps",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("sequence_id", sa.Uuid(), nullable=False),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column("delay_days", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("subject_template", sa.String(255), nullable=False),
        sa.Column("body_template", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["sequence_id"], ["email_sequences.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_step_sequence_order", "sequence_steps", ["sequence_id", "step_order"])

    # ------------------------------------------------------------------
    # contact_sequence_state
    # ------------------------------------------------------------------
    op.create_table(
        "contact_sequence_state",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("contact_id", sa.Uuid(), nullable=False),
        sa.Column("sequence_id", sa.Uuid(), nullable=False),
        sa.Column("current_step", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("next_send_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("signal_type", sa.String(128), nullable=True),
        sa.Column("signal_detected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"]),
        sa.ForeignKeyConstraint(["sequence_id"], ["email_sequences.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("contact_id", "sequence_id", name="uq_contact_sequence"),
    )
    op.create_index("idx_css_status_next_send", "contact_sequence_state", ["status", "next_send_at"])
    op.create_index("idx_css_contact", "contact_sequence_state", ["contact_id"])
    op.create_index("idx_css_sequence_status", "contact_sequence_state", ["sequence_id", "status"])

    # ------------------------------------------------------------------
    # send_requests
    # ------------------------------------------------------------------
    op.create_table(
        "send_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("contact_sequence_state_id", sa.Uuid(), nullable=False),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column("provider_message_id", sa.String(255), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["contact_sequence_state_id"], ["contact_sequence_state.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", name="uq_send_request_idempotency_key"),
    )
    op.create_index("idx_sr_css", "send_requests", ["contact_sequence_state_id"])

    # ------------------------------------------------------------------
    # email_events
    # ------------------------------------------------------------------
    op.create_table(
        "email_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("send_request_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(["send_request_id"], ["send_requests.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_ee_send_request", "email_events", ["send_request_id"])
    op.create_index("idx_ee_event_type", "email_events", ["event_type"])

    # ------------------------------------------------------------------
    # voice_scripts
    # ------------------------------------------------------------------
    op.create_table(
        "voice_scripts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("campaign_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_vs_campaign", "voice_scripts", ["campaign_id"])

    # ------------------------------------------------------------------
    # call_requests
    # ------------------------------------------------------------------
    op.create_table(
        "call_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("contact_id", sa.Uuid(), nullable=False),
        sa.Column("campaign_id", sa.Uuid(), nullable=False),
        sa.Column("voice_script_id", sa.Uuid(), nullable=False),
        sa.Column("trigger_reason", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="queued"),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"]),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"]),
        sa.ForeignKeyConstraint(["voice_script_id"], ["voice_scripts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_cr_status_scheduled", "call_requests", ["status", "scheduled_at"])
    op.create_index("idx_cr_campaign", "call_requests", ["campaign_id"])

    # ------------------------------------------------------------------
    # call_sessions
    # ------------------------------------------------------------------
    op.create_table(
        "call_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("call_request_id", sa.Uuid(), nullable=False),
        sa.Column("twilio_call_sid", sa.String(64), nullable=False, server_default=""),
        sa.Column("duration_seconds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("outcome", sa.String(32), nullable=True),
        sa.Column("recording_url", sa.String(1024), nullable=True),
        sa.Column("transcript", sa.Text(), nullable=True),
        sa.Column(
            "unanswered_questions",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("scheduling_interest", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("postcall_status", sa.String(32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["call_request_id"], ["call_requests.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_cs_call_request", "call_sessions", ["call_request_id"])
    op.create_index("idx_cs_outcome", "call_sessions", ["outcome"])

    # ------------------------------------------------------------------
    # signal_events
    # ------------------------------------------------------------------
    op.create_table(
        "signal_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("contact_id", sa.Uuid(), nullable=False),
        sa.Column("campaign_id", sa.Uuid(), nullable=False),
        sa.Column("channel", sa.String(16), nullable=False),
        sa.Column("signal_type", sa.String(64), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("source_event_id", sa.Uuid(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"]),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_signal_contact", "signal_events", ["contact_id"])
    op.create_index("idx_signal_campaign", "signal_events", ["campaign_id"])
    op.create_index("idx_signal_type", "signal_events", ["signal_type"])

    # ------------------------------------------------------------------
    # email_suppressions
    # ------------------------------------------------------------------
    op.create_table(
        "email_suppressions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("reason", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", "reason", name="uq_suppression_email_reason"),
    )
    op.create_index("idx_suppression_email", "email_suppressions", ["email"])

    # ------------------------------------------------------------------
    # scheduling_requests
    # ------------------------------------------------------------------
    op.create_table(
        "scheduling_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("contact_id", sa.Uuid(), nullable=False),
        sa.Column("campaign_id", sa.Uuid(), nullable=False),
        sa.Column("signal_event_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"]),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"]),
        sa.ForeignKeyConstraint(["signal_event_id"], ["signal_events.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_sched_contact", "scheduling_requests", ["contact_id"])
    op.create_index("idx_sched_status", "scheduling_requests", ["status"])


def downgrade() -> None:
    op.drop_index("idx_sched_status", "scheduling_requests")
    op.drop_index("idx_sched_contact", "scheduling_requests")
    op.drop_table("scheduling_requests")

    op.drop_index("idx_suppression_email", "email_suppressions")
    op.drop_table("email_suppressions")

    op.drop_index("idx_signal_type", "signal_events")
    op.drop_index("idx_signal_campaign", "signal_events")
    op.drop_index("idx_signal_contact", "signal_events")
    op.drop_table("signal_events")

    op.drop_index("idx_cs_outcome", "call_sessions")
    op.drop_index("idx_cs_call_request", "call_sessions")
    op.drop_table("call_sessions")

    op.drop_index("idx_cr_campaign", "call_requests")
    op.drop_index("idx_cr_status_scheduled", "call_requests")
    op.drop_table("call_requests")

    op.drop_index("idx_vs_campaign", "voice_scripts")
    op.drop_table("voice_scripts")

    op.drop_index("idx_ee_event_type", "email_events")
    op.drop_index("idx_ee_send_request", "email_events")
    op.drop_table("email_events")

    op.drop_index("idx_sr_css", "send_requests")
    op.drop_table("send_requests")

    op.drop_index("idx_css_sequence_status", "contact_sequence_state")
    op.drop_index("idx_css_contact", "contact_sequence_state")
    op.drop_index("idx_css_status_next_send", "contact_sequence_state")
    op.drop_table("contact_sequence_state")

    op.drop_index("idx_step_sequence_order", "sequence_steps")
    op.drop_table("sequence_steps")

    op.drop_index("idx_seq_campaign", "email_sequences")
    op.drop_table("email_sequences")

    op.drop_column("contacts", "phone")
