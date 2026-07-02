"""Persistence + API models for the ``voice`` domain."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, ClassVar

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Index,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Synonym, synonym
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CallRequestStatus(str, Enum):
    """Enumeration of call request states."""

    queued = "queued"
    in_progress = "in_progress"
    completed = "completed"
    failed = "failed"


class CallOutcome(str, Enum):
    """Enumeration of call outcomes."""

    answered = "answered"
    voicemail = "voicemail"
    no_answer = "no_answer"
    busy = "busy"
    failed = "failed"


class VoiceScript(SQLModel, table=True):
    """Script row: voice."""

    __tablename__ = "voice_scripts"
    __table_args__ = (Index("idx_vs_campaign", "campaign_id"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    campaign_id: uuid.UUID = Field(foreign_key="campaigns.id", index=True)
    name: str = Field(max_length=255)
    content: str = Field(sa_type=Text)
    active: bool = Field(default=True)
    created_by: uuid.UUID = Field()
    created_at: datetime = Field(
        default_factory=_utcnow, sa_type=DateTime(timezone=True)
    )
    updated_at: datetime = Field(
        default_factory=_utcnow, sa_type=DateTime(timezone=True)
    )


class CallRequest(SQLModel, table=True):
    """Request payload: call."""

    __tablename__ = "call_requests"
    __table_args__ = (
        Index("idx_cr_status_scheduled", "status", "scheduled_at"),
        Index("idx_cr_campaign", "campaign_id"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    shared_contact_id: uuid.UUID = Field(
        alias="contact_id",
        sa_column=Column("contact_id", Uuid(), index=True, nullable=False)
    )
    contact_id: ClassVar[Synonym] = synonym("shared_contact_id")
    campaign_id: uuid.UUID = Field(foreign_key="campaigns.id", index=True)
    voice_script_id: uuid.UUID = Field(foreign_key="voice_scripts.id")
    trigger_reason: str = Field(max_length=64)
    status: CallRequestStatus = Field(default=CallRequestStatus.queued)
    scheduled_at: datetime = Field(sa_type=DateTime(timezone=True))
    created_at: datetime = Field(
        default_factory=_utcnow, sa_type=DateTime(timezone=True)
    )


class CallSession(SQLModel, table=True):
    """Session row: call."""

    __tablename__ = "call_sessions"
    __table_args__ = (
        UniqueConstraint("call_request_id", name="uq_call_sessions_call_request_id"),
        Index("idx_cs_call_request", "call_request_id"),
        Index("idx_cs_outcome", "outcome"),
        Index("idx_cs_twilio_status", "twilio_status"),
        Index(
            "uq_cs_twilio_call_sid_nonempty",
            "twilio_call_sid",
            unique=True,
            postgresql_where=text("twilio_call_sid <> ''"),
            sqlite_where=text("twilio_call_sid <> ''"),
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    call_request_id: uuid.UUID = Field(foreign_key="call_requests.id", index=True)
    twilio_call_sid: str = Field(max_length=64, default="")
    twilio_account_sid: str | None = Field(default=None, max_length=64)
    twilio_status: str | None = Field(default=None, max_length=32)
    twilio_status_updated_at: datetime | None = Field(
        default=None, sa_type=DateTime(timezone=True)
    )
    duration_seconds: int = Field(default=0)
    outcome: CallOutcome | None = Field(default=None)
    recording_url: str | None = Field(default=None, max_length=1024)
    transcript: str | None = Field(default=None, sa_type=Text)
    unanswered_questions: dict[str, Any] | None = Field(
        default=None, sa_column=Column(JSON)
    )
    scheduling_interest: bool = Field(default=False)
    postcall_status: str | None = Field(default=None, max_length=32)
    post_call_processed: bool = Field(default=False)
    created_at: datetime = Field(
        default_factory=_utcnow, sa_type=DateTime(timezone=True)
    )
