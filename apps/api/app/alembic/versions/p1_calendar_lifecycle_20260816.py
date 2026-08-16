"""Add immutable calendar booking lifecycle generations.

Revision ID: p1_calendar_lifecycle_20260816
Revises: p1_calendar_scheduler_agent_20260816
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "p1_calendar_lifecycle_20260816"
down_revision = "p1_calendar_scheduler_agent_20260816"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "uq_calendar_booking_job_confirmation", "calendar_booking_job", type_="unique"
    )
    op.add_column(
        "calendar_booking_job",
        sa.Column("operation", sa.String(32), nullable=False, server_default="BOOK"),
    )
    op.add_column(
        "calendar_booking_job",
        sa.Column("generation", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "calendar_booking_job",
        sa.Column("provider_event_id", sa.String(255), nullable=True),
    )
    op.add_column(
        "calendar_booking_job",
        sa.Column("predecessor_job_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_calendar_booking_job_predecessor",
        "calendar_booking_job",
        "calendar_booking_job",
        ["predecessor_job_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint(
        "ck_calendar_booking_job_operation",
        "calendar_booking_job",
        "operation IN ('BOOK', 'RESCHEDULE', 'CANCEL')",
    )
    op.create_check_constraint(
        "ck_calendar_booking_job_generation", "calendar_booking_job", "generation >= 1"
    )
    op.create_unique_constraint(
        "uq_calendar_booking_job_confirmation_operation_generation",
        "calendar_booking_job",
        ["confirmation_id", "operation", "generation"],
    )
    op.create_unique_constraint(
        "uq_calendar_booking_job_predecessor",
        "calendar_booking_job",
        ["predecessor_job_id"],
    )
    op.create_index(
        "ix_calendar_booking_job_predecessor_job_id",
        "calendar_booking_job",
        ["predecessor_job_id"],
    )
    op.create_index(
        "ix_calendar_booking_job_operation", "calendar_booking_job", ["operation"]
    )

    op.drop_constraint(
        "uq_calendar_booking_receipt_confirmation",
        "calendar_booking_receipt",
        type_="unique",
    )
    op.add_column(
        "calendar_booking_receipt",
        sa.Column("operation", sa.String(32), nullable=False, server_default="BOOK"),
    )
    op.add_column(
        "calendar_booking_receipt",
        sa.Column("generation", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "calendar_booking_receipt",
        sa.Column("previous_provider_event_id", sa.String(255), nullable=True),
    )
    op.create_check_constraint(
        "ck_calendar_booking_receipt_operation",
        "calendar_booking_receipt",
        "operation IN ('BOOK', 'RESCHEDULE', 'CANCEL')",
    )
    op.create_check_constraint(
        "ck_calendar_booking_receipt_generation",
        "calendar_booking_receipt",
        "generation >= 1",
    )
    op.create_unique_constraint(
        "uq_calendar_booking_receipt_confirmation_operation_generation",
        "calendar_booking_receipt",
        ["confirmation_id", "operation", "generation"],
    )
    op.create_index(
        "ix_calendar_booking_receipt_operation",
        "calendar_booking_receipt",
        ["operation"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_calendar_booking_receipt_operation", table_name="calendar_booking_receipt"
    )
    op.drop_constraint(
        "uq_calendar_booking_receipt_confirmation_operation_generation",
        "calendar_booking_receipt",
        type_="unique",
    )
    op.drop_constraint(
        "ck_calendar_booking_receipt_generation",
        "calendar_booking_receipt",
        type_="check",
    )
    op.drop_constraint(
        "ck_calendar_booking_receipt_operation",
        "calendar_booking_receipt",
        type_="check",
    )
    op.drop_column("calendar_booking_receipt", "previous_provider_event_id")
    op.drop_column("calendar_booking_receipt", "generation")
    op.drop_column("calendar_booking_receipt", "operation")
    op.create_unique_constraint(
        "uq_calendar_booking_receipt_confirmation",
        "calendar_booking_receipt",
        ["confirmation_id"],
    )

    op.drop_index(
        "ix_calendar_booking_job_operation", table_name="calendar_booking_job"
    )
    op.drop_index(
        "ix_calendar_booking_job_predecessor_job_id", table_name="calendar_booking_job"
    )
    op.drop_constraint(
        "uq_calendar_booking_job_confirmation_operation_generation",
        "calendar_booking_job",
        type_="unique",
    )
    op.drop_constraint(
        "uq_calendar_booking_job_predecessor", "calendar_booking_job", type_="unique"
    )
    op.drop_constraint(
        "ck_calendar_booking_job_generation", "calendar_booking_job", type_="check"
    )
    op.drop_constraint(
        "ck_calendar_booking_job_operation", "calendar_booking_job", type_="check"
    )
    op.drop_constraint(
        "fk_calendar_booking_job_predecessor",
        "calendar_booking_job",
        type_="foreignkey",
    )
    op.drop_column("calendar_booking_job", "predecessor_job_id")
    op.drop_column("calendar_booking_job", "provider_event_id")
    op.drop_column("calendar_booking_job", "generation")
    op.drop_column("calendar_booking_job", "operation")
    op.create_unique_constraint(
        "uq_calendar_booking_job_confirmation",
        "calendar_booking_job",
        ["confirmation_id"],
    )
