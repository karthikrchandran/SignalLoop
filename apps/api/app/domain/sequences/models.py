"""Persistence + API models for the ``sequences`` domain."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from sqlalchemy import Column, DateTime, Index, JSON, String, Text, UniqueConstraint
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SequenceStatus(str, Enum):
    """Enumeration of sequence states."""
    active = "active"
    paused = "paused"
    stopped = "stopped"
    completed = "completed"


class SendRequestStatus(str, Enum):
    """Enumeration of send request states."""
    pending = "pending"
    sent = "sent"
    failed = "failed"


class EmailSequence(SQLModel, table=True):
    """Email sequence."""
    __tablename__ = "email_sequences"
    __table_args__ = (
        Index("idx_seq_campaign", "campaign_id"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    campaign_id: uuid.UUID = Field(foreign_key="campaigns.id", index=True)
    name: str = Field(max_length=255)
    active: bool = Field(default=True)
    created_by: uuid.UUID = Field()
    created_at: datetime = Field(default_factory=_utcnow, sa_type=DateTime(timezone=True))
    updated_at: datetime = Field(default_factory=_utcnow, sa_type=DateTime(timezone=True))


class SequenceStep(SQLModel, table=True):
    """Sequence step."""
    __tablename__ = "sequence_steps"
    __table_args__ = (
        Index("idx_step_sequence_order", "sequence_id", "step_order"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    sequence_id: uuid.UUID = Field(foreign_key="email_sequences.id", index=True)
    step_order: int = Field()
    delay_days: int = Field(default=0)
    subject_template: str = Field(max_length=255)
    body_template: str = Field(sa_type=Text)
    created_at: datetime = Field(default_factory=_utcnow, sa_type=DateTime(timezone=True))


class ContactSequenceState(SQLModel, table=True):
    """Enumeration of contact sequence states."""
    __tablename__ = "contact_sequence_state"
    __table_args__ = (
        UniqueConstraint("contact_id", "sequence_id", name="uq_contact_sequence"),
        Index("idx_css_status_next_send", "status", "next_send_at"),
        Index("idx_css_contact", "contact_id"),
        Index("idx_css_sequence_status", "sequence_id", "status"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    contact_id: uuid.UUID = Field(foreign_key="contacts.id", index=True)
    sequence_id: uuid.UUID = Field(foreign_key="email_sequences.id", index=True)
    current_step: int = Field(default=1)
    next_send_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    status: SequenceStatus = Field(default=SequenceStatus.active)
    signal_type: str | None = Field(default=None, max_length=128)
    signal_detected_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    created_at: datetime = Field(default_factory=_utcnow, sa_type=DateTime(timezone=True))
    updated_at: datetime = Field(default_factory=_utcnow, sa_type=DateTime(timezone=True))


class SendRequest(SQLModel, table=True):
    """Request payload: send."""
    __tablename__ = "send_requests"
    __table_args__ = (
        Index("idx_sr_css", "contact_sequence_state_id"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    contact_sequence_state_id: uuid.UUID = Field(
        foreign_key="contact_sequence_state.id", index=True
    )
    step_order: int = Field()
    idempotency_key: str = Field(unique=True, max_length=255, index=True)
    provider_message_id: str | None = Field(default=None, max_length=255)
    status: SendRequestStatus = Field(default=SendRequestStatus.pending)
    retry_count: int = Field(default=0)
    created_at: datetime = Field(default_factory=_utcnow, sa_type=DateTime(timezone=True))
    sent_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))


class EmailEvent(SQLModel, table=True):
    """Event row: email."""
    __tablename__ = "email_events"
    __table_args__ = (
        Index("idx_ee_send_request", "send_request_id"),
        Index("idx_ee_event_type", "event_type"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    send_request_id: uuid.UUID = Field(foreign_key="send_requests.id", index=True)
    event_type: str = Field(max_length=64)
    timestamp: datetime = Field(sa_type=DateTime(timezone=True))
    raw_payload: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
