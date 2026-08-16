"""Operational reconciliation and outcome evaluation for lead preparation."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlmodel import Field, Session, SQLModel, func, select

from app.domain.audit.audit_events import append_audit_event_to_session
from app.domain.commercial_agents.models import AgentUsageLedger, AgentUsageState
from app.domain.lead_preparation.models import (
    LeadOutcomeObservation,
    LeadPreparationJob,
    LeadPreparationJobStatus,
    LeadScoringPolicy,
)
from app.domain_models import Contact


class LeadPreparationReconciliationError(ValueError):
    """A reconciliation request is unauthorized, conflicting, or unsafe."""


class LeadPreparationReconciliationReport(SQLModel):
    tenant_id: uuid.UUID
    workspace_id: str
    unknown_outcomes: int = Field(ge=0)
    missing_terminal_packages: int = Field(ge=0)
    usage_mismatches: int = Field(ge=0)
    dead_letters: int = Field(ge=0)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def build_lead_preparation_reconciliation_report(
    session: Session, *, tenant_id: uuid.UUID, workspace_id: str
) -> LeadPreparationReconciliationReport:
    """Return bounded aggregate integrity signals without exposing payloads."""

    base = (
        LeadPreparationJob.tenant_id == tenant_id,
        LeadPreparationJob.workspace_id == workspace_id,
    )
    unknown = session.exec(
        select(func.count(LeadPreparationJob.id)).where(
            *base,
            LeadPreparationJob.status
            == LeadPreparationJobStatus.UNKNOWN_OUTCOME.value,
        )
    ).one()
    missing_packages = session.exec(
        select(func.count(LeadPreparationJob.id)).where(
            *base,
            LeadPreparationJob.status.in_(
                [
                    LeadPreparationJobStatus.COMPLETED.value,
                    LeadPreparationJobStatus.ROUTED.value,
                ]
            ),
            LeadPreparationJob.package_id.is_(None),
        )
    ).one()
    usage_mismatches = session.exec(
        select(func.count(LeadPreparationJob.id))
        .select_from(LeadPreparationJob)
        .outerjoin(
            AgentUsageLedger,
            AgentUsageLedger.id == LeadPreparationJob.usage_reservation_id,
        )
        .where(
            *base,
            LeadPreparationJob.status.in_(
                [
                    LeadPreparationJobStatus.COMPLETED.value,
                    LeadPreparationJobStatus.ROUTED.value,
                ]
            ),
            (LeadPreparationJob.usage_reservation_id.is_(None))
            | (AgentUsageLedger.state.is_(None))
            | (AgentUsageLedger.state != AgentUsageState.FINALIZED.value),
        )
    ).one()
    dead_letters = session.exec(
        select(func.count(LeadPreparationJob.id)).where(
            *base,
            LeadPreparationJob.status == LeadPreparationJobStatus.DEAD_LETTER.value,
        )
    ).one()
    return LeadPreparationReconciliationReport(
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        unknown_outcomes=int(unknown),
        missing_terminal_packages=int(missing_packages),
        usage_mismatches=int(usage_mismatches),
        dead_letters=int(dead_letters),
    )


def replay_dead_letter_job(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    workspace_id: str,
    job_id: uuid.UUID,
    actor_id: uuid.UUID,
    actor_role: str,
    capabilities: set[str],
    reason: str,
    now: datetime | None = None,
) -> LeadPreparationJob:
    """Authorize and audit explicit replay of one terminal safe failure."""

    if "agents.admin.manage" not in capabilities or not actor_role.strip():
        raise LeadPreparationReconciliationError(
            "agent administration capability is required"
        )
    if not reason.strip():
        raise LeadPreparationReconciliationError("replay reason is required")
    job = session.exec(
        select(LeadPreparationJob)
        .where(
            LeadPreparationJob.id == job_id,
            LeadPreparationJob.tenant_id == tenant_id,
            LeadPreparationJob.workspace_id == workspace_id,
        )
        .with_for_update()
    ).one_or_none()
    if job is None:
        raise LeadPreparationReconciliationError("lead preparation job was not found")
    if job.status != LeadPreparationJobStatus.DEAD_LETTER:
        raise LeadPreparationReconciliationError("only dead-letter jobs can be replayed")
    at = _utc(now or datetime.now(timezone.utc))
    job.status = LeadPreparationJobStatus.PENDING
    job.attempt_count = 0
    job.available_at = at
    job.lease_token = None
    job.lease_expires_at = None
    job.last_error_code = None
    job.last_error_detail = None
    job.updated_at = at
    session.add(job)
    append_audit_event_to_session(
        session,
        event_name="lead_preparation.dead_letter.replayed",
        workspace_id=workspace_id,
        actor_id=actor_id,
        actor_role=actor_role.strip(),
        resource_type="lead_preparation_job",
        resource_id=str(job.id),
        payload={"reason": reason.strip(), "tenant_id": str(tenant_id)},
    )
    session.flush()
    return job


def ingest_lead_outcome(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    workspace_id: str,
    contact_id: uuid.UUID,
    policy_id: uuid.UUID,
    outcome_type: str,
    outcome_reference: str,
    observed_at: datetime,
    idempotency_key: str,
) -> LeadOutcomeObservation:
    """Persist an immutable outcome observation without modifying policy state."""

    key = idempotency_key.strip()
    outcome = outcome_type.strip().upper()
    reference = outcome_reference.strip()
    if not key or not outcome or not reference:
        raise LeadPreparationReconciliationError(
            "outcome type, reference, and idempotency key are required"
        )
    existing = session.exec(
        select(LeadOutcomeObservation).where(
            LeadOutcomeObservation.tenant_id == tenant_id,
            LeadOutcomeObservation.workspace_id == workspace_id,
            LeadOutcomeObservation.idempotency_key == key,
        )
    ).one_or_none()
    if existing is not None:
        if (
            existing.contact_id != contact_id
            or existing.policy_id != policy_id
            or existing.outcome_type != outcome
            or existing.outcome_reference != reference
        ):
            raise LeadPreparationReconciliationError("outcome idempotency key conflicts")
        return existing
    contact = session.get(Contact, contact_id)
    policy = session.get(LeadScoringPolicy, policy_id)
    if (
        contact is None
        or contact.workspace_id != workspace_id
        or policy is None
        or policy.tenant_id != tenant_id
        or policy.workspace_id != workspace_id
    ):
        raise LeadPreparationReconciliationError(
            "owned contact and scoring policy are required"
        )
    observation = LeadOutcomeObservation(
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        contact_id=contact_id,
        policy_id=policy_id,
        policy_version=policy.version,
        outcome_type=outcome,
        outcome_reference=reference,
        observed_at=_utc(observed_at),
        idempotency_key=key,
    )
    session.add(observation)
    session.flush()
    return observation
