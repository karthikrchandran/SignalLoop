from __future__ import annotations

import asyncio

from sqlmodel import Session, SQLModel, create_engine

from app.domain.audit.audit_events import AuditEvent
from app.domain.revenue_intelligence.dispatcher import (
    InterventionDeliveryResult,
    RevenueInterventionDispatcher,
)
from app.domain.revenue_intelligence.persistence import RevenueInterventionStore
from app.domain.revenue_intelligence.persistence_models import (
    RevenueInterventionDispatch,
    RevenueInterventionOutcome,
    RevenueInterventionRecord,
    RevenueInterventionTransition,
    RevenueSignalRecord,
)
from app.domain.tenants.models import Tenant


class AcceptingDelivery:
    async def deliver(
        self, *, action: str, payload: dict[str, object], idempotency_key: str
    ) -> InterventionDeliveryResult:
        assert action == "send_email"
        assert payload["to"] == "owner@example.test"
        assert idempotency_key
        return InterventionDeliveryResult(
            provider="sendgrid",
            accepted=True,
            retryable=False,
            receipt={"message_id": "sg-123", "status_code": 202},
        )


def test_dispatcher_executes_approved_intervention_with_explicit_payload() -> None:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(
        engine,
        tables=[
            Tenant.__table__,
            RevenueSignalRecord.__table__,
            RevenueInterventionRecord.__table__,
            RevenueInterventionDispatch.__table__,
            RevenueInterventionTransition.__table__,
            RevenueInterventionOutcome.__table__,
            AuditEvent.__table__,
        ],
    )
    with Session(engine) as session:
        tenant = Tenant(key="ara-global", display_name="ARA Global")
        session.add(tenant)
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
            idempotency_key="signal-7-v1",
        )
        intervention = store.propose_intervention(
            tenant_id=tenant.id,
            signal_id=signal.id,
            action="send_email",
            action_payload={
                "to": "owner@example.test",
                "subject": "Opportunity needs review",
                "body_text": "Please review opportunity-7.",
                "body_html": "<p>Please review opportunity-7.</p>",
            },
            evidence_refs=["signal:opportunity-7"],
            idempotency_key="intervention-7-v1",
        )
        store.approve_intervention(
            tenant_id=tenant.id,
            intervention_id=intervention.id,
            actor_id="operator-1",
        )
        dispatch = store.claim_due_dispatches(tenant_id=tenant.id)[0]

        asyncio.run(
            RevenueInterventionDispatcher(AcceptingDelivery()).dispatch(
                store,
                tenant_id=tenant.id,
                dispatch_id=dispatch.id,
            )
        )

        session.refresh(dispatch)
        assert dispatch.status == "ACKNOWLEDGED"
        assert dispatch.provider_receipt == {"message_id": "sg-123", "status_code": 202}
