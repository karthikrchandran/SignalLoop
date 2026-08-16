"""Allow provider-native/manual calendar intents without a signal event.

Revision ID: p1_calendar_intent_nullable_20260816
Revises: p1_proposal_hardening_20260816
"""

from __future__ import annotations

from alembic import op

revision = "p1_calendar_intent_nullable_20260816"
down_revision = "p1_proposal_hardening_20260816"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("scheduling_requests", "signal_event_id", nullable=True)


def downgrade() -> None:
    op.alter_column("scheduling_requests", "signal_event_id", nullable=False)
