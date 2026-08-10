"""Module: ``suppression``."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, String, UniqueConstraint
from sqlmodel import Field, Session, SQLModel, select


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class EmailSuppression(SQLModel, table=True):
    """Suppression row: email."""
    __tablename__ = "email_suppressions"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "email",
            "reason",
            name="uq_suppression_workspace_email_reason",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workspace_id: str = Field(max_length=64, index=True)
    email: str = Field(sa_type=String(255), index=True)
    reason: str = Field(max_length=64)
    created_at: datetime = Field(default_factory=_utcnow, sa_type=DateTime(timezone=True))


def is_email_suppressed(session: Session, workspace_id: str, email: str) -> bool:
    """Return whether *email* is suppressed inside *workspace_id*."""
    return session.exec(
        select(EmailSuppression.id).where(
            EmailSuppression.workspace_id == workspace_id,
            EmailSuppression.email == email,
        )
    ).first() is not None
