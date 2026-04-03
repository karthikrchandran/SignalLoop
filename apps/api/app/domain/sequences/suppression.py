from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, String, UniqueConstraint
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class EmailSuppression(SQLModel, table=True):
    __tablename__ = "email_suppressions"
    __table_args__ = (
        UniqueConstraint("email", "reason", name="uq_suppression_email_reason"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    email: str = Field(sa_type=String(255), index=True)
    reason: str = Field(max_length=64)
    created_at: datetime = Field(default_factory=_utcnow, sa_type=DateTime(timezone=True))
