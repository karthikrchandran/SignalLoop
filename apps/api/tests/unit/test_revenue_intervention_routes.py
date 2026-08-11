from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi import HTTPException
from sqlmodel import Session, SQLModel, create_engine, select

from app.api.routes.revenue_interventions import (
    InterventionAction,
    InterventionOutcome,
    InterventionProposal,
    approve,
    cancel,
    list_dispatches,
    list_interventions,
    operational_health,
    outcome,
    propose_intervention,
    reject,
    retry_dispatch,
)
from app.domain.audit.audit_events import AuditEvent
from app.domain.revenue_intelligence.persistence import RevenueInterventionStore
from app.domain.revenue_intelligence.persistence_models import (
    RevenueInterventionDispatch,
    RevenueInterventionOutcome,
    RevenueInterventionRecord,
    RevenueInterventionTransition,
    RevenueSignalRecord,
)
from app.domain.tenants.models import (
    ProductCode,
    ProductInstallation,
    RoleBundle,
    SuiteMembership,
    SuiteProjectionOutbox,
    SuiteRoleAssignment,
    SupportAccessGrant,
    Tenant,
    TenantEntitlement,
    utc_now,
)
from app.domain_models import (
    NotificationProvider,
    ProviderCapability,
    ProviderCredential,
    WorkspaceProviderSelection,
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
            ProductInstallation.__table__,
            SuiteProjectionOutbox.__table__,
            ProviderCredential.__table__,
            WorkspaceProviderSelection.__table__,
            SuiteMembership.__table__,
            SuiteRoleAssignment.__table__,
            SupportAccessGrant.__table__,
            RevenueSignalRecord.__table__,
            RevenueInterventionRecord.__table__,
            RevenueInterventionDispatch.__table__,
            RevenueInterventionTransition.__table__,
            RevenueInterventionOutcome.__table__,
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


def test_revenue_intervention_routes_persist_reject_cancel_and_outcome() -> None:
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
            idempotency_key="signal-route-v1",
        )
        rejected_item = store.propose_intervention(
            tenant_id=tenant.id,
            signal_id=signal.id,
            action="send_email",
            evidence_refs=["signal:opportunity-7"],
            idempotency_key="route-reject-proposal-v1",
        )
        rejected = reject(
            intervention_id=rejected_item.id,
            body=InterventionAction(),
            session=session,
            current_user=user,
            x_tenant_key=tenant.key,
            idempotency_key="route-reject-v1",
        )
        assert rejected["status"] == "REJECTED"

        cancelled_item = store.propose_intervention(
            tenant_id=tenant.id,
            signal_id=signal.id,
            action="send_email",
            evidence_refs=["signal:opportunity-7"],
            idempotency_key="route-cancel-proposal-v1",
        )
        cancelled = cancel(
            intervention_id=cancelled_item.id,
            body=InterventionAction(),
            session=session,
            current_user=user,
            x_tenant_key=tenant.key,
            idempotency_key="route-cancel-v1",
        )
        assert cancelled["status"] == "CANCELLED"

        completed_item = store.propose_intervention(
            tenant_id=tenant.id,
            signal_id=signal.id,
            action="send_email",
            evidence_refs=["signal:opportunity-7"],
            idempotency_key="route-outcome-proposal-v1",
        )
        store.approve_intervention(
            tenant_id=tenant.id,
            intervention_id=completed_item.id,
            actor_id=str(user.id),
            idempotency_key="route-outcome-approve-v1",
        )
        dispatch = store.claim_due_dispatches(tenant_id=tenant.id)[0]
        store.record_dispatch_success(
            tenant_id=tenant.id,
            dispatch_id=dispatch.id,
            provider="sendgrid",
            receipt={"message_id": "sg-route-1"},
        )
        recorded = outcome(
            intervention_id=completed_item.id,
            body=InterventionOutcome(status="QUALIFIED", evidence_refs=["reply:sg-route-1"]),
            session=session,
            current_user=user,
            x_tenant_key=tenant.key,
            idempotency_key="route-outcome-v1",
        )
        assert recorded["status"] == "QUALIFIED"
        assert recorded["intervention_id"] == str(completed_item.id)


def test_intervention_action_rejects_caller_supplied_actor_impersonation() -> None:
    with _session() as session:
        user, tenant = _user_and_tenant(session)
        store = RevenueInterventionStore(session)
        signal = store.record_signal(
            tenant_id=tenant.id,
            signal_type="stalled_opportunity",
            subject_ref="opportunity-8",
            confidence=0.9,
            evidence_refs=["signal:opportunity-8"],
            evidence_hash="sha256:signal-8",
            source="local-revenueos",
            consent_verified=True,
            policy_allowed=True,
            idempotency_key="signal-actor-v1",
        )
        intervention = store.propose_intervention(
            tenant_id=tenant.id,
            signal_id=signal.id,
            action="send_email",
            evidence_refs=["signal:opportunity-8"],
            idempotency_key="intervention-actor-v1",
        )

        with pytest.raises(HTTPException, match="actor must match"):
            approve(
                intervention_id=intervention.id,
                body=InterventionAction(actor="different-user"),
                session=session,
                current_user=user,
                x_tenant_key=tenant.key,
                idempotency_key="approve-actor-v1",
            )


def test_revenue_operations_routes_list_and_retry_dead_letters() -> None:
    with _session() as session:
        user, tenant = _user_and_tenant(session)
        store = RevenueInterventionStore(session)
        signal = store.record_signal(
            tenant_id=tenant.id,
            signal_type="stalled_opportunity",
            subject_ref="opportunity-9",
            confidence=0.9,
            evidence_refs=["signal:opportunity-9"],
            evidence_hash="sha256:signal-9",
            source="local-revenueos",
            consent_verified=True,
            policy_allowed=True,
            idempotency_key="signal-operations-v1",
        )
        intervention = store.propose_intervention(
            tenant_id=tenant.id,
            signal_id=signal.id,
            action="send_email",
            evidence_refs=["signal:opportunity-9"],
            idempotency_key="intervention-operations-v1",
        )
        store.approve_intervention(
            tenant_id=tenant.id,
            intervention_id=intervention.id,
            actor_id=str(user.id),
            idempotency_key="approve-operations-v1",
        )
        dispatch = store.claim_due_dispatches(tenant_id=tenant.id)[0]
        store.record_dispatch_failure(
            tenant_id=tenant.id,
            dispatch_id=dispatch.id,
            provider="sendgrid",
            reason="HTTP_422",
            retryable=False,
        )

        listed = list_dispatches(
            session=session,
            current_user=user,
            x_tenant_key=tenant.key,
            dispatch_status="DEAD_LETTER",
        )
        retried = retry_dispatch(
            dispatch_id=dispatch.id,
            body=InterventionAction(),
            session=session,
            current_user=user,
            x_tenant_key=tenant.key,
            idempotency_key="retry-operations-v1",
        )

        assert listed["counts"]["DEAD_LETTER"] == 1
        assert listed["data"][0]["last_error"] == "HTTP_422"
        assert retried["status"] == "PENDING"


def test_operational_health_reports_projection_provider_and_dispatch_state() -> None:
    with _session() as session:
        user, tenant = _user_and_tenant(session)
        installation = ProductInstallation(
            tenant_id=tenant.id,
            product_code=ProductCode.SIGNAL_LOOP,
            local_identifier="ws-ara",
            projection_endpoint="https://signalloop.example.test/projections",
            workload_key_id="key-1",
            workload_key_status="ACTIVE",
        )
        session.add(installation)
        session.flush()
        session.add(
            SuiteProjectionOutbox(
                tenant_id=tenant.id,
                installation_id=installation.id,
                projection_kind="tenant_settings",
                projection_version=1,
                payload={"tenant_key": tenant.key},
                payload_digest="a" * 64,
                status="DEAD_LETTER",
                dead_letter_reason="HTTP_422",
                last_error="HTTP_422",
            )
        )
        session.add(
            WorkspaceProviderSelection(
                workspace_id="ws-ara",
                capability=ProviderCapability.email,
                provider=NotificationProvider.sendgrid,
                is_active=True,
            )
        )
        session.add(
            ProviderCredential(
                workspace_id="ws-ara",
                provider=NotificationProvider.sendgrid,
                channel="email",
                encrypted_api_key="encrypted-test-key",
                is_active=True,
            )
        )
        session.commit()

        health = operational_health(
            session=session,
            current_user=user,
            x_tenant_key=tenant.key,
        )

        assert health["tenant_key"] == tenant.key
        assert health["projections"]["counts"]["DEAD_LETTER"] == 1
        assert health["projections"]["unacknowledged_count"] == 1
        assert health["provider"]["email"]["provider"] == "sendgrid"
        assert health["provider"]["email"]["credential_configured"] is True
        assert health["installations"][0]["projection_ready"] is True


def test_operational_health_accepts_live_tenant_scoped_support_grant() -> None:
    with _session() as session:
        operator = User(email="support@example.com", hashed_password="not-used")
        tenant = Tenant(key="supported-tenant", display_name="Supported Tenant")
        session.add(operator)
        session.add(tenant)
        session.flush()
        session.add(
            TenantEntitlement(
                tenant_id=tenant.id,
                product_code=ProductCode.REVENUE_OS,
            )
        )
        grant = SupportAccessGrant(
            tenant_id=tenant.id,
            operator_user_id=operator.id,
            capabilities=["revenueos.admin.manage"],
            reason="Investigate dispatch backlog",
            ticket_reference="SUP-42",
            approved_by=operator.id,
            expires_at=utc_now() + timedelta(hours=1),
        )
        session.add(grant)
        session.commit()

        health = operational_health(
            session=session,
            current_user=operator,
            x_tenant_key=tenant.key,
            x_support_grant_id=str(grant.id),
        )

        assert health["tenant_key"] == tenant.key
        event = session.exec(
            select(AuditEvent).where(AuditEvent.event_name == "support.grant.used")
        ).one()
        assert event.resource_id == str(grant.id)


def test_operational_health_denies_cross_tenant_support_grant_and_audits() -> None:
    with _session() as session:
        operator = User(email="support-denied@example.com", hashed_password="not-used")
        requested_tenant = Tenant(key="requested-tenant", display_name="Requested Tenant")
        granted_tenant = Tenant(key="granted-tenant", display_name="Granted Tenant")
        session.add(operator)
        session.add(requested_tenant)
        session.add(granted_tenant)
        session.flush()
        session.add(
            TenantEntitlement(
                tenant_id=requested_tenant.id,
                product_code=ProductCode.REVENUE_OS,
            )
        )
        grant = SupportAccessGrant(
            tenant_id=granted_tenant.id,
            operator_user_id=operator.id,
            capabilities=["revenueos.admin.manage"],
            reason="Investigate dispatch backlog",
            approved_by=operator.id,
            expires_at=utc_now() + timedelta(hours=1),
        )
        session.add(grant)
        session.commit()

        with pytest.raises(HTTPException) as exc_info:
            operational_health(
                session=session,
                current_user=operator,
                x_tenant_key=requested_tenant.key,
                x_support_grant_id=str(grant.id),
            )

        assert exc_info.value.status_code == 404
        event = session.exec(
            select(AuditEvent).where(AuditEvent.event_name == "support.grant.denied")
        ).one()
        assert event.payload["denial_reason"] == "SUPPORT_GRANT_TENANT_MISMATCH"
