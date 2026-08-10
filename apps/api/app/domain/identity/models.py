"""Immutable external identity projections."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, String, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class OidcIdentity(SQLModel, table=True):
    """Map one immutable OIDC issuer/subject pair to a local user."""

    __tablename__ = "oidc_identity"
    __table_args__ = (
        UniqueConstraint("issuer", "subject", name="uq_oidc_identity_issuer_subject"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    issuer: str = Field(sa_column=Column(String(512), nullable=False, index=True))
    subject: str = Field(sa_column=Column(String(255), nullable=False))
    user_id: uuid.UUID = Field(
        sa_column=Column(ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    email_snapshot: str = Field(sa_column=Column(String(320), nullable=False))
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    last_login_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
