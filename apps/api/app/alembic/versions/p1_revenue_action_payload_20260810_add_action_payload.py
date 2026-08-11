"""add explicit RevenueOS intervention action payload

Revision ID: p1_revenue_action_payload_20260810
Revises: p1_revenue_interventions_20260810
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "p1_revenue_action_payload_20260810"
down_revision: str | None = "p1_revenue_interventions_20260810"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    """Require a persisted, explicit execution payload for each intervention."""
    op.add_column(
        "revenue_intervention_record",
        sa.Column("action_payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )
    op.alter_column("revenue_intervention_record", "action_payload", server_default=None)


def downgrade() -> None:
    """Remove explicit action payload."""
    op.drop_column("revenue_intervention_record", "action_payload")
