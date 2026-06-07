"""add_vapi_provider_enum_value

Revision ID: t5i6j7k8l9m0
Revises: m8b9c0d1e2f3
Create Date: 2026-06-07 00:00:01.000000

Adds the Vapi notification provider enum value for already-upgraded
PostgreSQL databases. The earlier provider-selection migration also includes
this value for fresh databases.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "t5i6j7k8l9m0"
down_revision: str | tuple[str, ...] | None = "m8b9c0d1e2f3"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    """Apply this Alembic migration."""
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    with op.get_context().autocommit_block():
        op.execute(
            sa.text("ALTER TYPE notificationprovider ADD VALUE IF NOT EXISTS 'vapi'")
        )


def downgrade() -> None:
    """PostgreSQL enum values cannot be removed safely in-place."""
