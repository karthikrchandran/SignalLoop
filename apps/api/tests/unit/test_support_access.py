from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from app.domain.audit.audit_events import AuditEvent
from app.domain.support_access.service import (
    SupportAccessDenied,
    resolve_support_context,
)
from app.domain.tenants.models import SupportAccessGrant, Tenant, utc_now
from app.models import User


def _session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(
        engine,
        tables=[
            User.__table__,
            Tenant.__table__,
            SupportAccessGrant.__table__,
            AuditEvent.__table__,
        ],
    )
    return Session(engine)


def _operator() -> User:
    return User(
        id=uuid.uuid4(),
        email="support@example.test",
        hashed_password="not-used",
        is_superuser=True,
    )


def test_active_support_grant_is_tenant_bound_and_audited_on_use() -> None:
    with _session() as session:
        tenant = Tenant(key="ara", display_name="ARA")
        operator = _operator()
        session.add_all([tenant, operator])
        session.flush()
        grant = SupportAccessGrant(
            tenant_id=tenant.id,
            operator_user_id=operator.id,
            capabilities=["contacts.read"],
            reason="Investigating a support ticket",
            ticket_reference="SUP-123",
            approved_by=operator.id,
            expires_at=utc_now() + timedelta(hours=1),
        )
        session.add(grant)
        session.flush()

        context = resolve_support_context(
            session,
            grant_id=grant.id,
            operator_user_id=operator.id,
            tenant_id=tenant.id,
            required_capability="contacts.read",
        )

        assert context.grant_id == grant.id
        assert context.tenant_id == tenant.id
        event = session.exec(select(AuditEvent)).one()
        assert event.event_name == "support.grant.used"
        assert event.payload["capability"] == "contacts.read"


def test_expired_support_grant_is_denied_and_audited() -> None:
    with _session() as session:
        tenant = Tenant(key="ara", display_name="ARA")
        operator = _operator()
        session.add_all([tenant, operator])
        session.flush()
        grant = SupportAccessGrant(
            tenant_id=tenant.id,
            operator_user_id=operator.id,
            capabilities=["contacts.read"],
            reason="Investigating a support ticket",
            approved_by=operator.id,
            expires_at=utc_now() - timedelta(minutes=1),
        )
        session.add(grant)
        session.flush()

        with pytest.raises(SupportAccessDenied, match="SUPPORT_GRANT_EXPIRED"):
            resolve_support_context(
                session,
                grant_id=grant.id,
                operator_user_id=operator.id,
                tenant_id=tenant.id,
                required_capability="contacts.read",
            )

        event = session.exec(select(AuditEvent)).one()
        assert event.event_name == "support.grant.denied"
        assert event.payload["denial_reason"] == "SUPPORT_GRANT_EXPIRED"


def test_support_grant_cannot_be_used_for_another_tenant() -> None:
    with _session() as session:
        ara = Tenant(key="ara", display_name="ARA")
        ai = Tenant(key="ai", display_name="AI Consulting")
        operator = _operator()
        session.add_all([ara, ai, operator])
        session.flush()
        grant = SupportAccessGrant(
            tenant_id=ara.id,
            operator_user_id=operator.id,
            capabilities=["contacts.read"],
            reason="Investigating a support ticket",
            approved_by=operator.id,
            expires_at=utc_now() + timedelta(hours=1),
        )
        session.add(grant)
        session.flush()

        with pytest.raises(SupportAccessDenied, match="SUPPORT_GRANT_TENANT_MISMATCH"):
            resolve_support_context(
                session,
                grant_id=grant.id,
                operator_user_id=operator.id,
                tenant_id=ai.id,
                required_capability="contacts.read",
            )
