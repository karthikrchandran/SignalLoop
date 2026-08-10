from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.domain.identity.models import OidcIdentity, OidcSession
from app.domain.identity.sessions import (
    SessionRevoked,
    create_session,
    resolve_session,
    revoke_session,
)
from app.models import User


def _session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(
        engine,
        tables=[User.__table__, OidcIdentity.__table__, OidcSession.__table__],
    )
    return Session(engine)


def test_session_resolves_until_user_version_changes() -> None:
    with _session() as session:
        user = User(
            id=uuid.uuid4(),
            email="user@example.test",
            hashed_password="local-only",
            auth_session_version=1,
        )
        session.add(user)
        session.commit()
        token = create_session(session, user=user, ttl=timedelta(minutes=5))
        session.commit()

        assert resolve_session(session, token) == user.id
        user.auth_session_version = 2
        session.add(user)
        session.commit()
        with pytest.raises(SessionRevoked):
            resolve_session(session, token)


def test_session_revoke_prevents_future_resolution() -> None:
    with _session() as session:
        user = User(
            id=uuid.uuid4(),
            email="user@example.test",
            hashed_password="local-only",
        )
        session.add(user)
        session.commit()
        token = create_session(session, user=user, ttl=timedelta(minutes=5))
        session.commit()
        revoke_session(session, token)
        session.commit()
        with pytest.raises(SessionRevoked):
            resolve_session(session, token)


def test_expired_session_is_rejected() -> None:
    with _session() as session:
        user = User(
            id=uuid.uuid4(),
            email="user@example.test",
            hashed_password="local-only",
        )
        session.add(user)
        session.commit()
        token = create_session(
            session,
            user=user,
            ttl=timedelta(seconds=-1),
        )
        session.commit()
        with pytest.raises(SessionRevoked):
            resolve_session(session, token)
