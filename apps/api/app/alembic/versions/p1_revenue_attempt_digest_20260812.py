"""Protect immutable RevenueOS provider commands with a content digest.

Revision ID: p1_revenue_attempt_digest_20260812
Revises: p1_revenue_attempt_envelope_20260812
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "p1_revenue_attempt_digest_20260812"
down_revision = "p1_revenue_attempt_envelope_20260812"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "revenue_intervention_dispatch",
        sa.Column("attempt_envelope_digest", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("revenue_intervention_dispatch", "attempt_envelope_digest")
