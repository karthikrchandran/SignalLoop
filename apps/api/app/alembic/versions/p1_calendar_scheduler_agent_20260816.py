"""Add autonomous calendar scheduler workflow records.

Revision ID: p1_calendar_scheduler_agent_20260816
Revises: p1_proposal_generation_20260816
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "p1_calendar_scheduler_agent_20260816"
down_revision = "p1_proposal_generation_20260816"
branch_labels = None
depends_on = None


def _scope_columns() -> list[sa.Column]:
    return [
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.String(64), nullable=False),
    ]


def _scope_constraints() -> list[sa.ForeignKeyConstraint]:
    return [
        sa.ForeignKeyConstraint(["tenant_id"], ["suite_tenant.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], ondelete="CASCADE"
        ),
    ]


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_tenant_workspace_binding_scope",
        "suite_tenant_workspace_binding",
        ["tenant_id", "workspace_id"],
    )
    op.create_unique_constraint(
        "uq_scheduling_request_workspace", "scheduling_requests", ["id", "workspace_id"]
    )
    op.create_table(
        "calendar_meeting_type",
        sa.Column("id", sa.Uuid(), nullable=False),
        *_scope_columns(),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False),
        sa.Column("working_hours", sa.JSON(), nullable=False),
        sa.Column("holiday_dates", sa.JSON(), nullable=False),
        sa.Column("buffer_before_minutes", sa.Integer(), nullable=False),
        sa.Column("buffer_after_minutes", sa.Integer(), nullable=False),
        sa.Column("minimum_notice_minutes", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        *_scope_constraints(),
        sa.ForeignKeyConstraint(
            ["tenant_id", "workspace_id"],
            [
                "suite_tenant_workspace_binding.tenant_id",
                "suite_tenant_workspace_binding.workspace_id",
            ],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "workspace_id", "name", name="uq_calendar_meeting_type_name"
        ),
    )
    op.create_table(
        "calendar_provider_binding",
        sa.Column("id", sa.Uuid(), nullable=False),
        *_scope_columns(),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("provider_account_ref", sa.String(255), nullable=False),
        sa.Column("credential_secret_ref", sa.String(1024), nullable=False),
        sa.Column("capabilities", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        *_scope_constraints(),
        sa.ForeignKeyConstraint(
            ["tenant_id", "workspace_id"],
            [
                "suite_tenant_workspace_binding.tenant_id",
                "suite_tenant_workspace_binding.workspace_id",
            ],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "workspace_id", "provider", name="uq_calendar_provider_binding"
        ),
    )
    op.create_table(
        "scheduling_offer",
        sa.Column("id", sa.Uuid(), nullable=False),
        *_scope_columns(),
        sa.Column("scheduling_request_id", sa.Uuid(), nullable=False),
        sa.Column("meeting_type_id", sa.Uuid(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("offer_digest", sa.String(64), nullable=False),
        sa.Column("slots", sa.JSON(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["suite_tenant.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["scheduling_request_id", "workspace_id"],
            ["scheduling_requests.id", "scheduling_requests.workspace_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["meeting_type_id"], ["calendar_meeting_type.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "scheduling_request_id", "version", name="uq_scheduling_offer_version"
        ),
        sa.UniqueConstraint("offer_digest", name="uq_scheduling_offer_digest"),
    )
    op.create_table(
        "scheduling_confirmation",
        sa.Column("id", sa.Uuid(), nullable=False),
        *_scope_columns(),
        sa.Column("offer_id", sa.Uuid(), nullable=False),
        sa.Column("selected_slot_digest", sa.String(64), nullable=False),
        sa.Column("confirmed_by", sa.String(255), nullable=False),
        sa.Column("confirmation_key", sa.String(255), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["suite_tenant.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["offer_id"], ["scheduling_offer.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("offer_id", name="uq_scheduling_confirmation_offer"),
        sa.UniqueConstraint(
            "tenant_id",
            "workspace_id",
            "confirmation_key",
            name="uq_scheduling_confirmation_key",
        ),
    )
    op.create_table(
        "calendar_booking_job",
        sa.Column("id", sa.Uuid(), nullable=False),
        *_scope_columns(),
        sa.Column("deployment_id", sa.Uuid(), nullable=False),
        sa.Column("binding_id", sa.Uuid(), nullable=False),
        sa.Column("confirmation_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("command_key", sa.String(255), nullable=False),
        sa.Column("command_envelope", sa.JSON(), nullable=True),
        sa.Column("command_digest", sa.String(64), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_token", sa.Uuid(), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provider_attempted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("usage_reservation_id", sa.Uuid(), nullable=True),
        sa.Column("last_error_code", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["suite_tenant.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["deployment_id"], ["agent_deployment.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["binding_id"], ["calendar_provider_binding.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["confirmation_id"], ["scheduling_confirmation.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "confirmation_id", name="uq_calendar_booking_job_confirmation"
        ),
        sa.UniqueConstraint("command_key"),
    )
    op.create_index(
        "ix_calendar_booking_job_poll",
        "calendar_booking_job",
        ["status", "available_at"],
    )
    op.create_table(
        "calendar_booking_receipt",
        sa.Column("id", sa.Uuid(), nullable=False),
        *_scope_columns(),
        sa.Column("confirmation_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("provider_event_id", sa.String(255), nullable=False),
        sa.Column("provider_receipt_id", sa.String(255), nullable=False),
        sa.Column("command_digest", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["suite_tenant.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["confirmation_id"], ["scheduling_confirmation.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "confirmation_id", name="uq_calendar_booking_receipt_confirmation"
        ),
        sa.UniqueConstraint(
            "workspace_id",
            "provider",
            "provider_event_id",
            name="uq_calendar_booking_receipt_event",
        ),
    )
    for table, columns in {
        "calendar_meeting_type": ("tenant_id", "workspace_id", "status"),
        "calendar_provider_binding": ("tenant_id", "workspace_id", "status"),
        "scheduling_offer": (
            "tenant_id",
            "workspace_id",
            "scheduling_request_id",
            "expires_at",
            "status",
        ),
        "scheduling_confirmation": ("tenant_id", "workspace_id", "offer_id"),
        "calendar_booking_job": (
            "tenant_id",
            "workspace_id",
            "deployment_id",
            "status",
            "lease_token",
        ),
        "calendar_booking_receipt": ("tenant_id", "workspace_id", "confirmation_id"),
    }.items():
        for column in columns:
            op.create_index(f"ix_{table}_{column}", table, [column])


def downgrade() -> None:
    op.drop_table("calendar_booking_receipt")
    op.drop_table("calendar_booking_job")
    op.drop_table("scheduling_confirmation")
    op.drop_table("scheduling_offer")
    op.drop_table("calendar_provider_binding")
    op.drop_table("calendar_meeting_type")
    op.drop_constraint(
        "uq_scheduling_request_workspace", "scheduling_requests", type_="unique"
    )
    op.drop_constraint(
        "uq_tenant_workspace_binding_scope",
        "suite_tenant_workspace_binding",
        type_="unique",
    )
