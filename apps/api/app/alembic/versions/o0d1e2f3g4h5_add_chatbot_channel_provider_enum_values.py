"""add_chatbot_channel_provider_enum_values

Revision ID: o0d1e2f3g4h5
Revises: n9c0d1e2f3g4
Create Date: 2026-06-05 00:00:01.000000

Extends the existing notificationprovider enum for ChatBot Hub channel
credentials stored through ProviderCredential.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "o0d1e2f3g4h5"
down_revision: str | tuple[str, ...] | None = "n9c0d1e2f3g4"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None

CHATBOT_PROVIDER_VALUES: tuple[str, ...] = (
    "facebook_messenger",
    "whatsapp_cloud",
    "telegram_bot",
    "linkedin_redirect",
)


def upgrade() -> None:
    """Apply this Alembic migration."""
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    for value in CHATBOT_PROVIDER_VALUES:
        op.execute(sa.text(f"ALTER TYPE notificationprovider ADD VALUE IF NOT EXISTS '{value}'"))


def downgrade() -> None:
    """PostgreSQL enum values cannot be removed safely in-place."""
