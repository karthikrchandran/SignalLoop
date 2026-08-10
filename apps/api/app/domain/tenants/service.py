"""Tenant invitation lifecycle services."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlmodel import Session, select

from app.domain.tenants.models import TenantInvitation


class InvitationAlreadyUsed(ValueError):
    """Raised for invalid, expired, or previously accepted invitations."""


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_invitation(
    session: Session, *, tenant_id: UUID, email: str, ttl: timedelta
) -> tuple[str, TenantInvitation]:
    raw_token = secrets.token_urlsafe(32)
    invitation = TenantInvitation(
        tenant_id=tenant_id,
        email=email.strip().lower(),
        token_digest=_digest(raw_token),
        expires_at=datetime.now(timezone.utc) + ttl,
    )
    session.add(invitation)
    session.flush()
    return raw_token, invitation


def accept_invitation(session: Session, raw_token: str) -> TenantInvitation:
    invitation = session.exec(
        select(TenantInvitation).where(TenantInvitation.token_digest == _digest(raw_token))
    ).one_or_none()
    if invitation is None or invitation.status != "PENDING":
        raise InvitationAlreadyUsed("invitation is not available")
    if invitation.expires_at is not None:
        expires_at = invitation.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at <= datetime.now(timezone.utc):
            raise InvitationAlreadyUsed("invitation is not available")
    invitation.status = "ACCEPTED"
    invitation.accepted_at = datetime.now(timezone.utc)
    session.add(invitation)
    return invitation
