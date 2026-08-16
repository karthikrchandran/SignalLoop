"""Persistence + API models for the ``scheduling`` domain."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SchedulingRequestStatus(str, Enum):
    """Lifecycle states for a scheduling request."""

    pending = "pending"  # intent detected, awaiting action
    link_sent = "link_sent"  # meeting link sent to contact
    booked = "booked"  # Calendly confirmed booking
    cancelled = "cancelled"  # cancelled or no-show


class SchedulingRequestSource(str, Enum):
    """How the scheduling request was triggered."""

    voice_call = "voice_call"
    email_reply = "email_reply"
    manual = "manual"


class SchedulingRequest(SQLModel, table=True):  # type: ignore[call-arg]
    """A scheduling request created when a contact expresses meeting intent."""

    __tablename__ = "scheduling_requests"
    __table_args__ = (
        ForeignKeyConstraint(
            ["campaign_id", "workspace_id"],
            ["campaigns.id", "campaigns.workspace_id"],
            name="fk_scheduling_campaign_workspace",
        ),
        ForeignKeyConstraint(
            ["contact_id", "workspace_id"],
            ["contacts.id", "contacts.workspace_id"],
            name="fk_scheduling_contact_workspace",
        ),
        ForeignKeyConstraint(
            ["signal_event_id", "workspace_id"],
            ["signal_events.id", "signal_events.workspace_id"],
            name="fk_scheduling_signal_workspace",
        ),
        UniqueConstraint(
            "workspace_id",
            "calendly_event_id",
            name="uq_scheduling_workspace_calendly_event",
        ),
        UniqueConstraint("id", "workspace_id", name="uq_scheduling_request_workspace"),
        {"extend_existing": True},
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workspace_id: str = Field(max_length=64)
    contact_id: uuid.UUID = Field(foreign_key="contacts.id")
    campaign_id: uuid.UUID = Field(foreign_key="campaigns.id")
    signal_event_id: uuid.UUID | None = Field(
        default=None, foreign_key="signal_events.id"
    )

    status: str = Field(default=SchedulingRequestStatus.pending, max_length=32)
    source: str = Field(default=SchedulingRequestSource.voice_call, max_length=32)

    meeting_link: str | None = Field(default=None, sa_type=Text)
    calendly_event_id: str | None = Field(default=None, max_length=255)
    meeting_datetime: datetime | None = Field(
        default=None, sa_type=DateTime(timezone=True)
    )
    assigned_to_email: str | None = Field(default=None, max_length=255)
    notes: str | None = Field(default=None, sa_type=Text)

    created_at: datetime = Field(
        default_factory=_utcnow, sa_type=DateTime(timezone=True)
    )
    updated_at: datetime = Field(
        default_factory=_utcnow, sa_type=DateTime(timezone=True)
    )


class CalendarMeetingType(SQLModel, table=True):  # type: ignore[call-arg]
    __tablename__ = "calendar_meeting_type"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "workspace_id", "name", name="uq_calendar_meeting_type_name"
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(
        sa_column=Column(
            ForeignKey("suite_tenant.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    workspace_id: str = Field(
        sa_column=Column(
            String(64),
            ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    name: str = Field(max_length=255)
    duration_minutes: int = Field(ge=5, le=480)
    timezone: str = Field(max_length=64)
    working_hours: dict[str, list[list[str]]] = Field(
        sa_column=Column(JSON, nullable=False)
    )
    holiday_dates: list[str] = Field(
        default_factory=list, sa_column=Column(JSON, nullable=False)
    )
    buffer_before_minutes: int = Field(default=0, ge=0, le=1440)
    buffer_after_minutes: int = Field(default=0, ge=0, le=1440)
    minimum_notice_minutes: int = Field(default=60, ge=0, le=10080)
    status: str = Field(default="ACTIVE", max_length=32, index=True)
    created_at: datetime = Field(
        default_factory=_utcnow, sa_type=DateTime(timezone=True)
    )


class CalendarProviderBinding(SQLModel, table=True):  # type: ignore[call-arg]
    __tablename__ = "calendar_provider_binding"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "workspace_id", "provider", name="uq_calendar_provider_binding"
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(
        sa_column=Column(
            ForeignKey("suite_tenant.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    workspace_id: str = Field(
        sa_column=Column(
            String(64),
            ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    provider: str = Field(max_length=32)
    provider_account_ref: str = Field(max_length=255)
    credential_secret_ref: str = Field(max_length=1024)
    capabilities: list[str] = Field(sa_column=Column(JSON, nullable=False))
    status: str = Field(default="ACTIVE", max_length=32, index=True)
    created_at: datetime = Field(
        default_factory=_utcnow, sa_type=DateTime(timezone=True)
    )


class SchedulingOffer(SQLModel, table=True):  # type: ignore[call-arg]
    __tablename__ = "scheduling_offer"
    __table_args__ = (
        UniqueConstraint(
            "scheduling_request_id", "version", name="uq_scheduling_offer_version"
        ),
        UniqueConstraint("offer_digest", name="uq_scheduling_offer_digest"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(
        sa_column=Column(
            ForeignKey("suite_tenant.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    workspace_id: str = Field(max_length=64, index=True)
    scheduling_request_id: uuid.UUID = Field(
        sa_column=Column(
            ForeignKey("scheduling_requests.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    meeting_type_id: uuid.UUID | None = Field(
        default=None, foreign_key="calendar_meeting_type.id"
    )
    version: int = Field(ge=1)
    offer_digest: str = Field(max_length=64)
    slots: list[dict[str, str]] = Field(sa_column=Column(JSON, nullable=False))
    expires_at: datetime = Field(sa_type=DateTime(timezone=True), index=True)
    status: str = Field(default="OPEN", max_length=32, index=True)
    created_at: datetime = Field(
        default_factory=_utcnow, sa_type=DateTime(timezone=True)
    )


class SchedulingConfirmation(SQLModel, table=True):  # type: ignore[call-arg]
    __tablename__ = "scheduling_confirmation"
    __table_args__ = (
        UniqueConstraint("offer_id", name="uq_scheduling_confirmation_offer"),
        UniqueConstraint(
            "tenant_id",
            "workspace_id",
            "confirmation_key",
            name="uq_scheduling_confirmation_key",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(
        sa_column=Column(
            ForeignKey("suite_tenant.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    workspace_id: str = Field(max_length=64, index=True)
    offer_id: uuid.UUID = Field(
        sa_column=Column(
            ForeignKey("scheduling_offer.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    selected_slot_digest: str = Field(max_length=64)
    confirmed_by: str = Field(max_length=255)
    confirmation_key: str = Field(max_length=255)
    confirmed_at: datetime = Field(
        default_factory=_utcnow, sa_type=DateTime(timezone=True)
    )


class CalendarBookingJob(SQLModel, table=True):  # type: ignore[call-arg]
    __tablename__ = "calendar_booking_job"
    __table_args__ = (
        UniqueConstraint(
            "confirmation_id",
            "operation",
            "generation",
            name="uq_calendar_booking_job_confirmation_operation_generation",
        ),
        UniqueConstraint(
            "predecessor_job_id", name="uq_calendar_booking_job_predecessor"
        ),
        Index("ix_calendar_booking_job_poll", "status", "available_at"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(
        sa_column=Column(
            ForeignKey("suite_tenant.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    workspace_id: str = Field(max_length=64, index=True)
    deployment_id: uuid.UUID = Field(
        sa_column=Column(
            ForeignKey("agent_deployment.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        )
    )
    binding_id: uuid.UUID = Field(
        sa_column=Column(
            ForeignKey("calendar_provider_binding.id", ondelete="RESTRICT"),
            nullable=False,
        )
    )
    confirmation_id: uuid.UUID = Field(
        sa_column=Column(
            ForeignKey("scheduling_confirmation.id", ondelete="CASCADE"), nullable=False
        )
    )
    operation: str = Field(default="BOOK", max_length=32, index=True)
    generation: int = Field(default=1, ge=1)
    provider_event_id: str | None = Field(default=None, max_length=255)
    predecessor_job_id: uuid.UUID | None = Field(
        default=None,
        sa_column=Column(
            ForeignKey("calendar_booking_job.id", ondelete="RESTRICT"),
            nullable=True,
            index=True,
        ),
    )
    status: str = Field(default="PENDING", max_length=32, index=True)
    command_key: str = Field(max_length=255, unique=True)
    command_envelope: dict | None = Field(default=None, sa_column=Column(JSON))
    command_digest: str | None = Field(default=None, max_length=64)
    attempt_count: int = Field(default=0, ge=0)
    max_attempts: int = Field(default=5, ge=1, le=20)
    available_at: datetime = Field(
        default_factory=_utcnow, sa_type=DateTime(timezone=True)
    )
    lease_token: uuid.UUID | None = Field(default=None, index=True)
    lease_expires_at: datetime | None = Field(
        default=None, sa_type=DateTime(timezone=True)
    )
    provider_attempted_at: datetime | None = Field(
        default=None, sa_type=DateTime(timezone=True)
    )
    usage_reservation_id: uuid.UUID | None = Field(default=None)
    last_error_code: str | None = Field(default=None, max_length=64)
    created_at: datetime = Field(
        default_factory=_utcnow, sa_type=DateTime(timezone=True)
    )
    updated_at: datetime = Field(
        default_factory=_utcnow, sa_type=DateTime(timezone=True)
    )


class CalendarBookingReceipt(SQLModel, table=True):  # type: ignore[call-arg]
    __tablename__ = "calendar_booking_receipt"
    __table_args__ = (
        UniqueConstraint(
            "confirmation_id",
            "operation",
            "generation",
            name="uq_calendar_booking_receipt_confirmation_operation_generation",
        ),
        UniqueConstraint(
            "workspace_id",
            "provider",
            "provider_receipt_id",
            name="uq_calendar_booking_receipt_provider_receipt",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(
        sa_column=Column(
            ForeignKey("suite_tenant.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    workspace_id: str = Field(max_length=64, index=True)
    confirmation_id: uuid.UUID = Field(
        sa_column=Column(
            ForeignKey("scheduling_confirmation.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    operation: str = Field(default="BOOK", max_length=32, index=True)
    generation: int = Field(default=1, ge=1)
    previous_provider_event_id: str | None = Field(default=None, max_length=255)
    provider: str = Field(max_length=32)
    provider_event_id: str = Field(max_length=255)
    provider_receipt_id: str = Field(max_length=255)
    command_digest: str = Field(max_length=64)
    created_at: datetime = Field(
        default_factory=_utcnow, sa_type=DateTime(timezone=True)
    )
