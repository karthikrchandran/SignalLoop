"""add_chatbot_inbox_compliance_state

Revision ID: q2f3g4h5i6j7
Revises: p1e2f3g4h5i6
Create Date: 2026-06-07 00:00:00.000000

Adds inbox handoff and compliance retention state for CBH-E5/E6.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "q2f3g4h5i6j7"
down_revision: str | tuple[str, ...] | None = "p1e2f3g4h5i6"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    """Apply this Alembic migration."""
    op.add_column("chatbot_conversations", sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("chatbot_conversations", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_chatbot_conversations_deleted_at", "chatbot_conversations", ["deleted_at"])
    op.add_column("chatbot_messages", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_chatbot_messages_deleted_at", "chatbot_messages", ["deleted_at"])


def downgrade() -> None:
    """Rollback this Alembic migration."""
    op.drop_index("ix_chatbot_messages_deleted_at", table_name="chatbot_messages")
    op.drop_column("chatbot_messages", "deleted_at")
    op.drop_index("ix_chatbot_conversations_deleted_at", table_name="chatbot_conversations")
    op.drop_column("chatbot_conversations", "deleted_at")
    op.drop_column("chatbot_conversations", "resolved_at")

