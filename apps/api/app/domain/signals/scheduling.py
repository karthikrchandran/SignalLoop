"""Module: ``scheduling``."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import ClassVar

from sqlalchemy import Column, DateTime, Index, Uuid
from sqlalchemy.orm import Synonym, synonym
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SchedulingStatus(str, Enum):
    """Enumeration of scheduling states."""

    pending = "pending"
    contacted = "contacted"
    booked = "booked"
    declined = "declined"


class SchedulingRequest(SQLModel, table=True):
    """Request payload: scheduling."""

    __tablename__ = "scheduling_requests"
    __table_args__ = (
        Index("idx_sched_contact", "contact_id"),
        Index("idx_sched_status", "status"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    shared_contact_id: uuid.UUID = Field(
        alias="contact_id",
        sa_column=Column("contact_id", Uuid(), index=True, nullable=False)
    )
    contact_id: ClassVar[Synonym] = synonym("shared_contact_id")
    campaign_id: uuid.UUID = Field(foreign_key="campaigns.id", index=True)
    signal_event_id: uuid.UUID = Field(foreign_key="signal_events.id")
    status: SchedulingStatus = Field(default=SchedulingStatus.pending)
    created_at: datetime = Field(
        default_factory=_utcnow, sa_type=DateTime(timezone=True)
    )
