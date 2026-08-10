from __future__ import annotations

import uuid

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel, create_engine

from app.domain.identity.models import OidcIdentity
from app.models import User


def _session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine, tables=[User.__table__, OidcIdentity.__table__])
    return Session(engine)


def _user(email: str) -> User:
    return User(
        id=uuid.uuid4(),
        email=email,
        hashed_password="local-only",
    )


def test_oidc_identity_is_unique_per_issuer_subject() -> None:
    with _session() as session:
        first_user = _user("one@example.test")
        second_user = _user("two@example.test")
        session.add(first_user)
        session.add(second_user)
        session.flush()
        session.add(
            OidcIdentity(
                issuer="https://id.example.test",
                subject="user-1",
                user_id=first_user.id,
                email_snapshot="one@example.test",
            )
        )
        session.commit()

        session.add(
            OidcIdentity(
                issuer="https://id.example.test",
                subject="user-1",
                user_id=second_user.id,
                email_snapshot="two@example.test",
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()


def test_oidc_identity_keeps_email_as_snapshot_not_identity_key() -> None:
    with _session() as session:
        user = _user("one@example.test")
        session.add(user)
        session.flush()
        identity = OidcIdentity(
            issuer="https://id.example.test",
            subject="stable-subject",
            user_id=user.id,
            email_snapshot="renamed@example.test",
        )
        session.add(identity)
        session.commit()

        loaded = session.get(OidcIdentity, identity.id)
        assert loaded is not None
        assert loaded.subject == "stable-subject"
        assert loaded.email_snapshot == "renamed@example.test"
