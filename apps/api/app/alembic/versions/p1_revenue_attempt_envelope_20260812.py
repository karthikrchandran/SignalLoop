"""Persist immutable RevenueOS provider attempt envelopes.

Revision ID: p1_revenue_attempt_envelope_20260812
Revises: p1_ecrm_install_q_20260812, phase1_merge_20260812
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "p1_revenue_attempt_envelope_20260812"
down_revision = ("p1_ecrm_install_q_20260812", "phase1_merge_20260812")
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Store the one stable command used for every provider retry."""
    op.add_column(
        "revenue_intervention_dispatch",
        sa.Column("attempt_envelope", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    """Remove persisted attempt snapshots."""
    op.drop_column("revenue_intervention_dispatch", "attempt_envelope")
