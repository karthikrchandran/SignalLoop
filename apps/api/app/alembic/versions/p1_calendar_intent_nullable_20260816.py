"""Allow provider-native/manual calendar intents without a signal event.

Revision ID: p1_calendar_intent_nullable_20260816
Revises: p1_proposal_hardening_20260816
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "p1_calendar_intent_nullable_20260816"
down_revision = "p1_proposal_hardening_20260816"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("scheduling_requests", "signal_event_id", nullable=True)


def downgrade() -> None:
    null_count = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT COUNT(*) FROM scheduling_requests WHERE signal_event_id IS NULL"
            )
        )
        .scalar_one()
    )
    if null_count:
        raise RuntimeError(
            "cannot downgrade scheduling_requests.signal_event_id to NOT NULL: "
            f"{null_count} row(s) have no signal event"
        )
    op.alter_column("scheduling_requests", "signal_event_id", nullable=False)
