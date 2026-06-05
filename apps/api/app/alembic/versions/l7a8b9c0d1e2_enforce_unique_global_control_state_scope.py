"""enforce_unique_global_control_state_scope

Revision ID: l7a8b9c0d1e2
Revises: k6f7a8b9c0d1
Create Date: 2026-05-28 00:00:01.000000

Ensures there is at most one global control state row per workspace scope.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "l7a8b9c0d1e2"
down_revision: str | tuple[str, ...] | None = "k6f7a8b9c0d1"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    """Apply this Alembic migration."""
    op.execute(
        sa.text(
            """
            WITH ranked AS (
                SELECT
                    id,
                    ROW_NUMBER() OVER (
                        PARTITION BY workspace_id, campaign_id
                        ORDER BY paused_at DESC NULLS LAST, id DESC
                    ) AS row_number
                FROM global_control_state
            )
            DELETE FROM global_control_state
            WHERE id IN (
                SELECT id
                FROM ranked
                WHERE row_number > 1
            )
            """
        )
    )
    op.create_index(
        "uq_global_control_state_workspace_global",
        "global_control_state",
        ["workspace_id"],
        unique=True,
        postgresql_where=sa.text("campaign_id IS NULL"),
    )
    op.create_index(
        "uq_global_control_state_workspace_campaign",
        "global_control_state",
        ["workspace_id", "campaign_id"],
        unique=True,
        postgresql_where=sa.text("campaign_id IS NOT NULL"),
    )


def downgrade() -> None:
    """Revert this Alembic migration."""
    op.drop_index("uq_global_control_state_workspace_campaign", table_name="global_control_state")
    op.drop_index("uq_global_control_state_workspace_global", table_name="global_control_state")