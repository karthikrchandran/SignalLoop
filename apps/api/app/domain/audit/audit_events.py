"""Module: ``audit events``."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Column, DateTime, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, Session, SQLModel

from app.core.db import engine
from app.core.middleware import get_request_id


class AuditEvent(SQLModel, table=True):
    """Event row: audit."""
    __tablename__ = "audit_events"
    __table_args__ = (
        Index("idx_audit_event_type", "event_name"),
        Index("idx_audit_workspace", "workspace_id"),
        Index("idx_audit_created", "created_at"),
        Index("idx_audit_workspace_created", "workspace_id", "created_at"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    event_name: str = Field(sa_type=String(255))
    workspace_id: str = Field(sa_type=String(64))
    actor_id: uuid.UUID | None = Field(default=None)
    actor_role: str | None = Field(default=None, sa_type=String(64))
    resource_type: str | None = Field(default=None, sa_type=String(128))
    resource_id: str | None = Field(default=None, sa_type=String(255))
    correlation_id: str | None = Field(default=None, sa_type=String(255))
    payload: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON().with_variant(JSONB(), "postgresql")),
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_type=DateTime(timezone=True),
    )


def audit_actor_role(user: Any) -> str:
    """Return the audit actor role label for a user-like object."""
    if getattr(user, "is_superuser", False):
        return "super_admin"
    return str(getattr(user, "role", "unknown") or "unknown")


def _resolve_correlation_id(correlation_id: str | None) -> str | None:
    return correlation_id or get_request_id() or None


def build_audit_event(
    *,
    event_name: str,
    workspace_id: str,
    payload: dict[str, Any] | None = None,
    actor_id: uuid.UUID | None = None,
    actor_role: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    correlation_id: str | None = None,
) -> AuditEvent:
    """Build a normalized audit event row."""
    return AuditEvent(
        event_name=event_name,
        workspace_id=workspace_id,
        payload=payload or {},
        actor_id=actor_id,
        actor_role=actor_role,
        resource_type=resource_type,
        resource_id=resource_id,
        correlation_id=_resolve_correlation_id(correlation_id),
    )


def append_audit_event_to_session(
    session: Session,
    *,
    event_name: str,
    workspace_id: str,
    payload: dict[str, Any] | None = None,
    actor_id: uuid.UUID | None = None,
    actor_role: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    correlation_id: str | None = None,
) -> AuditEvent:
    """Append an audit event to an existing transaction."""
    event = build_audit_event(
        event_name=event_name,
        workspace_id=workspace_id,
        payload=payload,
        actor_id=actor_id,
        actor_role=actor_role,
        resource_type=resource_type,
        resource_id=resource_id,
        correlation_id=correlation_id,
    )
    session.add(event)
    return event


async def append_audit_event(
    *,
    event_name: str,
    workspace_id: str,
    payload: dict[str, Any] | None = None,
    actor_id: uuid.UUID | None = None,
    actor_role: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    correlation_id: str | None = None,
) -> None:
    """Append audit event."""
    event = build_audit_event(
        event_name=event_name,
        workspace_id=workspace_id,
        payload=payload,
        actor_id=actor_id,
        actor_role=actor_role,
        resource_type=resource_type,
        resource_id=resource_id,
        correlation_id=correlation_id,
    )

    def _sync_write() -> None:
        with Session(engine) as session:
            session.add(event)
            session.commit()

    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _sync_write)
