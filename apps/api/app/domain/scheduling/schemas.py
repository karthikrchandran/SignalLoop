"""Request/response schemas for the ``scheduling`` domain."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlmodel import SQLModel


class SchedulingRequestPublic(SQLModel):
    """API response model for a scheduling request."""

    id: uuid.UUID
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
