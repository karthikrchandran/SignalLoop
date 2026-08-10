from __future__ import annotations

from datetime import timedelta

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.domain.tenants.models import Tenant, TenantInvitation
from app.domain.tenants.service import (
    InvitationAlreadyUsed,
    accept_invitation,
    create_invitation,
)


def _session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine, tables=[Tenant.__table__, TenantInvitation.__table__])
    return Session(engine)


def test_invitation_token_is_returned_once_and_acceptance_is_one_use() -> None:
    with _session() as session:
        tenant = Tenant(key="ai-consulting", display_name="AI Consulting")
        session.add(tenant)
        session.commit()
        raw_token, invitation = create_invitation(
            session,
            tenant_id=tenant.id,
            email="owner@example.test",
            ttl=timedelta(hours=1),
        )
        session.commit()
        assert raw_token
        assert invitation.token_digest != raw_token
        assert accept_invitation(session, raw_token).id == invitation.id
        session.commit()
        with pytest.raises(InvitationAlreadyUsed):
            accept_invitation(session, raw_token)


def test_unknown_invitation_token_does_not_reveal_tenant() -> None:
    with _session() as session:
        with pytest.raises(InvitationAlreadyUsed):
            accept_invitation(session, "not-a-valid-token")
