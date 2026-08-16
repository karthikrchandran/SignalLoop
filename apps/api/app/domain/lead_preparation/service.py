"""Transactional administration for immutable lead-scoring policies."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import update
from sqlmodel import Session, select

from app.domain.commercial_agents.models import (
    AgentDeployment,
    AgentDeploymentStatus,
    AgentType,
)
from app.domain.lead_preparation.models import (
    LeadPolicyChangeEvidence,
    LeadPolicyEvaluationEvidence,
    LeadPreparationJob,
    LeadPreparationJobStatus,
    LeadScoringPolicy,
    LeadScoringPolicyStatus,
)
from app.domain.tenants.models import TenantWorkspaceBinding
from app.domain_models import Contact


class LeadPreparationError(ValueError):
    """Base error for deterministic lead-preparation rules."""


class PublishedPolicyImmutableError(LeadPreparationError):
    """A published policy must be superseded by a new version."""


class LeadPreparationOwnershipError(LeadPreparationError):
    """Requested work crosses a tenant, workspace, or deployment boundary."""


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _digest(value: object) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def require_active_tenant_workspace_binding(
    session: Session, *, tenant_id: uuid.UUID, workspace_id: str
) -> TenantWorkspaceBinding:
    """Fail closed before any lead-preparation contact access."""

    binding = session.exec(
        select(TenantWorkspaceBinding).where(
            TenantWorkspaceBinding.tenant_id == tenant_id,
            TenantWorkspaceBinding.workspace_id == workspace_id,
            TenantWorkspaceBinding.status == "ACTIVE",
        )
    ).one_or_none()
    if binding is None:
        raise LeadPreparationOwnershipError("active tenant workspace binding is required")
    return binding


def record_policy_evaluation_evidence(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    workspace_id: str,
    contact_id: uuid.UUID,
    actor_id: uuid.UUID,
    policy_digest: str,
    input_payload: object,
    result_payload: dict[str, Any],
) -> LeadPolicyEvaluationEvidence:
    evidence = LeadPolicyEvaluationEvidence(
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        contact_id=contact_id,
        actor_id=actor_id,
        policy_digest=policy_digest,
        input_digest=_digest(input_payload),
        result_digest=_digest(result_payload),
        result=result_payload,
    )
    session.add(evidence)
    session.flush()
    return evidence


def record_policy_change_evidence(
    session: Session,
    *,
    policy: LeadScoringPolicy,
    action: str,
    from_status: LeadScoringPolicyStatus | str | None,
    to_status: LeadScoringPolicyStatus | str,
    actor_id: uuid.UUID,
    actor_role: str,
    reason: str,
    idempotency_key: str,
) -> LeadPolicyChangeEvidence:
    evidence = LeadPolicyChangeEvidence(
        tenant_id=policy.tenant_id,
        workspace_id=policy.workspace_id,
        policy_id=policy.id,
        action=action,
        from_status=(
            from_status.value if isinstance(from_status, LeadScoringPolicyStatus) else from_status
        ),
        to_status=to_status.value if isinstance(to_status, LeadScoringPolicyStatus) else to_status,
        actor_id=actor_id,
        actor_role=actor_role,
        reason=reason.strip(),
        policy_digest=policy.policy_digest,
        idempotency_key=idempotency_key,
    )
    session.add(evidence)
    session.flush()
    return evidence


def update_scoring_policy(
    session: Session,
    *,
    policy_id: uuid.UUID,
    feature_weights: dict[str, int] | None = None,
    band_thresholds: dict[str, int] | None = None,
    freshness_windows: dict[str, int] | None = None,
    exclusion_rules: list[str] | None = None,
) -> LeadScoringPolicy:
    """Update a draft; published history is immutable by service contract."""

    policy = session.get(LeadScoringPolicy, policy_id)
    if policy is None:
        raise LeadPreparationError("lead scoring policy was not found")
    if policy.status is not LeadScoringPolicyStatus.DRAFT:
        raise PublishedPolicyImmutableError(
            "published lead scoring policies must be superseded"
        )
    changes: dict[str, Any] = {
        "feature_weights": feature_weights,
        "band_thresholds": band_thresholds,
        "freshness_windows": freshness_windows,
        "exclusion_rules": exclusion_rules,
    }
    for field, value in changes.items():
        if value is not None:
            setattr(policy, field, value)
    session.add(policy)
    session.flush()
    return policy


def enqueue_preparation_job(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    workspace_id: str,
    deployment_id: uuid.UUID,
    contact_id: uuid.UUID,
    policy_id: uuid.UUID,
    event_key: str,
    max_attempts: int = 5,
    now: datetime | None = None,
) -> LeadPreparationJob:
    """Persist one tenant-scoped preparation job per source event."""

    key = event_key.strip()
    if not key or max_attempts < 1 or max_attempts > 20:
        raise LeadPreparationError("event key and valid maximum attempts are required")
    require_active_tenant_workspace_binding(
        session, tenant_id=tenant_id, workspace_id=workspace_id
    )
    existing = session.exec(
        select(LeadPreparationJob).where(
            LeadPreparationJob.tenant_id == tenant_id,
            LeadPreparationJob.workspace_id == workspace_id,
            LeadPreparationJob.event_key == key,
        )
    ).one_or_none()
    if existing is not None:
        if (
            existing.deployment_id != deployment_id
            or existing.contact_id != contact_id
            or existing.policy_id != policy_id
        ):
            raise LeadPreparationOwnershipError("event key conflicts with stored job")
        return existing
    deployment = session.get(AgentDeployment, deployment_id)
    contact = session.get(Contact, contact_id)
    policy = session.get(LeadScoringPolicy, policy_id)
    if (
        deployment is None
        or deployment.tenant_id != tenant_id
        or deployment.workspace_id != workspace_id
        or deployment.agent_type != AgentType.LEAD_PREPARATION
        or deployment.status != AgentDeploymentStatus.ACTIVE
        or contact is None
        or contact.workspace_id != workspace_id
        or policy is None
        or policy.tenant_id != tenant_id
        or policy.workspace_id != workspace_id
        or policy.status != LeadScoringPolicyStatus.PUBLISHED
    ):
        raise LeadPreparationOwnershipError(
            "active owned deployment, contact, and published policy are required"
        )
    at = _utc(now or datetime.now(timezone.utc))
    job = LeadPreparationJob(
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        deployment_id=deployment_id,
        contact_id=contact_id,
        policy_id=policy_id,
        event_key=key,
        max_attempts=max_attempts,
        available_at=at,
        created_at=at,
        updated_at=at,
    )
    session.add(job)
    session.flush()
    return job


def claim_preparation_job(
    session: Session,
    *,
    now: datetime | None = None,
    lease_seconds: int = 300,
) -> LeadPreparationJob | None:
    """Atomically claim the oldest ready job and persist lease ownership."""

    at = _utc(now or datetime.now(timezone.utc))
    candidate = session.exec(
        select(LeadPreparationJob.id)
        .where(
            LeadPreparationJob.status.in_(
                [
                    LeadPreparationJobStatus.PENDING.value,
                    LeadPreparationJobStatus.RETRY_SCHEDULED.value,
                ]
            ),
            LeadPreparationJob.available_at <= at,
        )
        .order_by(LeadPreparationJob.created_at, LeadPreparationJob.id)
        .limit(1)
    ).first()
    if candidate is None:
        return None
    token = uuid.uuid4()
    statement = (
        update(LeadPreparationJob)
        .where(
            LeadPreparationJob.id == candidate,
            LeadPreparationJob.status.in_(
                [
                    LeadPreparationJobStatus.PENDING.value,
                    LeadPreparationJobStatus.RETRY_SCHEDULED.value,
                ]
            ),
            LeadPreparationJob.available_at <= at,
        )
        .values(
            status=LeadPreparationJobStatus.IN_PROGRESS.value,
            attempt_count=LeadPreparationJob.attempt_count + 1,
            lease_token=token,
            lease_expires_at=at + timedelta(seconds=lease_seconds),
            updated_at=at,
        )
        .execution_options(synchronize_session=False)
    )
    result = session.exec(statement)
    if result.rowcount != 1:
        session.rollback()
        return None
    session.commit()
    return session.exec(
        select(LeadPreparationJob).where(
            LeadPreparationJob.id == candidate,
            LeadPreparationJob.lease_token == token,
        )
    ).one()


def recover_expired_preparation_leases(
    session: Session, *, now: datetime | None = None
) -> int:
    """Requeue expired internal-only work; no external side effect has occurred."""

    at = _utc(now or datetime.now(timezone.utc))
    result = session.exec(
        update(LeadPreparationJob)
        .where(
            LeadPreparationJob.status == LeadPreparationJobStatus.IN_PROGRESS.value,
            LeadPreparationJob.lease_expires_at < at,
            LeadPreparationJob.package_id.is_(None),
        )
        .values(
            status=LeadPreparationJobStatus.RETRY_SCHEDULED.value,
            available_at=at,
            lease_token=None,
            lease_expires_at=None,
            last_error_code="LEASE_EXPIRED",
            updated_at=at,
        )
        .execution_options(synchronize_session=False)
    )
    return int(result.rowcount or 0)
