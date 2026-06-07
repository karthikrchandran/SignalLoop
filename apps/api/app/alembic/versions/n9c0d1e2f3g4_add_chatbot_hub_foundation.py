"""add_chatbot_hub_foundation

Revision ID: n9c0d1e2f3g4
Revises: m8b9c0d1e2f3
Create Date: 2026-06-05 00:00:00.000000

Adds the ChatBot Hub foundation tables and enables pgvector for PostgreSQL.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.types import UserDefinedType

revision: str = "n9c0d1e2f3g4"
down_revision: str | tuple[str, ...] | None = "m8b9c0d1e2f3"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


class PgVector(UserDefinedType):
    """Minimal pgvector Alembic type."""

    cache_ok = True

    def __init__(self, dimensions: int = 768) -> None:
        self.dimensions = dimensions

    def get_col_spec(self, **_: object) -> str:
        return f"vector({self.dimensions})"


# Set to False inside upgrade() when pgvector is not available.
_pgvector_available: bool = True


def _json_type() -> sa.types.TypeEngine:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return postgresql.JSONB(astext_type=sa.Text())
    return sa.JSON()


def _embedding_type() -> sa.types.TypeEngine:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql" and _pgvector_available:
        return PgVector(768)
    return sa.JSON()


def upgrade() -> None:
    """Apply this Alembic migration."""
    global _pgvector_available
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        try:
            with op.get_context().autocommit_block():
                op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector"))
        except Exception:
            # pgvector not installed at the system level — proceed without it.
            # The embedding column will be created as JSON instead.
            _pgvector_available = False

    json_type = _json_type()

    op.create_table(
        "chatbot_channel_configs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.String(length=64), nullable=False),
        sa.Column("channel_type", sa.String(length=32), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("credential_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("webhook_secret_hash", sa.Text(), nullable=True),
        sa.Column("config_json", json_type, nullable=True),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["credential_id"], ["provider_credentials.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "channel_type", name="uq_chatbot_channel_workspace_type"),
    )
    op.create_index("ix_chatbot_channel_configs_workspace_id", "chatbot_channel_configs", ["workspace_id"])
    op.create_index("ix_chatbot_channel_configs_channel_type", "chatbot_channel_configs", ["channel_type"])
    op.create_index(
        "idx_chatbot_channel_workspace_status",
        "chatbot_channel_configs",
        ["workspace_id", "status"],
    )

    op.create_table(
        "chatbot_bot_configs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.String(length=64), nullable=False),
        sa.Column("bot_name", sa.String(length=120), nullable=False),
        sa.Column("persona", sa.Text(), nullable=True),
        sa.Column("greeting_message", sa.Text(), nullable=True),
        sa.Column("escalation_message", sa.Text(), nullable=True),
        sa.Column("out_of_hours_message", sa.Text(), nullable=True),
        sa.Column("ai_disclosure", sa.String(length=255), nullable=False),
        sa.Column("token_cap_per_session", sa.Integer(), nullable=False),
        sa.Column("retention_days", sa.Integer(), nullable=False),
        sa.Column("business_hours_json", json_type, nullable=True),
        sa.Column("lead_capture_json", json_type, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", name="uq_chatbot_bot_config_workspace"),
    )
    op.create_index("ix_chatbot_bot_configs_workspace_id", "chatbot_bot_configs", ["workspace_id"])

    op.create_table(
        "chatbot_knowledge_sources",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.String(length=64), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("source_uri", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("index_version", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(length=128), nullable=True),
        sa.Column("config_json", json_type, nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_chatbot_knowledge_sources_workspace_id", "chatbot_knowledge_sources", ["workspace_id"])
    op.create_index("ix_chatbot_knowledge_sources_source_type", "chatbot_knowledge_sources", ["source_type"])
    op.create_index("ix_chatbot_knowledge_sources_index_version", "chatbot_knowledge_sources", ["index_version"])
    op.create_index(
        "idx_chatbot_knowledge_workspace_status",
        "chatbot_knowledge_sources",
        ["workspace_id", "status"],
    )
    op.create_index(
        "idx_chatbot_knowledge_workspace_version",
        "chatbot_knowledge_sources",
        ["workspace_id", "index_version"],
    )

    op.create_table(
        "chatbot_knowledge_chunks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.String(length=64), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("index_version", sa.Integer(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("embedding", _embedding_type(), nullable=True),
        sa.Column("metadata_json", json_type, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["source_id"], ["chatbot_knowledge_sources.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_id", "chunk_index", name="uq_chatbot_chunk_source_index"),
    )
    op.create_index("ix_chatbot_knowledge_chunks_workspace_id", "chatbot_knowledge_chunks", ["workspace_id"])
    op.create_index("ix_chatbot_knowledge_chunks_source_id", "chatbot_knowledge_chunks", ["source_id"])
    op.create_index("ix_chatbot_knowledge_chunks_index_version", "chatbot_knowledge_chunks", ["index_version"])
    op.create_index(
        "idx_chatbot_chunk_workspace_version",
        "chatbot_knowledge_chunks",
        ["workspace_id", "index_version"],
    )

    op.create_table(
        "chatbot_conversations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.String(length=64), nullable=False),
        sa.Column("channel_type", sa.String(length=32), nullable=False),
        sa.Column("visitor_id", sa.String(length=255), nullable=False),
        sa.Column("provider_thread_id", sa.String(length=255), nullable=True),
        sa.Column("contact_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("index_version", sa.Integer(), nullable=False),
        sa.Column("bot_paused", sa.Boolean(), nullable=False),
        sa.Column("escalated", sa.Boolean(), nullable=False),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id",
            "channel_type",
            "visitor_id",
            name="uq_chatbot_conversation_workspace_visitor",
        ),
    )
    op.create_index("ix_chatbot_conversations_workspace_id", "chatbot_conversations", ["workspace_id"])
    op.create_index("ix_chatbot_conversations_channel_type", "chatbot_conversations", ["channel_type"])
    op.create_index("ix_chatbot_conversations_visitor_id", "chatbot_conversations", ["visitor_id"])
    op.create_index("ix_chatbot_conversations_contact_id", "chatbot_conversations", ["contact_id"])
    op.create_index("ix_chatbot_conversations_last_message_at", "chatbot_conversations", ["last_message_at"])
    op.create_index(
        "idx_chatbot_conversation_workspace_status",
        "chatbot_conversations",
        ["workspace_id", "status"],
    )
    op.create_index(
        "idx_chatbot_conversation_workspace_last_message",
        "chatbot_conversations",
        ["workspace_id", "last_message_at"],
    )

    op.create_table(
        "chatbot_messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.String(length=64), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("provider_message_id", sa.String(length=255), nullable=True),
        sa.Column("direction", sa.String(length=16), nullable=False),
        sa.Column("sender", sa.String(length=16), nullable=False),
        sa.Column("message_type", sa.String(length=32), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("metadata_json", json_type, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["conversation_id"], ["chatbot_conversations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id",
            "provider_message_id",
            name="uq_chatbot_message_workspace_provider_message",
        ),
    )
    op.create_index("ix_chatbot_messages_workspace_id", "chatbot_messages", ["workspace_id"])
    op.create_index("ix_chatbot_messages_conversation_id", "chatbot_messages", ["conversation_id"])
    op.create_index("ix_chatbot_messages_direction", "chatbot_messages", ["direction"])
    op.create_index("ix_chatbot_messages_sender", "chatbot_messages", ["sender"])
    op.create_index("ix_chatbot_messages_created_at", "chatbot_messages", ["created_at"])
    op.create_index(
        "idx_chatbot_message_conversation_created",
        "chatbot_messages",
        ["conversation_id", "created_at"],
    )
    op.create_index("idx_chatbot_message_workspace_sender", "chatbot_messages", ["workspace_id", "sender"])

    op.create_table(
        "chatbot_opt_outs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.String(length=64), nullable=False),
        sa.Column("channel_type", sa.String(length=32), nullable=False),
        sa.Column("visitor_id", sa.String(length=255), nullable=False),
        sa.Column("contact_id", sa.Uuid(), nullable=True),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column("source_message_id", sa.Uuid(), nullable=True),
        sa.Column("reopt_in_invited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"]),
        sa.ForeignKeyConstraint(["source_message_id"], ["chatbot_messages.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "channel_type", "visitor_id", name="uq_chatbot_opt_out_visitor"),
    )
    op.create_index("ix_chatbot_opt_outs_workspace_id", "chatbot_opt_outs", ["workspace_id"])
    op.create_index("ix_chatbot_opt_outs_channel_type", "chatbot_opt_outs", ["channel_type"])
    op.create_index("ix_chatbot_opt_outs_visitor_id", "chatbot_opt_outs", ["visitor_id"])
    op.create_index("ix_chatbot_opt_outs_contact_id", "chatbot_opt_outs", ["contact_id"])
    op.create_index("idx_chatbot_opt_out_workspace_created", "chatbot_opt_outs", ["workspace_id", "created_at"])

    op.create_table(
        "chatbot_analytics_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.String(length=64), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("channel_type", sa.String(length=32), nullable=True),
        sa.Column("total_conversations", sa.Integer(), nullable=False),
        sa.Column("bot_messages", sa.Integer(), nullable=False),
        sa.Column("escalations", sa.Integer(), nullable=False),
        sa.Column("leads_captured", sa.Integer(), nullable=False),
        sa.Column("metrics_json", json_type, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id",
            "snapshot_date",
            "channel_type",
            name="uq_chatbot_analytics_workspace_date_channel",
        ),
    )
    op.create_index("ix_chatbot_analytics_snapshots_workspace_id", "chatbot_analytics_snapshots", ["workspace_id"])
    op.create_index(
        "idx_chatbot_analytics_workspace_date",
        "chatbot_analytics_snapshots",
        ["workspace_id", "snapshot_date"],
    )


def downgrade() -> None:
    """Revert this Alembic migration."""
    op.drop_table("chatbot_analytics_snapshots")
    op.drop_table("chatbot_opt_outs")
    op.drop_table("chatbot_messages")
    op.drop_table("chatbot_conversations")
    op.drop_table("chatbot_knowledge_chunks")
    op.drop_table("chatbot_knowledge_sources")
    op.drop_table("chatbot_bot_configs")
    op.drop_table("chatbot_channel_configs")
