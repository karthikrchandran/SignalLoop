"""Request/response schemas for the ``scheduling`` domain."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import ConfigDict, Field, field_validator
from sqlmodel import SQLModel


class SchedulingRequestPublic(SQLModel):
    """API response model for a scheduling request."""

    id: uuid.UUID
    workspace_id: str
    calendly_state: str | None = None
    contact_id: uuid.UUID
    campaign_id: uuid.UUID
    signal_event_id: uuid.UUID | None
    status: str
    source: str
    meeting_link: str | None
    calendly_event_id: str | None
    meeting_datetime: datetime | None
    assigned_to_email: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class SchedulingRequestsPublic(SQLModel):
    """Paginated list of scheduling requests."""

    data: list[SchedulingRequestPublic]
    count: int


class SchedulingRequestCreate(SQLModel):
    """Payload for creating a scheduling request manually."""

    contact_id: uuid.UUID
    campaign_id: uuid.UUID
    signal_event_id: uuid.UUID | None = None
    source: str = "manual"
    assigned_to_email: str | None = None
    notes: str | None = None


class SchedulingRequestUpdate(SQLModel):
    """Payload for updating a scheduling request."""

    status: str | None = None
    meeting_link: str | None = None
    assigned_to_email: str | None = None
    notes: str | None = None


class CalendlyWebhookPayload(SQLModel):
    """Minimal shape of a Calendly webhook invitee.created payload."""

    event: str
    payload: dict


class CalendarMeetingTypeCreate(SQLModel):
    model_config = ConfigDict(extra="forbid")

    workspace_id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    duration_minutes: int = Field(ge=5, le=480)
    timezone: str = Field(min_length=1, max_length=64)
    working_hours: dict[str, list[list[str]]]
    holiday_dates: list[date] = Field(default_factory=list)
    buffer_before_minutes: int = Field(default=0, ge=0, le=1440)
    buffer_after_minutes: int = Field(default=0, ge=0, le=1440)
    minimum_notice_minutes: int = Field(default=60, ge=0, le=10080)


class CalendarProviderBindingCreate(SQLModel):
    model_config = ConfigDict(extra="forbid")

    workspace_id: str = Field(min_length=1, max_length=64)
    provider: str = Field(pattern=r"^CALENDLY$")
    provider_account_ref: str = Field(min_length=1, max_length=255)
    credential_secret_ref: str = Field(min_length=1, max_length=1024)
    capabilities: set[str] = Field(min_length=1)

    @field_validator("credential_secret_ref")
    @classmethod
    def secret_reference_only(cls, value: str) -> str:
        if not value.startswith(("secret://", "env://")):
            raise ValueError("calendar credentials must be secret references")
        return value


class CalendarOfferCreate(SQLModel):
    model_config = ConfigDict(extra="forbid")

    workspace_id: str = Field(min_length=1, max_length=64)
    meeting_type_id: uuid.UUID
    start_date: date
    end_date: date
    expires_in_minutes: int = Field(default=60, ge=5, le=10080)
    limit: int = Field(default=10, ge=1, le=50)


class CalendarConfirmationCreate(SQLModel):
    model_config = ConfigDict(extra="forbid")

    workspace_id: str = Field(min_length=1, max_length=64)
    deployment_id: uuid.UUID
    binding_id: uuid.UUID
    selected_slot_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    confirmed_by: str = Field(min_length=3, max_length=255)
    operation: Literal["BOOK", "RESCHEDULE"] = "BOOK"
    predecessor_job_id: uuid.UUID | None = None


class CalendarCancellationCreate(SQLModel):
    model_config = ConfigDict(extra="forbid")

    workspace_id: str = Field(min_length=1, max_length=64)
    reason: str = Field(min_length=3, max_length=500)


class CalendarReconciliationCreate(SQLModel):
    model_config = ConfigDict(extra="forbid")

    workspace_id: str = Field(min_length=1, max_length=64)
    provider_accepted: bool
    provider_evidence_id: str = Field(min_length=3, max_length=255)
    reason: str = Field(min_length=3, max_length=500)


class CalendarReplayCreate(SQLModel):
    model_config = ConfigDict(extra="forbid")

    workspace_id: str = Field(min_length=1, max_length=64)
    reason: str = Field(min_length=3, max_length=500)
