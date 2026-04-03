from __future__ import annotations

import uuid
from datetime import datetime, timezone

from typing import Any

from sqlalchemy import Column, DateTime, Index, JSON, String
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SignalEvent(SQLModel, table=True):
    __tablename__ = "signal_events"
    __table_args__ = (
        Index("idx_signal_contact", "contact_id"),
        Index("idx_signal_campaign", "campaign_id"),
        Index("idx_signal_type", "signal_type"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    contact_id: uuid.UUID = Field(foreign_key="contacts.id", index=True)
    campaign_id: uuid.UUID = Field(foreign_key="campaigns.id", index=True)
    channel: str = Field(max_length=16)  # "email" or "voice"
    signal_type: str = Field(max_length=64)
    confidence: float = Field(default=0.0)
    source_event_id: uuid.UUID | None = Field(default=None)
    signal_metadata: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON, name="metadata"))
    created_at: datetime = Field(default_factory=_utcnow, sa_type=DateTime(timezone=True))
