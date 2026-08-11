from __future__ import annotations

from datetime import timedelta

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from app.domain.audit.audit_events import AuditEvent
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
from app.domain.tenants.models import Tenant, utc_now


def _session() -> Session:
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
    return Session(engine)


def _signal(store: RevenueInterventionStore, tenant_id) -> RevenueSignalRecord:  # noqa: ANN001
    return store.record_signal(
        tenant_id=tenant_id,
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


def test_store_persists_idempotent_policy_gated_intervention() -> None:
    with _session() as session:
        tenant = Tenant(key="ara-global", display_name="ARA Global")
        session.add(tenant)
        session.commit()
        store = RevenueInterventionStore(session)
        signal = _signal(store, tenant.id)

        first = store.propose_intervention(
            tenant_id=tenant.id,
            signal_id=signal.id,
            action="notify_account_owner",
            evidence_refs=["signal:opportunity-7"],
            idempotency_key="intervention-7-v1",
        )
        second = store.propose_intervention(
            tenant_id=tenant.id,
            signal_id=signal.id,
            action="notify_account_owner",
            evidence_refs=["signal:opportunity-7"],
            idempotency_key="intervention-7-v1",
        )

        assert first.id == second.id
        assert first.status == "PROPOSED"
        audit_names = [event.event_name for event in session.exec(select(AuditEvent)).all()]
        assert "revenueos.intervention.proposed" in audit_names
        with pytest.raises(RevenueInterventionConflict):
            store.propose_intervention(
                tenant_id=tenant.id,
                signal_id=signal.id,
                action="send_email",
                evidence_refs=["signal:opportunity-7"],
                idempotency_key="intervention-7-v1",
            )


def test_store_persists_policy_denial_and_recovers_expired_dispatch_lease() -> None:
    with _session() as session:
        tenant = Tenant(key="ara-global", display_name="ARA Global")
        session.add(tenant)
        session.commit()
        store = RevenueInterventionStore(session)
        denied_signal = store.record_signal(
            tenant_id=tenant.id,
            signal_type="do_not_contact",
            subject_ref="contact-9",
            confidence=1.0,
            evidence_refs=["consent:revoked"],
            evidence_hash="sha256:revoked",
            source="local-revenueos",
            consent_verified=False,
            policy_allowed=False,
            idempotency_key="signal-9-v1",
        )
        denied = store.propose_intervention(
            tenant_id=tenant.id,
            signal_id=denied_signal.id,
            action="send_email",
            evidence_refs=["consent:revoked"],
            idempotency_key="intervention-9-v1",
        )
        assert denied.status == "DENIED"
        assert denied.denial_reason == "CONSENT_NOT_VERIFIED"
        assert session.exec(
            select(AuditEvent).where(AuditEvent.event_name == "revenueos.intervention.denied")
        ).one()

        approved_signal = _signal(store, tenant.id)
        intervention = store.propose_intervention(
            tenant_id=tenant.id,
            signal_id=approved_signal.id,
            action="notify_account_owner",
            evidence_refs=["signal:opportunity-7"],
            idempotency_key="intervention-8-v1",
        )
        store.approve_intervention(
            tenant_id=tenant.id,
            intervention_id=intervention.id,
            actor_id="operator-1",
        )
        dispatch = store.claim_due_dispatches(tenant_id=tenant.id)[0]
        dispatch.lease_expires_at = utc_now() - timedelta(seconds=1)
        session.add(dispatch)
        session.commit()

        assert store.recover_expired_dispatch_leases() == 1
        session.refresh(dispatch)
        assert dispatch.status == "PENDING"


def test_store_settles_dispatch_with_retry_and_dead_letter_state() -> None:
    with _session() as session:
        tenant = Tenant(key="ara-global", display_name="ARA Global")
        session.add(tenant)
        session.commit()
        store = RevenueInterventionStore(session)
        signal = _signal(store, tenant.id)
        intervention = store.propose_intervention(
            tenant_id=tenant.id,
            signal_id=signal.id,
            action="send_email",
            evidence_refs=["signal:opportunity-7"],
            idempotency_key="intervention-10-v1",
        )
        store.approve_intervention(
            tenant_id=tenant.id,
            intervention_id=intervention.id,
            actor_id="operator-1",
        )
        dispatch = store.claim_due_dispatches(tenant_id=tenant.id)[0]

        retried = store.record_dispatch_failure(
            tenant_id=tenant.id,
            dispatch_id=dispatch.id,
            provider="sendgrid",
            reason="HTTP_503",
            retryable=True,
        )
        assert retried.status == "RETRY_SCHEDULED"
        assert retried.attempt_count == 1
        assert retried.next_attempt_at is not None

        retried.next_attempt_at = utc_now() - timedelta(seconds=1)
        session.add(retried)
        session.commit()
        claimed = store.claim_due_dispatches(tenant_id=tenant.id)[0]
        dead_lettered = store.record_dispatch_failure(
            tenant_id=tenant.id,
            dispatch_id=claimed.id,
            provider="sendgrid",
            reason="HTTP_422",
            retryable=False,
        )
        assert dead_lettered.status == "DEAD_LETTER"
        assert dead_lettered.dead_letter_reason == "HTTP_422"

        intervention2 = store.propose_intervention(
            tenant_id=tenant.id,
            signal_id=signal.id,
            action="send_email",
            evidence_refs=["signal:opportunity-7"],
            idempotency_key="intervention-11-v1",
        )
        store.approve_intervention(
            tenant_id=tenant.id,
            intervention_id=intervention2.id,
            actor_id="operator-1",
        )
        accepted = store.claim_due_dispatches(tenant_id=tenant.id)[0]
        acknowledged = store.record_dispatch_success(
            tenant_id=tenant.id,
            dispatch_id=accepted.id,
            provider="sendgrid",
            receipt={"message_id": "sg-123", "status_code": 202},
        )
        session.refresh(intervention2)
        assert acknowledged.status == "ACKNOWLEDGED"
        assert intervention2.status == "DISPATCHED"


def test_store_rejects_and_cancels_interventions_idempotently() -> None:
    with _session() as session:
        tenant = Tenant(key="ara-global", display_name="ARA Global")
        session.add(tenant)
        session.commit()
        store = RevenueInterventionStore(session)
        signal = _signal(store, tenant.id)
        rejected = store.propose_intervention(
            tenant_id=tenant.id,
            signal_id=signal.id,
            action="send_email",
            evidence_refs=["signal:opportunity-7"],
            idempotency_key="intervention-reject-v1",
        )

        first = store.reject_intervention(
            tenant_id=tenant.id,
            intervention_id=rejected.id,
            actor_id="operator-1",
            idempotency_key="reject-v1",
        )
        second = store.reject_intervention(
            tenant_id=tenant.id,
            intervention_id=rejected.id,
            actor_id="operator-1",
            idempotency_key="reject-v1",
        )

        assert first.status == second.status == "REJECTED"
        assert len(session.exec(select(RevenueInterventionTransition)).all()) == 1

        cancellable = store.propose_intervention(
            tenant_id=tenant.id,
            signal_id=signal.id,
            action="send_email",
            evidence_refs=["signal:opportunity-7"],
            idempotency_key="intervention-cancel-v1",
        )
        store.approve_intervention(
            tenant_id=tenant.id,
            intervention_id=cancellable.id,
            actor_id="operator-1",
            idempotency_key="approve-cancel-v1",
        )
        cancelled = store.cancel_intervention(
            tenant_id=tenant.id,
            intervention_id=cancellable.id,
            actor_id="operator-1",
            idempotency_key="cancel-v1",
        )
        dispatch = session.exec(
            select(RevenueInterventionDispatch).where(
                RevenueInterventionDispatch.intervention_id == cancellable.id
            )
        ).one()
        assert cancelled.status == "CANCELLED"
        assert dispatch.status == "CANCELLED"

        with pytest.raises(RevenueInterventionConflict):
            store.reject_intervention(
                tenant_id=tenant.id,
                intervention_id=cancellable.id,
                actor_id="operator-1",
                idempotency_key="cancel-v1",
            )


def test_store_records_tenant_scoped_idempotent_outcome_with_evidence() -> None:
    with _session() as session:
        tenant = Tenant(key="ara-global", display_name="ARA Global")
        session.add(tenant)
        session.commit()
        store = RevenueInterventionStore(session)
        signal = _signal(store, tenant.id)
        intervention = store.propose_intervention(
            tenant_id=tenant.id,
            signal_id=signal.id,
            action="send_email",
            evidence_refs=["signal:opportunity-7"],
            idempotency_key="intervention-outcome-v1",
        )
        store.approve_intervention(
            tenant_id=tenant.id,
            intervention_id=intervention.id,
            actor_id="operator-1",
            idempotency_key="approve-outcome-v1",
        )
        dispatch = store.claim_due_dispatches(tenant_id=tenant.id)[0]
        store.record_dispatch_success(
            tenant_id=tenant.id,
            dispatch_id=dispatch.id,
            provider="sendgrid",
            receipt={"message_id": "sg-123"},
        )

        first = store.record_outcome(
            tenant_id=tenant.id,
            intervention_id=intervention.id,
            status="QUALIFIED",
            evidence_refs=["reply:sg-123"],
            actor_id="operator-1",
            idempotency_key="outcome-v1",
        )
        second = store.record_outcome(
            tenant_id=tenant.id,
            intervention_id=intervention.id,
            status="QUALIFIED",
            evidence_refs=["reply:sg-123"],
            actor_id="operator-1",
            idempotency_key="outcome-v1",
        )

        assert first.id == second.id
        assert session.exec(select(RevenueInterventionOutcome)).one().status == "QUALIFIED"
        assert session.exec(
            select(AuditEvent).where(AuditEvent.event_name == "revenueos.intervention.outcome_recorded")
        ).one()


def test_approval_replay_does_not_duplicate_dispatch_and_leased_dispatch_cannot_cancel() -> None:
    with _session() as session:
        tenant = Tenant(key="ara-global", display_name="ARA Global")
        session.add(tenant)
        session.commit()
        store = RevenueInterventionStore(session)
        signal = _signal(store, tenant.id)
        intervention = store.propose_intervention(
            tenant_id=tenant.id,
            signal_id=signal.id,
            action="send_email",
            evidence_refs=["signal:opportunity-7"],
            idempotency_key="intervention-approval-replay-v1",
        )

        first = store.approve_intervention(
            tenant_id=tenant.id,
            intervention_id=intervention.id,
            actor_id="operator-1",
            idempotency_key="approve-replay-v1",
        )
        second = store.approve_intervention(
            tenant_id=tenant.id,
            intervention_id=intervention.id,
            actor_id="operator-1",
            idempotency_key="approve-replay-v1",
        )

        assert first.id == second.id
        assert len(session.exec(select(RevenueInterventionDispatch)).all()) == 1
        store.claim_due_dispatches(tenant_id=tenant.id)
        with pytest.raises(ValueError, match="dispatch in IN_FLIGHT state"):
            store.cancel_intervention(
                tenant_id=tenant.id,
                intervention_id=intervention.id,
                actor_id="operator-1",
                idempotency_key="cancel-after-lease-v1",
            )


def test_dead_letter_retry_is_operator_attributed_and_idempotent() -> None:
    with _session() as session:
        tenant = Tenant(key="ara-global", display_name="ARA Global")
        session.add(tenant)
        session.commit()
        store = RevenueInterventionStore(session)
        signal = _signal(store, tenant.id)
        intervention = store.propose_intervention(
            tenant_id=tenant.id,
            signal_id=signal.id,
            action="send_email",
            evidence_refs=["signal:opportunity-7"],
            idempotency_key="intervention-dead-letter-v1",
        )
        store.approve_intervention(
            tenant_id=tenant.id,
            intervention_id=intervention.id,
            actor_id="operator-1",
            idempotency_key="approve-dead-letter-v1",
        )
        dispatch = store.claim_due_dispatches(tenant_id=tenant.id)[0]
        store.record_dispatch_failure(
            tenant_id=tenant.id,
            dispatch_id=dispatch.id,
            provider="sendgrid",
            reason="HTTP_422",
            retryable=False,
        )

        first = store.retry_dead_letter_dispatch(
            tenant_id=tenant.id,
            dispatch_id=dispatch.id,
            actor_id="operator-1",
            idempotency_key="retry-dead-letter-v1",
        )
        second = store.retry_dead_letter_dispatch(
            tenant_id=tenant.id,
            dispatch_id=dispatch.id,
            actor_id="operator-1",
            idempotency_key="retry-dead-letter-v1",
        )

        assert first.id == second.id
        assert first.status == "PENDING"
        assert first.attempt_count == 1
        assert first.dead_letter_reason is None
        assert len(store.list_dispatches(tenant_id=tenant.id, status="PENDING")) == 1
        assert session.exec(
            select(AuditEvent).where(
                AuditEvent.event_name == "revenueos.intervention.dispatch_requeued"
            )
        ).one()
