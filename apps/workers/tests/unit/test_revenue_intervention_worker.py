from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from app.domain.audit.audit_events import AuditEvent
from app.domain.revenue_intelligence.dispatcher import InterventionDeliveryResult
from app.domain.revenue_intelligence.persistence import (
    RevenueInterventionConflict,
    RevenueInterventionStore,
)
from app.domain.revenue_intelligence.persistence_models import (
    RevenueInterventionDispatch,
    RevenueInterventionOutcome,
    RevenueInterventionRecord,
    RevenueInterventionTransition,
    RevenueSignalRecord,
)
from app.domain.sequences.suppression import EmailSuppression
from app.domain.tenants.models import (
    ProductCode,
    ProductInstallation,
    Tenant,
    TenantOperationalControl,
    utc_now,
)
from app.domain_models import ActionQueue, Contact, GlobalControlState, GovernancePolicy
from worker_app import revenue_intervention_worker
from worker_app.revenue_intervention_worker import process_claimed_revenue_interventions


class AcceptingDelivery:
    def __init__(self) -> None:
        self.calls = 0
        self.envelopes = []

    async def deliver(self, *, envelope) -> InterventionDeliveryResult:
        self.calls += 1
        self.envelopes.append(envelope)
        return InterventionDeliveryResult(
            provider="email",
            accepted=True,
            retryable=False,
            receipt={"status_code": 202, "message_id": envelope.idempotency_key},
        )


class LostResponseDelivery:
    """Provider accepted the command but the worker dies before a receipt arrives."""

    def __init__(self) -> None:
        self.calls = 0

    async def deliver(self, *, envelope) -> InterventionDeliveryResult:
        del envelope
        self.calls += 1
        raise KeyboardInterrupt("worker terminated after provider acceptance")


class TimedOutDelivery:
    def __init__(self) -> None:
        self.calls = 0

    async def deliver(self, *, envelope) -> InterventionDeliveryResult:
        del envelope
        self.calls += 1
        raise TimeoutError("response lost after provider acceptance")


def _session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(
        engine,
        tables=[
            Tenant.__table__,
            ProductInstallation.__table__,
            TenantOperationalControl.__table__,
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


def _approved_dispatch(
    session: Session,
    *,
    tenant_key: str = "ara-global",
    workspace_id: str = "ws-ara",
) -> tuple[Tenant, RevenueInterventionDispatch]:
    tenant = Tenant(key=tenant_key, display_name="ARA Global")
    session.add(tenant)
    session.flush()
    session.add(
        ProductInstallation(
            tenant_id=tenant.id,
            product_code=ProductCode.SIGNAL_LOOP,
            local_identifier=workspace_id,
        )
    )
    contact = Contact(
        workspace_id=workspace_id,
        email="owner@example.test",
        consent_email=True,
    )
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
        idempotency_key="signal-7-v1",
    )
    intervention = store.propose_intervention(
        tenant_id=tenant.id,
        signal_id=signal.id,
        action="send_email",
        action_payload={
            "contact_id": str(contact.id),
            "to": "owner@example.test",
            "subject": "Review account",
            "body_text": "Review account A.",
            "body_html": "<p>Review account A.</p>",
        },
        evidence_refs=["signal:opportunity-7"],
        idempotency_key="intervention-7-v1",
    )
    store.approve_intervention(
        tenant_id=tenant.id,
        intervention_id=intervention.id,
        actor_id="operator-1",
    )
    dispatch = session.exec(
        select(RevenueInterventionDispatch).where(
            RevenueInterventionDispatch.intervention_id == intervention.id
        )
    ).one()
    return tenant, dispatch


def test_worker_dispatches_due_revenue_intervention() -> None:
    with _session() as session:
        _tenant, dispatch = _approved_dispatch(session)
        deliveries: list[tuple[str, AcceptingDelivery]] = []

        def delivery_factory(_session: Session, workspace_id: str) -> AcceptingDelivery:
            delivery = AcceptingDelivery()
            deliveries.append((workspace_id, delivery))
            return delivery

        processed = asyncio.run(
            process_claimed_revenue_interventions(
                session,
                delivery_factory=delivery_factory,
            )
        )

        session.refresh(dispatch)
        assert processed == 1
        assert dispatch.status == "ACKNOWLEDGED"
        assert deliveries[0][0] == "ws-ara"
        assert deliveries[0][1].calls == 1
        envelope = deliveries[0][1].envelopes[0]
        assert envelope.workspace_id == "ws-ara"
        assert envelope.destination_ref == "owner@example.test"
        assert envelope.idempotency_key == str(dispatch.id)
        assert dispatch.attempt_envelope is not None


def test_worker_does_not_claim_a_tenant_product_paused_by_an_operator() -> None:
    with _session() as session:
        tenant, dispatch = _approved_dispatch(session)
        session.add(
            TenantOperationalControl(
                tenant_id=tenant.id,
                product_code=ProductCode.REVENUE_OS,
                paused=True,
                paused_reason="provider incident INC-42",
            )
        )
        session.commit()
        delivery = AcceptingDelivery()

        processed = asyncio.run(
            process_claimed_revenue_interventions(
                session,
                delivery_factory=lambda _session, _workspace_id: delivery,
            )
        )

        session.refresh(dispatch)
        assert processed == 0
        assert delivery.calls == 0
        assert dispatch.status == "PENDING"


def test_worker_honors_the_signal_loop_switch_for_revenueos_delivery() -> None:
    with _session() as session:
        tenant, dispatch = _approved_dispatch(session)
        session.add(
            TenantOperationalControl(
                tenant_id=tenant.id,
                product_code=ProductCode.SIGNAL_LOOP,
                paused=True,
                paused_reason="SignalLoop provider maintenance",
            )
        )
        session.commit()
        delivery = AcceptingDelivery()

        processed = asyncio.run(
            process_claimed_revenue_interventions(
                session,
                delivery_factory=lambda _session, _workspace_id: delivery,
            )
        )

        session.refresh(dispatch)
        assert processed == 0
        assert delivery.calls == 0
        assert dispatch.status == "PENDING"


def test_pause_between_tenant_enumeration_and_claim_prevents_provider_delivery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with _session() as session:
        tenant, dispatch = _approved_dispatch(session)
        original_claim = RevenueInterventionStore.claim_due_dispatches

        def pause_then_claim(
            store: RevenueInterventionStore, *, tenant_id, **kwargs
        ) -> list[RevenueInterventionDispatch]:
            session.add(
                TenantOperationalControl(
                    tenant_id=tenant_id,
                    product_code=ProductCode.REVENUE_OS,
                    paused=True,
                    paused_reason="incident race guard",
                )
            )
            session.commit()
            return original_claim(store, tenant_id=tenant_id, **kwargs)

        monkeypatch.setattr(
            revenue_intervention_worker.RevenueInterventionStore,
            "claim_due_dispatches",
            pause_then_claim,
        )
        delivery = AcceptingDelivery()

        processed = asyncio.run(
            process_claimed_revenue_interventions(
                session,
                delivery_factory=lambda _session, _workspace_id: delivery,
            )
        )

        session.refresh(dispatch)
        assert processed == 0
        assert delivery.calls == 0
        assert dispatch.status == "PENDING"


def test_resume_after_paused_claim_attempt_preserves_pending_dispatch() -> None:
    with _session() as session:
        tenant, dispatch = _approved_dispatch(session)
        control = TenantOperationalControl(
            tenant_id=tenant.id,
            product_code=ProductCode.REVENUE_OS,
            paused=True,
            paused_reason="incident recovery",
        )
        session.add(control)
        session.commit()

        assert asyncio.run(process_claimed_revenue_interventions(session)) == 0
        session.refresh(dispatch)
        assert dispatch.status == "PENDING"

        control.paused = False
        control.paused_reason = None
        session.add(control)
        session.commit()
        delivery = AcceptingDelivery()

        processed = asyncio.run(
            process_claimed_revenue_interventions(
                session,
                delivery_factory=lambda _session, _workspace_id: delivery,
            )
        )

        session.refresh(dispatch)
        assert processed == 1
        assert delivery.calls == 1
        assert dispatch.status == "ACKNOWLEDGED"


def test_tenant_pause_does_not_halt_another_tenants_dispatch() -> None:
    with _session() as session:
        tenant_a, dispatch_a = _approved_dispatch(session)
        _tenant_b, dispatch_b = _approved_dispatch(
            session,
            tenant_key="tenant-b",
            workspace_id="ws-tenant-b",
        )
        session.add(
            TenantOperationalControl(
                tenant_id=tenant_a.id,
                product_code=ProductCode.REVENUE_OS,
                paused=True,
                paused_reason="tenant A incident",
            )
        )
        session.commit()
        delivery = AcceptingDelivery()

        processed = asyncio.run(
            process_claimed_revenue_interventions(
                session,
                delivery_factory=lambda _session, _workspace_id: delivery,
            )
        )

        session.refresh(dispatch_a)
        session.refresh(dispatch_b)
        assert processed == 1
        assert delivery.calls == 1
        assert dispatch_a.status == "PENDING"
        assert dispatch_b.status == "ACKNOWLEDGED"


def test_worker_recovers_expired_revenue_dispatch_lease() -> None:
    with _session() as session:
        tenant, dispatch = _approved_dispatch(session)
        store = RevenueInterventionStore(session)
        claimed = store.claim_due_dispatches(tenant_id=tenant.id)[0]
        claimed.lease_expires_at = utc_now() - timedelta(seconds=1)
        session.add(claimed)
        session.commit()

        processed = asyncio.run(
            process_claimed_revenue_interventions(
                session,
                delivery_factory=lambda _session, _workspace_id: AcceptingDelivery(),
            )
        )

        session.refresh(dispatch)
        assert processed == 1
        assert dispatch.status == "ACKNOWLEDGED"


def test_lost_provider_response_is_held_for_reconciliation_not_redispatched() -> None:
    with _session() as session:
        tenant, dispatch = _approved_dispatch(session)
        lost = LostResponseDelivery()

        with pytest.raises(KeyboardInterrupt, match="provider acceptance"):
            asyncio.run(
                process_claimed_revenue_interventions(
                    session,
                    delivery_factory=lambda _session, _workspace_id: lost,
                )
            )

        session.refresh(dispatch)
        assert lost.calls == 1
        assert dispatch.status == "IN_FLIGHT"
        assert dispatch.attempt_envelope is not None
        dispatch.lease_expires_at = utc_now() - timedelta(seconds=1)
        session.add(dispatch)
        session.commit()

        processed = asyncio.run(
            process_claimed_revenue_interventions(
                session,
                delivery_factory=lambda _session, _workspace_id: AcceptingDelivery(),
            )
        )

        session.refresh(dispatch)
        assert processed == 0
        assert dispatch.status == "UNKNOWN_PROVIDER_OUTCOME"
        assert lost.calls == 1


def test_provider_timeout_after_invocation_is_not_automatically_redispatched() -> None:
    with _session() as session:
        _tenant, dispatch = _approved_dispatch(session)
        timed_out = TimedOutDelivery()
        processed = asyncio.run(
            process_claimed_revenue_interventions(
                session,
                delivery_factory=lambda _session, _workspace_id: timed_out,
            )
        )
        session.refresh(dispatch)
        assert processed == 1
        assert timed_out.calls == 1
        assert dispatch.status == "UNKNOWN_PROVIDER_OUTCOME"

        processed = asyncio.run(
            process_claimed_revenue_interventions(
                session,
                delivery_factory=lambda _session, _workspace_id: AcceptingDelivery(),
            )
        )
        assert processed == 0
        assert timed_out.calls == 1
        assert dispatch.status == "UNKNOWN_PROVIDER_OUTCOME"


def test_attempt_envelope_tampering_is_rejected_before_provider_execution() -> None:
    with _session() as session:
        tenant, dispatch = _approved_dispatch(session)
        store = RevenueInterventionStore(session)
        store.claim_due_dispatches(tenant_id=tenant.id)
        original = store.prepare_dispatch_attempt(
            tenant_id=tenant.id, dispatch_id=dispatch.id, workspace_id="ws-ara"
        )
        assert original["destination_ref"] == "owner@example.test"
        assert dispatch.attempt_envelope is not None
        tampered = dict(dispatch.attempt_envelope)
        tampered["destination_ref"] = "attacker@example.test"
        dispatch.attempt_envelope = tampered
        dispatch.attempt_envelope_digest = hashlib.sha256(
            json.dumps(tampered, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        session.add(dispatch)
        session.commit()

        with pytest.raises(RevenueInterventionConflict, match="immutable"):
            store.prepare_dispatch_attempt(
                tenant_id=tenant.id, dispatch_id=dispatch.id, workspace_id="ws-ara"
            )


def test_unknown_provider_outcome_requires_authorized_operator_and_evidence() -> None:
    with _session() as session:
        tenant, dispatch = _approved_dispatch(session)
        store = RevenueInterventionStore(session)
        store.claim_due_dispatches(tenant_id=tenant.id)
        store.prepare_dispatch_attempt(
            tenant_id=tenant.id, dispatch_id=dispatch.id, workspace_id="ws-ara"
        )
        dispatch.lease_expires_at = utc_now() - timedelta(seconds=1)
        session.add(dispatch)
        session.commit()
        store.recover_expired_dispatch_leases()

        with pytest.raises(PermissionError, match="capability"):
            store.reconcile_unknown_provider_outcome(
                tenant_id=tenant.id,
                dispatch_id=dispatch.id,
                actor_id=uuid4(),
                provider="email",
                receipt={"provider_receipt_id": "provider-1"},
                provider_accepted=True,
                operator_capabilities=frozenset(),
            )
        with pytest.raises(ValueError, match="receipt"):
            store.reconcile_unknown_provider_outcome(
                tenant_id=tenant.id,
                dispatch_id=dispatch.id,
                actor_id=uuid4(),
                provider="email",
                receipt=None,
                provider_accepted=False,
                operator_capabilities=frozenset({"revenueos.admin.manage"}),
            )
        reconciled = store.reconcile_unknown_provider_outcome(
            tenant_id=tenant.id,
            dispatch_id=dispatch.id,
            actor_id=uuid4(),
            provider="email",
            receipt={"provider_receipt_id": "provider-1", "status_code": 202},
            provider_accepted=True,
            operator_capabilities=frozenset({"revenueos.admin.manage"}),
        )
        assert reconciled.status == "ACKNOWLEDGED"
