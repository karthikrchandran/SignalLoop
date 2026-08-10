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
    ForeignKeyConstraint,
    Index,
    Text,
    UniqueConstraint,
    Uuid,
    event,
    text,
)
from sqlalchemy import (
    select as sa_select,
)
from sqlalchemy.engine import Connection
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
    __table_args__ = (
        Index("idx_vs_campaign", "campaign_id"),
        UniqueConstraint("id", "workspace_id", name="uq_voice_script_id_workspace"),
        ForeignKeyConstraint(
            ["campaign_id", "workspace_id"],
            ["campaigns.id", "campaigns.workspace_id"],
            name="fk_voice_script_campaign_workspace",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workspace_id: str = Field(max_length=64, index=True)
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
        ForeignKeyConstraint(
            ["campaign_id", "workspace_id"],
            ["campaigns.id", "campaigns.workspace_id"],
            name="fk_call_request_campaign_workspace",
        ),
        ForeignKeyConstraint(
            ["contact_id", "workspace_id"],
            ["contacts.id", "contacts.workspace_id"],
            name="fk_call_request_contact_workspace",
        ),
        ForeignKeyConstraint(
            ["voice_script_id", "workspace_id"],
            ["voice_scripts.id", "voice_scripts.workspace_id"],
            name="fk_call_request_script_workspace",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workspace_id: str = Field(max_length=64, index=True)
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
    media_stream_nonce_hash: str | None = Field(default=None, max_length=64)
    media_stream_token_expires_at: datetime | None = Field(  # type: ignore[call-overload]
        default=None, sa_type=DateTime(timezone=True)
    )
    media_stream_token_consumed_at: datetime | None = Field(  # type: ignore[call-overload]
        default=None, sa_type=DateTime(timezone=True)
    )
    callback_correlation_hash: str | None = Field(default=None, max_length=64, index=True)
    callback_correlation_expires_at: datetime | None = Field(  # type: ignore[call-overload]
        default=None, sa_type=DateTime(timezone=True)
    )
    created_at: datetime = Field(
        default_factory=_utcnow, sa_type=DateTime(timezone=True)
    )


@event.listens_for(VoiceScript, "before_insert")
def _derive_voice_script_workspace(
    _mapper: object, connection: Connection, target: VoiceScript
) -> None:
    if target.workspace_id:
        return
    campaigns = SQLModel.metadata.tables["campaigns"]
    target.workspace_id = connection.execute(
        sa_select(campaigns.c.workspace_id).where(campaigns.c.id == target.campaign_id)
    ).scalar_one()
