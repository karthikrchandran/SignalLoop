"""add_provider_event_replay_unique_constraint

Revision ID: r3g4h5i6j7k8
Revises: q2f3g4h5i6j7
Create Date: 2026-06-07 00:00:00.000000
"""
from __future__ import annotations

from alembic import op

revision: str = "r3g4h5i6j7k8"
down_revision: str | None = "q2f3g4h5i6j7"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    """Apply this Alembic migration."""
    op.create_unique_constraint(
        "uq_provider_event_provider_event_id",
        "provider_event_logs",
        ["provider", "provider_event_id"],
    )


def downgrade() -> None:
    """Revert this Alembic migration."""
    op.drop_constraint(
        "uq_provider_event_provider_event_id",
        "provider_event_logs",
        type_="unique",
    )
