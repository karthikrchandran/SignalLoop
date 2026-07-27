"""Persistence + API models for the ``scheduling`` domain."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import DateTime, Text
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SchedulingRequestStatus(str, Enum):
    """Lifecycle states for a scheduling request."""

    pending = "pending"        # intent detected, awaiting action
    link_sent = "link_sent"    # meeting link sent to contact
    booked = "booked"          # Calendly confirmed booking
    cancelled = "cancelled"    # cancelled or no-show


class SchedulingRequestSource(str, Enum):
    """How the scheduling request was triggered."""

    voice_call = "voice_call"
    email_reply = "email_reply"
    manual = "manual"


class SchedulingRequest(SQLModel, table=True):
    """A scheduling request created when a contact expresses meeting intent."""

    __tablename__ = "scheduling_requests"
    __table_args__ = ({"extend_existing": True},)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    contact_id: uuid.UUID = Field(foreign_key="contacts.id")
    campaign_id: uuid.UUID = Field(foreign_key="campaigns.id")
    signal_event_id: uuid.UUID | None = Field(default=None, foreign_key="signal_events.id")

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
