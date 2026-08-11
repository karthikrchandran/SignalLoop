from __future__ import annotations

from datetime import timedelta

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from app.domain.identity.models import OidcIdentity
from app.domain.identity.service import (
    OidcAuthorizationError,
    activate_oidc_identity,
    activate_oidc_identity_for_invitation,
)
from app.domain.tenants.models import SuiteMembership, Tenant, TenantInvitation
from app.domain.tenants.service import create_invitation
from app.models import User


def _session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(
        engine,
        tables=[
            User.__table__,
            OidcIdentity.__table__,
            Tenant.__table__,
            TenantInvitation.__table__,
            SuiteMembership.__table__,
        ],
    )
    return Session(engine)


def test_activation_binds_an_invitation_to_one_verified_identity() -> None:
    with _session() as session:
        tenant = Tenant(key="ara-global", display_name="ARA Global")
        session.add(tenant)
        session.commit()
        invitation_token, invitation = create_invitation(
            session,
            tenant_id=tenant.id,
            email="owner@example.test",
            ttl=timedelta(hours=1),
        )

        user = activate_oidc_identity(
            session,
            tenant_id=tenant.id,
            invitation_token=invitation_token,
            issuer="https://id.example.test",
            subject="subject-1",
            email="OWNER@example.test",
            email_verified=True,
        )
        session.commit()

        assert user.email == "owner@example.test"
        assert session.get(TenantInvitation, invitation.id).status == "ACCEPTED"  # type: ignore[union-attr]
        assert session.exec(select(OidcIdentity)).one().user_id == user.id
        assert session.exec(select(SuiteMembership)).one().tenant_id == tenant.id


def test_activation_rejects_an_invitation_when_email_is_not_verified_or_exact() -> None:
    with _session() as session:
        tenant = Tenant(key="ara-global", display_name="ARA Global")
        session.add(tenant)
        session.commit()
        invitation_token, invitation = create_invitation(
            session,
            tenant_id=tenant.id,
            email="owner@example.test",
            ttl=timedelta(hours=1),
        )

        with pytest.raises(OidcAuthorizationError):
            activate_oidc_identity(
                session,
                tenant_id=tenant.id,
                invitation_token=invitation_token,
                issuer="https://id.example.test",
                subject="subject-1",
                email="other@example.test",
                email_verified=False,
            )

        assert session.get(TenantInvitation, invitation.id).status == "PENDING"  # type: ignore[union-attr]
        assert session.exec(select(User)).all() == []


def test_activation_can_use_a_server_bound_invitation_id() -> None:
    with _session() as session:
        tenant = Tenant(key="ara-global", display_name="ARA Global")
        session.add(tenant)
        session.commit()
        _, invitation = create_invitation(
            session,
            tenant_id=tenant.id,
            email="owner@example.test",
            ttl=timedelta(hours=1),
        )

        user = activate_oidc_identity_for_invitation(
            session,
            tenant_id=tenant.id,
            invitation_id=invitation.id,
            issuer="https://id.example.test",
            subject="subject-1",
            email="owner@example.test",
            email_verified=True,
        )

        assert user.email == "owner@example.test"


def test_known_identity_requires_an_active_membership_in_the_bound_tenant() -> None:
    with _session() as session:
        tenant = Tenant(key="ara-global", display_name="ARA Global")
        user = User(email="owner@example.test", hashed_password="oidc-only")
        session.add_all([tenant, user])
        session.commit()
        session.add(
            OidcIdentity(
                issuer="https://id.example.test",
                subject="subject-1",
                user_id=user.id,
                email_snapshot=user.email,
            )
        )
        session.add(SuiteMembership(tenant_id=tenant.id, user_id=user.id, status="SUSPENDED"))
        session.commit()

        with pytest.raises(OidcAuthorizationError):
            activate_oidc_identity(
                session,
                tenant_id=tenant.id,
                invitation_token=None,
                issuer="https://id.example.test",
                subject="subject-1",
                email="owner@example.test",
                email_verified=True,
            )
