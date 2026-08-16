"""Harden calendar lifecycle receipts for stable provider event identities.

Revision ID: p1_calendar_lifecycle_hardening_20260816
Revises: p1_calendar_intent_nullable_20260816
"""

from __future__ import annotations

from alembic import op

revision = "p1_calendar_lifecycle_hardening_20260816"
down_revision = "p1_calendar_intent_nullable_20260816"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "uq_calendar_booking_receipt_event",
        "calendar_booking_receipt",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_calendar_booking_receipt_provider_receipt",
        "calendar_booking_receipt",
        ["workspace_id", "provider", "provider_receipt_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_calendar_booking_receipt_provider_receipt",
        "calendar_booking_receipt",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_calendar_booking_receipt_event",
        "calendar_booking_receipt",
        ["workspace_id", "provider", "provider_event_id"],
    )
