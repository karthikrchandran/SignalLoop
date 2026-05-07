"""add_workspace_id_to_contact_state_history

Revision ID: j5e6f7a8b9c0
Revises: i4d5e6f7a8b9
Create Date: 2026-05-06 00:00:00.000000

Adds workspace_id to contact_state_history for direct tenant isolation
without requiring a JOIN through campaigns.

Migration steps:
  1. Add workspace_id column (nullable initially).
  2. Backfill from the campaigns table via campaign_id.
  3. Tighten to NOT NULL + add index.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "j5e6f7a8b9c0"
down_revision: tuple[str, str] = ("i4d5e6f7a8b9", "b1c2d3e4f5a6")
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    """Apply this Alembic migration."""
    # 1. Add column as nullable so existing rows don't violate NOT NULL.
    op.add_column(
        "contact_state_history",
        sa.Column("workspace_id", sa.String(length=64), nullable=True),
    )

    # 2. Backfill: copy workspace_id from campaigns via campaign_id.
    op.execute(
        """
        UPDATE contact_state_history AS csh
        SET    workspace_id = c.workspace_id
        FROM   campaigns AS c
        WHERE  csh.campaign_id = c.id
        """
    )

    # 3. Any orphaned rows (no matching campaign) get a sentinel so the
    #    NOT NULL constraint can be applied cleanly.
    op.execute(
        """
        UPDATE contact_state_history
        SET    workspace_id = 'unknown'
        WHERE  workspace_id IS NULL
        """
    )

    # 4. Tighten to NOT NULL.
    op.alter_column(
        "contact_state_history",
        "workspace_id",
        existing_type=sa.String(length=64),
        nullable=False,
    )

    # 5. Add index for workspace-scoped queries.
    op.create_index(
        "ix_contact_state_history_workspace_id",
        "contact_state_history",
        ["workspace_id"],
    )


def downgrade() -> None:
    """Revert this Alembic migration."""
    op.drop_index("ix_contact_state_history_workspace_id", table_name="contact_state_history")
    op.drop_column("contact_state_history", "workspace_id")
