"""Persistence helpers for installation keys and assertion replay protection."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.domain.tenants.models import NativeWorkloadReplay, ProductInstallation


def configure_installation_key(
    session: Session,
    installation: ProductInstallation,
    *,
    key_id: str,
    public_key: str,
    valid_from: datetime | None = None,
    valid_to: datetime | None = None,
) -> ProductInstallation:
    """Store public verification material only; private key remains in a secret manager."""

    installation.workload_key_id = key_id
    installation.workload_public_key = public_key
    installation.workload_key_status = "ACTIVE"
    installation.workload_key_valid_from = valid_from or datetime.now(timezone.utc)
    installation.workload_key_valid_to = valid_to
    installation.workload_key_version += 1
    session.add(installation)
    session.flush()
    return installation


def consume_jti(
    session: Session,
    *,
    installation_id: uuid.UUID,
    jti: uuid.UUID,
    expires_at: datetime,
) -> bool:
    """Atomically consume an assertion JTI; return false for replay."""

    if session.exec(
        select(NativeWorkloadReplay).where(
            NativeWorkloadReplay.installation_id == installation_id,
            NativeWorkloadReplay.jti == jti,
            NativeWorkloadReplay.expires_at > datetime.now(timezone.utc),
        )
    ).first():
        return False
    session.add(
        NativeWorkloadReplay(
            installation_id=installation_id,
            jti=jti,
            expires_at=expires_at,
        )
    )
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        return False
    return True


def replay_expiry(exp: int) -> datetime:
    return datetime.fromtimestamp(exp, tz=timezone.utc) + timedelta(seconds=30)
