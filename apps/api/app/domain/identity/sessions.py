"""Opaque server-side OIDC sessions."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlmodel import Session, select

from app.domain.identity.models import OidcSession
from app.models import User


class SessionRevoked(ValueError):
    """Raised for expired, revoked, or version-invalid sessions."""


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def create_session(session: Session, *, user: User, ttl: timedelta) -> str:
    token = secrets.token_urlsafe(48)
    session.add(
        OidcSession(
            token_digest=_digest(token),
            user_id=user.id,
            session_version=user.auth_session_version,
            expires_at=datetime.now(timezone.utc) + ttl,
        )
    )
    return token


def resolve_session(session: Session, token: str) -> UUID:
    record = session.exec(
        select(OidcSession).where(OidcSession.token_digest == _digest(token))
    ).one_or_none()
    if record is None or record.revoked_at is not None:
        raise SessionRevoked("session is not active")
    if _as_utc(record.expires_at) <= datetime.now(timezone.utc):
        raise SessionRevoked("session is expired")
    user = session.get(User, record.user_id)
    if (
        user is None
        or not user.is_active
        or user.auth_session_version != record.session_version
    ):
        raise SessionRevoked("session version is invalid")
    return user.id


def revoke_session(session: Session, token: str) -> None:
    record = session.exec(
        select(OidcSession).where(OidcSession.token_digest == _digest(token))
    ).one_or_none()
    if record is not None and record.revoked_at is None:
        record.revoked_at = datetime.now(timezone.utc)
        session.add(record)
