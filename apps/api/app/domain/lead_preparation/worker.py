"""Bounded autonomous worker for lead preparation jobs."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import update
from sqlmodel import Session, func, select

from app.domain.audit.audit_events import append_audit_event_to_session
from app.domain.commercial_agents.capacity import finalize_capacity, reserve_capacity
from app.domain.lead_preparation.models import (
    LeadEvidenceItem,
    LeadPreparationJob,
    LeadPreparationJobStatus,
    LeadPreparationPackage,
    LeadScoreVersion,
    LeadScoringPolicy,
)
from app.domain.lead_preparation.scoring import score_contact
from app.domain.lead_preparation.service import claim_preparation_job
from app.domain_models import Contact

EvidenceCollector = Callable[[Contact], dict[str, Any]]


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _digest(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _finalize_job_status(
    session: Session,
    *,
    job: LeadPreparationJob,
    status: LeadPreparationJobStatus,
    now: datetime,
    score_version_id: object | None = None,
    package_id: object | None = None,
    usage_reservation_id: object | None = None,
) -> None:
    result = session.exec(
        update(LeadPreparationJob)
        .where(
            LeadPreparationJob.id == job.id,
            LeadPreparationJob.status == LeadPreparationJobStatus.IN_PROGRESS.value,
            LeadPreparationJob.lease_token == job.lease_token,
            LeadPreparationJob.lease_expires_at >= now,
        )
        .values(
            status=status.value,
            score_version_id=score_version_id,
            package_id=package_id,
            usage_reservation_id=usage_reservation_id,
            completed_at=now,
            lease_token=None,
            lease_expires_at=None,
            last_error_code=None,
            last_error_detail=None,
            updated_at=now,
        )
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        raise RuntimeError("lead preparation lease was lost before finalization")


def _record_failure(
    session: Session, *, job_id: object, lease_token: object, now: datetime, error: Exception
) -> None:
    job = session.get(LeadPreparationJob, job_id)
    if job is None:
        return
    terminal = job.attempt_count >= job.max_attempts
    delay_minutes = min(60, 2 ** max(0, job.attempt_count - 1))
    session.exec(
        update(LeadPreparationJob)
        .where(
            LeadPreparationJob.id == job.id,
            LeadPreparationJob.status == LeadPreparationJobStatus.IN_PROGRESS.value,
            LeadPreparationJob.lease_token == lease_token,
        )
        .values(
            status=(
                LeadPreparationJobStatus.DEAD_LETTER.value
                if terminal
                else LeadPreparationJobStatus.RETRY_SCHEDULED.value
            ),
            available_at=now + timedelta(minutes=delay_minutes),
            lease_token=None,
            lease_expires_at=None,
            last_error_code=type(error).__name__[:64],
            last_error_detail=str(error)[:1000],
            updated_at=now,
        )
        .execution_options(synchronize_session=False)
    )
    session.commit()


def _process_job(
    session: Session,
    *,
    job: LeadPreparationJob,
    evidence_collector: EvidenceCollector,
    now: datetime,
) -> None:
    contact = session.exec(
        select(Contact).where(Contact.id == job.contact_id).with_for_update()
    ).one_or_none()
    policy = session.get(LeadScoringPolicy, job.policy_id)
    if contact is None or contact.workspace_id != job.workspace_id or policy is None:
        raise RuntimeError("owned contact and scoring policy are required")
    scored = score_contact(contact=contact, policy=policy, now=now)
    if scored.exclusions:
        _finalize_job_status(
            session,
            job=job,
            status=LeadPreparationJobStatus.SUPPRESSED,
            now=now,
        )
        append_audit_event_to_session(
            session,
            event_name="lead_preparation.suppressed",
            workspace_id=job.workspace_id,
            resource_type="lead_preparation_job",
            resource_id=str(job.id),
            payload={"exclusions": scored.exclusions},
        )
        session.commit()
        return

    collected = evidence_collector(contact)
    source_type = str(collected.get("source_type", "")).strip()
    source_reference = str(collected.get("source_reference", "")).strip()
    if not source_type or not source_reference:
        raise RuntimeError("evidence source identity is required")
    redacted_excerpt = str(collected.get("redacted_excerpt", "")).strip() or None
    evidence_payload = {
        "source_type": source_type,
        "source_reference": source_reference,
        "redacted_excerpt": redacted_excerpt,
    }
    evidence_digest = _digest(evidence_payload)
    evidence = LeadEvidenceItem(
        tenant_id=job.tenant_id,
        workspace_id=job.workspace_id,
        contact_id=job.contact_id,
        source_type=source_type,
        source_reference=source_reference,
        retrieved_at=now,
        content_digest=evidence_digest,
        redacted_excerpt=redacted_excerpt,
    )
    session.add(evidence)
    reservation = reserve_capacity(
        session,
        tenant_id=job.tenant_id,
        workspace_id=job.workspace_id,
        deployment_id=job.deployment_id,
        capacity_metric="prepared_lead",
        idempotency_key=f"lead-preparation:{job.id}",
        now=now,
    )
    version = int(
        session.exec(
            select(func.coalesce(func.max(LeadScoreVersion.version), 0)).where(
                LeadScoreVersion.tenant_id == job.tenant_id,
                LeadScoreVersion.workspace_id == job.workspace_id,
                LeadScoreVersion.contact_id == job.contact_id,
            )
        ).one()
    ) + 1
    score_version = LeadScoreVersion(
        tenant_id=job.tenant_id,
        workspace_id=job.workspace_id,
        agent_deployment_id=job.deployment_id,
        contact_id=job.contact_id,
        policy_id=policy.id,
        policy_version=policy.version,
        version=version,
        score=scored.score,
        band=scored.band,
        feature_vector=scored.feature_vector,
        contributions=[item.model_dump(mode="json") for item in scored.contributions],
        reasons=scored.reasons,
        negative_factors=scored.negative_factors,
        exclusions=scored.exclusions,
        channel_eligibility=scored.channel_eligibility,
        evidence_digest=evidence_digest,
        created_at=now,
    )
    session.add(score_version)
    session.flush()
    brief = {
        "contact": {
            "name": " ".join(
                value for value in (contact.first_name, contact.last_name) if value
            ),
            "company": contact.company,
        },
        "intent": list(contact.intent_json),
        "score": scored.score,
        "band": scored.band.value,
        "reasons": scored.reasons,
        "evidence_ids": [str(evidence.id)],
    }
    next_action = {
        "action": "review_for_outreach" if scored.score >= 40 else "nurture",
        "eligible_channels": [
            channel for channel, eligible in scored.channel_eligibility.items() if eligible
        ],
    }
    package_payload = {"brief": brief, "next_action": next_action, "draft_references": {}}
    package = LeadPreparationPackage(
        tenant_id=job.tenant_id,
        workspace_id=job.workspace_id,
        agent_deployment_id=job.deployment_id,
        contact_id=job.contact_id,
        score_version_id=score_version.id,
        version=version,
        brief=brief,
        next_action=next_action,
        draft_references={},
        content_digest=_digest(package_payload),
        created_at=now,
    )
    session.add(package)
    session.flush()
    finalize_capacity(
        session,
        reservation_id=reservation.id,
        provider_receipt_id=f"lead-package:{package.id}",
        finalized_units=1,
        provider_units={"prepared_leads": 1},
        now=now,
    )
    _finalize_job_status(
        session,
        job=job,
        status=LeadPreparationJobStatus.COMPLETED,
        now=now,
        score_version_id=score_version.id,
        package_id=package.id,
        usage_reservation_id=reservation.id,
    )
    append_audit_event_to_session(
        session,
        event_name="lead_preparation.completed",
        workspace_id=job.workspace_id,
        resource_type="lead_preparation_package",
        resource_id=str(package.id),
        payload={
            "job_id": str(job.id),
            "policy_version": policy.version,
            "score_version": version,
        },
    )
    session.commit()


def run_lead_preparation_batch(
    session: Session,
    *,
    evidence_collector: EvidenceCollector,
    now: datetime | None = None,
    limit: int = 25,
) -> int:
    """Process a bounded batch; every failure is durably retried or dead-lettered."""

    processed = 0
    for _ in range(limit):
        claim_time = _utc(now or datetime.now(timezone.utc))
        job = claim_preparation_job(session, now=claim_time)
        if job is None:
            break
        token = job.lease_token
        try:
            _process_job(
                session,
                job=job,
                evidence_collector=evidence_collector,
                now=_utc(now or datetime.now(timezone.utc)),
            )
        except Exception as exc:
            session.rollback()
            _record_failure(
                session,
                job_id=job.id,
                lease_token=token,
                now=_utc(now or datetime.now(timezone.utc)),
                error=exc,
            )
        processed += 1
    return processed
