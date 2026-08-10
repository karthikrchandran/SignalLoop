"""Persistence + API models for the ``signals`` domain."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, ClassVar

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    ForeignKeyConstraint,
    Index,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Synonym, synonym
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SignalEvent(SQLModel, table=True):
    """Event row: signal."""

    __tablename__ = "signal_events"
    __table_args__ = (
        Index("idx_signal_contact", "contact_id"),
        Index("idx_signal_campaign", "campaign_id"),
        Index("idx_signal_type", "signal_type"),
        UniqueConstraint(
            "workspace_id",
            "source_event_id",
            "signal_type",
            name="uq_signal_workspace_source_type",
        ),
        UniqueConstraint("id", "workspace_id", name="uq_signal_event_id_workspace"),
        ForeignKeyConstraint(
            ["campaign_id", "workspace_id"],
            ["campaigns.id", "campaigns.workspace_id"],
            name="fk_signal_event_campaign_workspace",
        ),
        ForeignKeyConstraint(
            ["contact_id", "workspace_id"],
            ["contacts.id", "contacts.workspace_id"],
            name="fk_signal_event_contact_workspace",
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
    channel: str = Field(max_length=16)  # "email" or "voice"
    signal_type: str = Field(max_length=64)
    confidence: float = Field(default=0.0)
    source_event_id: uuid.UUID | None = Field(default=None)
    signal_metadata: dict[str, Any] | None = Field(
        default=None, sa_column=Column(JSON, name="metadata")
    )
    created_at: datetime = Field(
        default_factory=_utcnow, sa_type=DateTime(timezone=True)
    )
