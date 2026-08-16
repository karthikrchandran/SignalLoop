from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlmodel import func, select

from app.domain.audit.audit_events import AuditEvent
from app.domain.lead_preparation.models import (
    LeadOutcomeObservation,
    LeadPreparationJobStatus,
)
from app.domain.lead_preparation.reconciliation import (
    LeadPreparationReconciliationError,
    build_lead_preparation_reconciliation_report,
    ingest_lead_outcome,
    replay_dead_letter_job,
)
from tests.workers.test_lead_preparation_worker import _context, _session


def test_report_finds_unknown_missing_package_and_usage_mismatch() -> None:
    with _session() as session:
        _, _, _, unknown = _context(session)
        _, _, _, missing_package = _context(session)
        _, _, _, usage_mismatch = _context(session)
        unknown.status = LeadPreparationJobStatus.UNKNOWN_OUTCOME
        missing_package.status = LeadPreparationJobStatus.COMPLETED
        missing_package.completed_at = datetime.now(timezone.utc)
        usage_mismatch.status = LeadPreparationJobStatus.COMPLETED
        usage_mismatch.completed_at = datetime.now(timezone.utc)
        usage_mismatch.package_id = uuid.uuid4()
        session.add_all([unknown, missing_package, usage_mismatch])
        session.commit()

        report = build_lead_preparation_reconciliation_report(
            session,
            tenant_id=unknown.tenant_id,
            workspace_id=unknown.workspace_id,
        )

        assert report.unknown_outcomes == 1
        assert report.missing_terminal_packages == 0
        assert report.usage_mismatches == 0
        other = build_lead_preparation_reconciliation_report(
            session,
            tenant_id=missing_package.tenant_id,
            workspace_id=missing_package.workspace_id,
        )
        assert other.missing_terminal_packages == 1
        third = build_lead_preparation_reconciliation_report(
            session,
            tenant_id=usage_mismatch.tenant_id,
            workspace_id=usage_mismatch.workspace_id,
        )
        assert third.usage_mismatches == 1


def test_dead_letter_replay_requires_capability_and_is_audited() -> None:
    with _session() as session:
        _, _, _, job = _context(session)
        job.status = LeadPreparationJobStatus.DEAD_LETTER
        job.last_error_code = "SOURCE_UNAVAILABLE"
        session.add(job)
        session.commit()
        actor_id = uuid.uuid4()

        with pytest.raises(LeadPreparationReconciliationError):
            replay_dead_letter_job(
                session,
                tenant_id=job.tenant_id,
                workspace_id=job.workspace_id,
                job_id=job.id,
                actor_id=actor_id,
                actor_role="employee",
                capabilities=set(),
                reason="Source recovered",
            )

        replayed = replay_dead_letter_job(
            session,
            tenant_id=job.tenant_id,
            workspace_id=job.workspace_id,
            job_id=job.id,
            actor_id=actor_id,
            actor_role="tenant_owner",
            capabilities={"agents.admin.manage"},
            reason="Source recovered",
        )
        session.commit()

        assert replayed.status == LeadPreparationJobStatus.PENDING
        assert session.exec(
            select(func.count(AuditEvent.id)).where(
                AuditEvent.event_name == "lead_preparation.dead_letter.replayed",
                AuditEvent.resource_id == str(job.id),
            )
        ).one() == 1


def test_outcome_observation_is_immutable_input_not_policy_self_modification() -> None:
    with _session() as session:
        _, contact, policy, job = _context(session)
        original_digest = policy.policy_digest

        observation = ingest_lead_outcome(
            session,
            tenant_id=job.tenant_id,
            workspace_id=job.workspace_id,
            contact_id=contact.id,
            policy_id=policy.id,
            outcome_type="MEETING_BOOKED",
            outcome_reference="calendar:event:123",
            observed_at=datetime.now(timezone.utc),
            idempotency_key="meeting-123",
        )
        replay = ingest_lead_outcome(
            session,
            tenant_id=job.tenant_id,
            workspace_id=job.workspace_id,
            contact_id=contact.id,
            policy_id=policy.id,
            outcome_type="MEETING_BOOKED",
            outcome_reference="calendar:event:123",
            observed_at=observation.observed_at,
            idempotency_key="meeting-123",
        )
        session.commit()
        session.refresh(policy)

        assert replay.id == observation.id
        assert session.exec(select(func.count(LeadOutcomeObservation.id))).one() == 1
        assert policy.policy_digest == original_digest
