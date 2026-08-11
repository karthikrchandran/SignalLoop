from __future__ import annotations

from sqlmodel import Session, SQLModel, create_engine, select

from app.api.routes.revenue_interventions import (
    InterventionAction,
    InterventionProposal,
    approve,
    list_interventions,
    propose_intervention,
)
from app.domain.audit.audit_events import AuditEvent
from app.domain.revenue_intelligence.persistence import RevenueInterventionStore
from app.domain.revenue_intelligence.persistence_models import (
    RevenueInterventionDispatch,
    RevenueInterventionRecord,
    RevenueSignalRecord,
)
from app.domain.tenants.models import (
    ProductCode,
    RoleBundle,
    SuiteMembership,
    SuiteRoleAssignment,
    Tenant,
    TenantEntitlement,
)
from app.models import User


def _session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(
        engine,
        tables=[
            User.__table__,
            Tenant.__table__,
            TenantEntitlement.__table__,
            SuiteMembership.__table__,
            SuiteRoleAssignment.__table__,
            RevenueSignalRecord.__table__,
            RevenueInterventionRecord.__table__,
            RevenueInterventionDispatch.__table__,
            AuditEvent.__table__,
        ],
    )
    return Session(engine)


def _user_and_tenant(session: Session) -> tuple[User, Tenant]:
    user = User(email="operator@example.test", hashed_password="not-used")
    tenant = Tenant(key="ara-global", display_name="ARA Global")
    session.add(user)
    session.add(tenant)
    session.flush()
    session.add(
        TenantEntitlement(
            tenant_id=tenant.id,
            product_code=ProductCode.REVENUE_OS,
        )
    )
    membership = SuiteMembership(tenant_id=tenant.id, user_id=user.id)
    session.add(membership)
    session.flush()
    session.add(
        SuiteRoleAssignment(
            membership_id=membership.id,
            role_bundle=RoleBundle.REVENUE_OS_ADMIN,
        )
    )
    session.commit()
    return user, tenant


def test_revenue_intervention_route_uses_durable_store_without_caller_policy_flags() -> None:
    with _session() as session:
        user, tenant = _user_and_tenant(session)
        signal = RevenueInterventionStore(session).record_signal(
            tenant_id=tenant.id,
            signal_type="stalled_opportunity",
            subject_ref="opportunity-7",
            confidence=0.91,
            evidence_refs=["signal:opportunity-7"],
            evidence_hash="sha256:signal-7",
            source="local-revenueos",
            consent_verified=True,
            policy_allowed=True,
            idempotency_key="signal-7-v1",
        )

        created = propose_intervention(
            body=InterventionProposal(
                signal_id=signal.id,
                action="send_email",
                action_payload={
                    "to": "owner@example.test",
                    "subject": "Review account",
                    "body_text": "Review account A.",
                    "body_html": "<p>Review account A.</p>",
                },
                evidence_refs=["signal:opportunity-7"],
            ),
            session=session,
            current_user=user,
            x_tenant_key="ara-global",
            idempotency_key="intervention-7-v1",
        )
        listed = list_interventions(
            session=session,
            current_user=user,
            x_tenant_key="ara-global",
        )

        assert created["tenant_key"] == "ara-global"
        assert created["status"] == "PROPOSED"
        assert listed["data"][0]["id"] == created["id"]


def test_revenue_intervention_approval_enqueues_durable_dispatch() -> None:
    with _session() as session:
        user, tenant = _user_and_tenant(session)
        store = RevenueInterventionStore(session)
        signal = store.record_signal(
            tenant_id=tenant.id,
            signal_type="stalled_opportunity",
            subject_ref="opportunity-7",
            confidence=0.91,
            evidence_refs=["signal:opportunity-7"],
            evidence_hash="sha256:signal-7",
            source="local-revenueos",
            consent_verified=True,
            policy_allowed=True,
            idempotency_key="signal-7-v1",
        )
        intervention = store.propose_intervention(
            tenant_id=tenant.id,
            signal_id=signal.id,
            action="send_email",
            action_payload={"to": "owner@example.test"},
            evidence_refs=["signal:opportunity-7"],
            idempotency_key="intervention-7-v1",
        )

        approved = approve(
            intervention_id=intervention.id,
            body=InterventionAction(),
            session=session,
            current_user=user,
            x_tenant_key="ara-global",
            idempotency_key="approve-7-v1",
        )

        dispatch = session.exec(select(RevenueInterventionDispatch)).one()
        assert approved["status"] == "APPROVED"
        assert dispatch.intervention_id == intervention.id
