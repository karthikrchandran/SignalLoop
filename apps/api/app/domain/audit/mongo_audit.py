from __future__ import annotations

import asyncio
import functools
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Column, DateTime, Index, JSON, String, Text
from sqlmodel import Field, Session, SQLModel

from app.core.db import engine


class AuditEvent(SQLModel, table=True):
    __tablename__ = "audit_events"
    __table_args__ = (
        Index("idx_audit_event_type", "event_name"),
        Index("idx_audit_workspace", "workspace_id"),
        Index("idx_audit_created", "created_at"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    event_name: str = Field(sa_type=String(255))
    workspace_id: str = Field(sa_type=String(64))
    actor_id: uuid.UUID | None = Field(default=None)
    resource_type: str | None = Field(default=None, sa_type=String(128))
    resource_id: str | None = Field(default=None, sa_type=String(255))
    payload: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_type=DateTime(timezone=True),
    )


async def append_audit_event(
    *,
    event_name: str,
    workspace_id: str,
    payload: dict[str, Any],
    actor_id: uuid.UUID | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
) -> None:
    event = AuditEvent(
        event_name=event_name,
        workspace_id=workspace_id,
        payload=payload,
        actor_id=actor_id,
        resource_type=resource_type,
        resource_id=resource_id,
    )

    def _sync_write() -> None:
        with Session(engine) as session:
            session.add(event)
            session.commit()

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _sync_write)
