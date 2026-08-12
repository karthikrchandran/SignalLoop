from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from sqlmodel import Session, SQLModel, create_engine

from app.domain.audit.audit_events import AuditEvent
from app.domain.revenue_intelligence.dispatcher import (
    InterventionDeliveryResult,
    RevenueInterventionDispatcher,
)
from app.domain.revenue_intelligence.enforcement import (
    ConfiguredInterventionEnforcementGate,
)
from app.domain.revenue_intelligence.persistence import RevenueInterventionStore
from app.domain.revenue_intelligence.persistence_models import (
    RevenueInterventionDispatch,
    RevenueInterventionOutcome,
    RevenueInterventionRecord,
    RevenueInterventionTransition,
    RevenueSignalRecord,
)
from app.domain.sequences.suppression import EmailSuppression
from app.domain.tenants.models import Tenant
from app.domain_models import (
    ActionQueue,
    Contact,
    GlobalControlState,
    GovernancePolicy,
    PolicyStatus,
    PolicyType,
)


class CountingDelivery:
    def __init__(self) -> None:
        self.calls = 0

    async def deliver(self, *, envelope) -> InterventionDeliveryResult:
        self.calls += 1
        return InterventionDeliveryResult(
            provider="sendgrid",
            accepted=True,
            retryable=False,
            receipt={"message_id": envelope.idempotency_key},
        )


def _session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(
        engine,
        tables=[
            Tenant.__table__,
            Contact.__table__,
            EmailSuppression.__table__,
            GovernancePolicy.__table__,
            GlobalControlState.__table__,
            ActionQueue.__table__,
            RevenueSignalRecord.__table__,
            RevenueInterventionRecord.__table__,
            RevenueInterventionDispatch.__table__,
            RevenueInterventionTransition.__table__,
            RevenueInterventionOutcome.__table__,
            AuditEvent.__table__,
        ],
    )
    return Session(engine)


def _claimed_dispatch(
    session: Session, *, contact: Contact
) -> tuple[RevenueInterventionStore, Tenant, RevenueInterventionDispatch]:
    tenant = Tenant(key="ara-global", display_name="ARA Global")
    session.add(tenant)
    session.add(contact)
    session.commit()
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
        idempotency_key="signal-enforcement-v1",
    )
    intervention = store.propose_intervention(
        tenant_id=tenant.id,
        signal_id=signal.id,
        action="send_email",
        action_payload={
            "contact_id": str(contact.id),
            "to": contact.email,
            "subject": "Review account",
            "body_text": "Review account A.",
            "body_html": "<p>Review account A.</p>",
        },
        evidence_refs=["signal:opportunity-7"],
        idempotency_key="intervention-enforcement-v1",
    )
    store.approve_intervention(
        tenant_id=tenant.id,
        intervention_id=intervention.id,
        actor_id="operator-1",
        idempotency_key="approve-enforcement-v1",
    )
    return store, tenant, store.claim_due_dispatches(tenant_id=tenant.id)[0]


def test_dispatch_rechecks_revoked_consent_without_calling_provider() -> None:
    with _session() as session:
        contact = Contact(
            workspace_id="ws-ara",
            email="buyer@example.test",
            consent_email=True,
        )
        store, tenant, dispatch = _claimed_dispatch(session, contact=contact)
        contact.consent_email = False
        session.add(contact)
        session.commit()
        delivery = CountingDelivery()

        asyncio.run(
            RevenueInterventionDispatcher(
                delivery,
                enforcement_gate=ConfiguredInterventionEnforcementGate(
                    session=session,
                    workspace_id="ws-ara",
                ),
            ).dispatch(store, tenant_id=tenant.id, dispatch_id=dispatch.id, workspace_id="ws-ara")
        )

        session.refresh(dispatch)
        assert delivery.calls == 0
        assert dispatch.status == "SUPPRESSED"
        assert dispatch.last_error == "CONSENT_MISSING"


def test_dispatch_defers_quiet_hours_without_consuming_provider_attempt() -> None:
    with _session() as session:
        contact = Contact(
            workspace_id="ws-ara",
            email="buyer@example.test",
            consent_email=True,
            timezone="UTC",
        )
        store, tenant, dispatch = _claimed_dispatch(session, contact=contact)
        session.add(
            GovernancePolicy(
                workspace_id="ws-ara",
                scope="workspace",
                policy_type=PolicyType.quiet_hours,
                payload_json={"timezone": "UTC", "start": "21:00", "end": "08:00"},
                status=PolicyStatus.active,
            )
        )
        session.commit()
        delivery = CountingDelivery()
        gate = ConfiguredInterventionEnforcementGate(
            session=session,
            workspace_id="ws-ara",
            now=lambda: datetime(2026, 8, 11, 23, 0, tzinfo=UTC),
        )

        asyncio.run(
            RevenueInterventionDispatcher(delivery, enforcement_gate=gate).dispatch(
                store, tenant_id=tenant.id, dispatch_id=dispatch.id, workspace_id="ws-ara"
            )
        )

        session.refresh(dispatch)
        assert delivery.calls == 0
        assert dispatch.status == "RETRY_SCHEDULED"
        assert dispatch.attempt_count == 0
        assert dispatch.last_error == "QUIET_HOURS_BLOCK"
        assert dispatch.next_attempt_at is not None


def test_live_gate_blocks_suppressed_recipient() -> None:
    with _session() as session:
        contact = Contact(
            workspace_id="ws-ara",
            email="buyer@example.test",
            consent_email=True,
        )
        store, tenant, dispatch = _claimed_dispatch(session, contact=contact)
        session.add(
            EmailSuppression(
                workspace_id="ws-ara",
                email=contact.email,
                reason="unsubscribe",
            )
        )
        session.commit()
        delivery = CountingDelivery()

        asyncio.run(
            RevenueInterventionDispatcher(
                delivery,
                enforcement_gate=ConfiguredInterventionEnforcementGate(
                    session=session,
                    workspace_id="ws-ara",
                ),
            ).dispatch(store, tenant_id=tenant.id, dispatch_id=dispatch.id, workspace_id="ws-ara")
        )

        session.refresh(dispatch)
        assert delivery.calls == 0
        assert dispatch.status == "SUPPRESSED"
        assert dispatch.last_error == "EMAIL_SUPPRESSED"


def test_live_gate_defers_while_workspace_is_paused() -> None:
    with _session() as session:
        contact = Contact(
            workspace_id="ws-ara",
            email="buyer@example.test",
            consent_email=True,
        )
        store, tenant, dispatch = _claimed_dispatch(session, contact=contact)
        session.add(
            GlobalControlState(
                workspace_id="ws-ara",
                paused=True,
                paused_reason="incident",
            )
        )
        session.commit()
        delivery = CountingDelivery()

        asyncio.run(
            RevenueInterventionDispatcher(
                delivery,
                enforcement_gate=ConfiguredInterventionEnforcementGate(
                    session=session,
                    workspace_id="ws-ara",
                    now=lambda: datetime(2026, 8, 11, 15, 0, tzinfo=UTC),
                ),
            ).dispatch(store, tenant_id=tenant.id, dispatch_id=dispatch.id, workspace_id="ws-ara")
        )

        session.refresh(dispatch)
        assert delivery.calls == 0
        assert dispatch.status == "RETRY_SCHEDULED"
        assert dispatch.attempt_count == 0
        assert dispatch.last_error == "WORKSPACE_PAUSED"
