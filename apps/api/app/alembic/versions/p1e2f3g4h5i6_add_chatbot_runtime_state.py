"""add_chatbot_runtime_state

Revision ID: p1e2f3g4h5i6
Revises: o0d1e2f3g4h5
Create Date: 2026-06-05 00:00:02.000000

Adds runtime conversation state for CBH-E4 and minimal contact metadata for
chatbot lead write-back.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "p1e2f3g4h5i6"
down_revision: str | tuple[str, ...] | None = "o0d1e2f3g4h5"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def _json_array_default() -> sa.TextClause:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return sa.text("'[]'::json")
    return sa.text("'[]'")


def upgrade() -> None:
    """Apply this Alembic migration."""
    op.add_column("contacts", sa.Column("source_channel", sa.String(length=64), nullable=True))
    op.add_column("contacts", sa.Column("tags_json", sa.JSON(), nullable=False, server_default=_json_array_default()))
    op.add_column("contacts", sa.Column("intent_json", sa.JSON(), nullable=False, server_default=_json_array_default()))
    op.add_column("contacts", sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True))

    op.add_column("chatbot_conversations", sa.Column("escalation_reason", sa.String(length=255), nullable=True))
    op.add_column(
        "chatbot_conversations",
        sa.Column("lead_capture_state", sa.String(length=32), nullable=False, server_default="none"),
    )
    op.add_column("chatbot_conversations", sa.Column("lead_capture_intent", sa.String(length=128), nullable=True))
    op.add_column("chatbot_conversations", sa.Column("outcome", sa.String(length=32), nullable=True))
    op.add_column(
        "chatbot_conversations",
        sa.Column("turn_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "chatbot_conversations",
        sa.Column("consecutive_low_confidence_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "chatbot_conversations",
        sa.Column("session_token_total", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("chatbot_conversations", sa.Column("customer_last_message_at", sa.DateTime(timezone=True), nullable=True))

    op.add_column("chatbot_messages", sa.Column("bot_confidence", sa.Float(), nullable=True))
    op.add_column("chatbot_messages", sa.Column("prompt_tokens", sa.Integer(), nullable=True))
    op.add_column("chatbot_messages", sa.Column("completion_tokens", sa.Integer(), nullable=True))


def downgrade() -> None:
    """Rollback this Alembic migration."""
    op.drop_column("chatbot_messages", "completion_tokens")
    op.drop_column("chatbot_messages", "prompt_tokens")
    op.drop_column("chatbot_messages", "bot_confidence")

    op.drop_column("chatbot_conversations", "customer_last_message_at")
    op.drop_column("chatbot_conversations", "session_token_total")
    op.drop_column("chatbot_conversations", "consecutive_low_confidence_count")
    op.drop_column("chatbot_conversations", "turn_count")
    op.drop_column("chatbot_conversations", "outcome")
    op.drop_column("chatbot_conversations", "lead_capture_intent")
    op.drop_column("chatbot_conversations", "lead_capture_state")
    op.drop_column("chatbot_conversations", "escalation_reason")

    op.drop_column("contacts", "last_seen_at")
    op.drop_column("contacts", "intent_json")
    op.drop_column("contacts", "tags_json")
    op.drop_column("contacts", "source_channel")
