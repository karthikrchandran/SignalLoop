"""Tenant-scoped Lead Preparation Agent administration and review."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from sqlmodel import select

from app.api.deps import CurrentUser, SessionDep
from app.api.request_context import IdempotencyKeyDep
from app.api.routes.commercial_agents import _authorize_agent_admin
from app.core.idempotency import run_idempotent_mutation
from app.domain.audit.audit_events import (
    append_audit_event_to_session,
    audit_actor_role,
)
from app.domain.commercial_agents.models import (
    AgentDependency,
    AgentDeployment,
    AgentDeploymentStatus,
    AgentType,
)
from app.domain.lead_preparation.models import (
    LeadPreparationJob,
    LeadPreparationPackage,
    LeadScoringPolicy,
    LeadScoringPolicyStatus,
)
from app.domain.lead_preparation.reconciliation import (
    LeadPreparationReconciliationError,
    LeadPreparationReconciliationReport,
    build_lead_preparation_reconciliation_report,
    ingest_lead_outcome,
    replay_dead_letter_job,
)
from app.domain.lead_preparation.schemas import (
    LeadOutcomeCreate,
    LeadOutcomePublic,
    LeadPackageDecision,
    LeadPackagePublic,
    LeadPackageRoute,
    LeadPolicyCreate,
    LeadPolicyDecision,
    LeadPolicyDryRun,
    LeadPolicyPublic,
    LeadPreparationJobCreate,
    LeadPreparationJobPublic,
    LeadScoreDryRunPublic,
)
from app.domain.lead_preparation.scoring import score_contact
from app.domain.lead_preparation.service import (
    LeadPreparationError,
    LeadPreparationOwnershipError,
    enqueue_preparation_job,
    record_policy_change_evidence,
    record_policy_evaluation_evidence,
    require_active_tenant_workspace_binding,
    require_policy_evaluation_evidence,
)
from app.domain_models import Contact

router = APIRouter(prefix="/lead-preparation", tags=["lead-preparation"])


def _digest(payload: object) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _require_active_binding(
    session: SessionDep, *, tenant_id: uuid.UUID, workspace_id: str
) -> None:
    try:
        require_active_tenant_workspace_binding(
            session, tenant_id=tenant_id, workspace_id=workspace_id
        )
    except LeadPreparationOwnershipError as exc:
        raise HTTPException(status_code=404, detail="Workspace not found") from exc


def _policy_from_payload(
    *, tenant_id: uuid.UUID, payload: LeadPolicyCreate
) -> LeadScoringPolicy:
    policy_values = payload.model_dump(mode="json")
    return LeadScoringPolicy(
        tenant_id=tenant_id,
        **payload.model_dump(),
        policy_digest=_digest(policy_values),
    )


@router.post(
    "/tenants/{tenant_id}/policies/dry-run",
    response_model=LeadScoreDryRunPublic,
)
def dry_run_policy(
    *,
    session: SessionDep,
    user: CurrentUser,
    tenant_id: uuid.UUID,
    payload: LeadPolicyDryRun,
) -> dict[str, Any]:
    _authorize_agent_admin(session, user, tenant_id)
    _require_active_binding(
        session, tenant_id=tenant_id, workspace_id=payload.workspace_id
    )
    contact = session.exec(
        select(Contact).where(
            Contact.id == payload.contact_id,
            Contact.workspace_id == payload.workspace_id,
        )
    ).one_or_none()
    if contact is None:
        raise HTTPException(status_code=404, detail="Contact not found")
    policy = _policy_from_payload(
        tenant_id=tenant_id,
        payload=LeadPolicyCreate.model_validate(payload.model_dump(exclude={"contact_id"})),
    )
    result = score_contact(contact=contact, policy=policy)
    public_result = {
        "score": result.score,
        "band": result.band,
        "contributions": [item.model_dump(mode="json") for item in result.contributions],
        "reasons": result.reasons,
        "negative_factors": result.negative_factors,
        "exclusions": result.exclusions,
        "channel_eligibility": result.channel_eligibility,
    }
    evidence = record_policy_evaluation_evidence(
        session,
        tenant_id=tenant_id,
        workspace_id=payload.workspace_id,
        contact_id=contact.id,
        actor_id=user.id,
        policy_digest=policy.policy_digest,
        input_payload=payload.model_dump(mode="json"),
        result_payload=public_result,
    )
    append_audit_event_to_session(
        session,
        event_name="lead_policy.evaluated",
        workspace_id=payload.workspace_id,
        actor_id=user.id,
        actor_role=audit_actor_role(user),
        resource_type="lead_policy_evaluation_evidence",
        resource_id=str(evidence.id),
        payload={"tenant_id": str(tenant_id), "policy_digest": policy.policy_digest},
    )
    session.commit()
    return {"evaluation_id": evidence.id, **public_result}


@router.get(
    "/tenants/{tenant_id}/policies", response_model=list[LeadPolicyPublic]
)
def list_policies(
    *, session: SessionDep, user: CurrentUser, tenant_id: uuid.UUID, workspace_id: str
) -> list[LeadScoringPolicy]:
    _authorize_agent_admin(session, user, tenant_id)
    _require_active_binding(session, tenant_id=tenant_id, workspace_id=workspace_id)
    return list(
        session.exec(
            select(LeadScoringPolicy)
            .where(
                LeadScoringPolicy.tenant_id == tenant_id,
                LeadScoringPolicy.workspace_id == workspace_id,
            )
            .order_by(LeadScoringPolicy.version.desc())
        ).all()
    )


@router.post(
    "/tenants/{tenant_id}/policies",
    response_model=LeadPolicyPublic,
    status_code=status.HTTP_201_CREATED,
)
async def create_policy(
    request: Request,
    *,
    session: SessionDep,
    user: CurrentUser,
    tenant_id: uuid.UUID,
    payload: LeadPolicyCreate,
    idempotency_key: IdempotencyKeyDep,
) -> dict[str, Any]:
    _authorize_agent_admin(session, user, tenant_id)
    _require_active_binding(
        session, tenant_id=tenant_id, workspace_id=payload.workspace_id
    )

    def create_once() -> dict[str, Any]:
        if session.exec(
            select(LeadScoringPolicy).where(
                LeadScoringPolicy.tenant_id == tenant_id,
                LeadScoringPolicy.workspace_id == payload.workspace_id,
                LeadScoringPolicy.version == payload.version,
            )
        ).one_or_none():
            raise HTTPException(status_code=409, detail="Policy version already exists")
        policy = _policy_from_payload(tenant_id=tenant_id, payload=payload)
        policy.created_by = user.id
        session.add(policy)
        session.flush()
        record_policy_change_evidence(
            session,
            policy=policy,
            action="CREATED",
            from_status=None,
            to_status=LeadScoringPolicyStatus.DRAFT,
            actor_id=user.id,
            actor_role=audit_actor_role(user),
            reason="Policy version created",
            idempotency_key=idempotency_key,
        )
        append_audit_event_to_session(
            session,
            event_name="lead_policy.created",
            workspace_id=payload.workspace_id,
            actor_id=user.id,
            actor_role=audit_actor_role(user),
            resource_type="lead_scoring_policy",
            resource_id=str(policy.id),
            payload={"tenant_id": str(tenant_id), "version": policy.version},
        )
        return LeadPolicyPublic.model_validate(policy).model_dump(mode="json")

    return await run_idempotent_mutation(
        request,
        session=session,
        idempotency_key=idempotency_key,
        workspace_id=str(tenant_id),
        operation="lead-preparation:policy:create",
        request_payload=payload.model_dump(mode="json"),
        mutation=create_once,
        safe_to_retry_on_failure=True,
    )


@router.get(
    "/tenants/{tenant_id}/operations/reconciliation",
    response_model=LeadPreparationReconciliationReport,
)
def reconciliation_report(
    *, session: SessionDep, user: CurrentUser, tenant_id: uuid.UUID, workspace_id: str
) -> LeadPreparationReconciliationReport:
    _authorize_agent_admin(session, user, tenant_id)
    return build_lead_preparation_reconciliation_report(
        session, tenant_id=tenant_id, workspace_id=workspace_id
    )


@router.post(
    "/tenants/{tenant_id}/jobs/{job_id}/replay",
    response_model=LeadPreparationJobPublic,
)
async def replay_dead_letter(
    request: Request,
    *,
    session: SessionDep,
    user: CurrentUser,
    tenant_id: uuid.UUID,
    job_id: uuid.UUID,
    payload: LeadPackageDecision,
    idempotency_key: IdempotencyKeyDep,
) -> dict[str, Any]:
    _authorize_agent_admin(session, user, tenant_id)

    def replay_once() -> dict[str, Any]:
        workspace = session.exec(
            select(LeadPreparationJob.workspace_id).where(
                LeadPreparationJob.id == job_id,
                LeadPreparationJob.tenant_id == tenant_id,
            )
        ).one_or_none()
        if workspace is None:
            raise HTTPException(status_code=404, detail="Lead preparation job not found")
        try:
            job = replay_dead_letter_job(
                session,
                tenant_id=tenant_id,
                workspace_id=workspace,
                job_id=job_id,
                actor_id=user.id,
                actor_role=audit_actor_role(user),
                capabilities={"agents.admin.manage"},
                reason=payload.reason,
            )
        except LeadPreparationReconciliationError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return LeadPreparationJobPublic.model_validate(job).model_dump(mode="json")

    return await run_idempotent_mutation(
        request,
        session=session,
        idempotency_key=idempotency_key,
        workspace_id=str(tenant_id),
        operation=f"lead-preparation:job:{job_id}:replay",
        request_payload=payload.model_dump(mode="json"),
        mutation=replay_once,
        safe_to_retry_on_failure=True,
    )


@router.post(
    "/tenants/{tenant_id}/outcomes",
    response_model=LeadOutcomePublic,
    status_code=status.HTTP_201_CREATED,
)
async def create_outcome(
    request: Request,
    *,
    session: SessionDep,
    user: CurrentUser,
    tenant_id: uuid.UUID,
    payload: LeadOutcomeCreate,
    idempotency_key: IdempotencyKeyDep,
) -> dict[str, Any]:
    _authorize_agent_admin(session, user, tenant_id)
    _require_active_binding(
        session, tenant_id=tenant_id, workspace_id=payload.workspace_id
    )

    def ingest_once() -> dict[str, Any]:
        try:
            observation = ingest_lead_outcome(
                session,
                tenant_id=tenant_id,
                workspace_id=payload.workspace_id,
                contact_id=payload.contact_id,
                policy_id=payload.policy_id,
                outcome_type=payload.outcome_type,
                outcome_reference=payload.outcome_reference,
                observed_at=payload.observed_at,
                idempotency_key=idempotency_key,
            )
        except LeadPreparationReconciliationError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        append_audit_event_to_session(
            session,
            event_name="lead_preparation.outcome.observed",
            workspace_id=payload.workspace_id,
            actor_id=user.id,
            actor_role=audit_actor_role(user),
            resource_type="lead_outcome_observation",
            resource_id=str(observation.id),
            payload={
                "outcome_type": observation.outcome_type,
                "policy_version": observation.policy_version,
                "tenant_id": str(tenant_id),
            },
        )
        return LeadOutcomePublic.model_validate(observation).model_dump(mode="json")

    return await run_idempotent_mutation(
        request,
        session=session,
        idempotency_key=idempotency_key,
        workspace_id=str(tenant_id),
        operation="lead-preparation:outcome:create",
        request_payload=payload.model_dump(mode="json"),
        mutation=ingest_once,
        safe_to_retry_on_failure=True,
    )


@router.post(
    "/tenants/{tenant_id}/policies/{policy_id}/approve",
    response_model=LeadPolicyPublic,
)
async def approve_policy(
    request: Request,
    *,
    session: SessionDep,
    user: CurrentUser,
    tenant_id: uuid.UUID,
    policy_id: uuid.UUID,
    payload: LeadPolicyDecision,
    idempotency_key: IdempotencyKeyDep,
) -> dict[str, Any]:
    _authorize_agent_admin(session, user, tenant_id)

    def approve_once() -> dict[str, Any]:
        policy = session.exec(
            select(LeadScoringPolicy)
            .where(
                LeadScoringPolicy.id == policy_id,
                LeadScoringPolicy.tenant_id == tenant_id,
            )
            .with_for_update()
        ).one_or_none()
        if policy is None:
            raise HTTPException(status_code=404, detail="Policy not found")
        _require_active_binding(
            session, tenant_id=tenant_id, workspace_id=policy.workspace_id
        )
        if policy.status == LeadScoringPolicyStatus.APPROVED:
            return LeadPolicyPublic.model_validate(policy).model_dump(mode="json")
        if policy.status != LeadScoringPolicyStatus.DRAFT:
            raise HTTPException(status_code=409, detail="Only draft policies can be approved")
        if policy.created_by is None or policy.created_by == user.id:
            raise HTTPException(
                status_code=409,
                detail="Policy approval requires an independent administrator",
            )
        try:
            evaluation = require_policy_evaluation_evidence(session, policy=policy)
        except LeadPreparationError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        policy.status = LeadScoringPolicyStatus.APPROVED
        policy.approved_by = user.id
        policy.approved_at = datetime.now(timezone.utc)
        session.add(policy)
        record_policy_change_evidence(
            session,
            policy=policy,
            action="APPROVED",
            from_status=LeadScoringPolicyStatus.DRAFT,
            to_status=LeadScoringPolicyStatus.APPROVED,
            actor_id=user.id,
            actor_role=audit_actor_role(user),
            reason=payload.reason,
            idempotency_key=idempotency_key,
        )
        append_audit_event_to_session(
            session,
            event_name="lead_policy.approved",
            workspace_id=policy.workspace_id,
            actor_id=user.id,
            actor_role=audit_actor_role(user),
            resource_type="lead_scoring_policy",
            resource_id=str(policy.id),
            payload={
                "tenant_id": str(tenant_id),
                "reason": payload.reason,
                "evaluation_id": str(evaluation.id),
                "evaluation_result_digest": evaluation.result_digest,
            },
        )
        session.flush()
        return LeadPolicyPublic.model_validate(policy).model_dump(mode="json")

    return await run_idempotent_mutation(
        request,
        session=session,
        idempotency_key=idempotency_key,
        workspace_id=str(tenant_id),
        operation=f"lead-preparation:policy:{policy_id}:approve",
        request_payload=payload.model_dump(mode="json"),
        mutation=approve_once,
        safe_to_retry_on_failure=True,
    )


@router.post(
    "/tenants/{tenant_id}/policies/{policy_id}/publish",
    response_model=LeadPolicyPublic,
)
async def publish_policy(
    request: Request,
    *,
    session: SessionDep,
    user: CurrentUser,
    tenant_id: uuid.UUID,
    policy_id: uuid.UUID,
    idempotency_key: IdempotencyKeyDep,
) -> dict[str, Any]:
    _authorize_agent_admin(session, user, tenant_id)

    def publish_once() -> dict[str, Any]:
        policy = session.exec(
            select(LeadScoringPolicy)
            .where(
                LeadScoringPolicy.id == policy_id,
                LeadScoringPolicy.tenant_id == tenant_id,
            )
            .with_for_update()
        ).one_or_none()
        if policy is None:
            raise HTTPException(status_code=404, detail="Policy not found")
        _require_active_binding(
            session, tenant_id=tenant_id, workspace_id=policy.workspace_id
        )
        if policy.status == LeadScoringPolicyStatus.PUBLISHED:
            return LeadPolicyPublic.model_validate(policy).model_dump(mode="json")
        if (
            policy.status != LeadScoringPolicyStatus.APPROVED
            or policy.approved_by is None
            or policy.approved_at is None
        ):
            raise HTTPException(
                status_code=409, detail="Policy requires independent approval before publish"
            )
        previous = session.exec(
            select(LeadScoringPolicy).where(
                LeadScoringPolicy.tenant_id == tenant_id,
                LeadScoringPolicy.workspace_id == policy.workspace_id,
                LeadScoringPolicy.status == LeadScoringPolicyStatus.PUBLISHED,
            )
        ).all()
        for item in previous:
            item.status = LeadScoringPolicyStatus.SUPERSEDED
            session.add(item)
            record_policy_change_evidence(
                session,
                policy=item,
                action="SUPERSEDED",
                from_status=LeadScoringPolicyStatus.PUBLISHED,
                to_status=LeadScoringPolicyStatus.SUPERSEDED,
                actor_id=user.id,
                actor_role=audit_actor_role(user),
                reason=f"Superseded by policy {policy.id}",
                idempotency_key=idempotency_key,
            )
        policy.status = LeadScoringPolicyStatus.PUBLISHED
        session.add(policy)
        record_policy_change_evidence(
            session,
            policy=policy,
            action="PUBLISHED",
            from_status=LeadScoringPolicyStatus.APPROVED,
            to_status=LeadScoringPolicyStatus.PUBLISHED,
            actor_id=user.id,
            actor_role=audit_actor_role(user),
            reason="Approved policy published",
            idempotency_key=idempotency_key,
        )
        append_audit_event_to_session(
            session,
            event_name="lead_policy.published",
            workspace_id=policy.workspace_id,
            actor_id=user.id,
            actor_role=audit_actor_role(user),
            resource_type="lead_scoring_policy",
            resource_id=str(policy.id),
            payload={"tenant_id": str(tenant_id), "version": policy.version},
        )
        session.flush()
        return LeadPolicyPublic.model_validate(policy).model_dump(mode="json")

    return await run_idempotent_mutation(
        request,
        session=session,
        idempotency_key=idempotency_key,
        workspace_id=str(tenant_id),
        operation=f"lead-preparation:policy:{policy_id}:publish",
        request_payload={},
        mutation=publish_once,
        safe_to_retry_on_failure=True,
    )


@router.post(
    "/tenants/{tenant_id}/jobs",
    response_model=LeadPreparationJobPublic,
    status_code=status.HTTP_201_CREATED,
)
async def create_job(
    request: Request,
    *,
    session: SessionDep,
    user: CurrentUser,
    tenant_id: uuid.UUID,
    payload: LeadPreparationJobCreate,
    idempotency_key: IdempotencyKeyDep,
) -> dict[str, Any]:
    _authorize_agent_admin(session, user, tenant_id)

    def create_once() -> dict[str, Any]:
        try:
            job = enqueue_preparation_job(
                session,
                tenant_id=tenant_id,
                workspace_id=payload.workspace_id,
                deployment_id=payload.deployment_id,
                contact_id=payload.contact_id,
                policy_id=payload.policy_id,
                event_key=payload.event_key,
                max_attempts=payload.max_attempts,
            )
        except LeadPreparationOwnershipError as exc:
            raise HTTPException(status_code=404, detail="Lead preparation input not found") from exc
        except LeadPreparationError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        append_audit_event_to_session(
            session,
            event_name="lead_preparation.enqueued",
            workspace_id=job.workspace_id,
            actor_id=user.id,
            actor_role=audit_actor_role(user),
            resource_type="lead_preparation_job",
            resource_id=str(job.id),
            payload={"contact_id": str(job.contact_id), "tenant_id": str(tenant_id)},
        )
        return LeadPreparationJobPublic.model_validate(job).model_dump(mode="json")

    return await run_idempotent_mutation(
        request,
        session=session,
        idempotency_key=idempotency_key,
        workspace_id=str(tenant_id),
        operation="lead-preparation:job:create",
        request_payload=payload.model_dump(mode="json"),
        mutation=create_once,
        safe_to_retry_on_failure=True,
    )


@router.get(
    "/tenants/{tenant_id}/packages", response_model=list[LeadPackagePublic]
)
def list_packages(
    *, session: SessionDep, user: CurrentUser, tenant_id: uuid.UUID, workspace_id: str
) -> list[LeadPreparationPackage]:
    _authorize_agent_admin(session, user, tenant_id)
    _require_active_binding(session, tenant_id=tenant_id, workspace_id=workspace_id)
    return list(
        session.exec(
            select(LeadPreparationPackage)
            .where(
                LeadPreparationPackage.tenant_id == tenant_id,
                LeadPreparationPackage.workspace_id == workspace_id,
            )
            .order_by(LeadPreparationPackage.created_at.desc())
        ).all()
    )


def _load_package(
    session: SessionDep, *, tenant_id: uuid.UUID, package_id: uuid.UUID
) -> LeadPreparationPackage:
    package = session.exec(
        select(LeadPreparationPackage)
        .where(
            LeadPreparationPackage.id == package_id,
            LeadPreparationPackage.tenant_id == tenant_id,
        )
        .with_for_update()
    ).one_or_none()
    if package is None:
        raise HTTPException(status_code=404, detail="Lead package not found")
    return package


async def _review_package(
    request: Request,
    *,
    session: SessionDep,
    user: CurrentUser,
    tenant_id: uuid.UUID,
    package_id: uuid.UUID,
    payload: LeadPackageDecision,
    idempotency_key: str,
    decision: str,
) -> dict[str, Any]:
    _authorize_agent_admin(session, user, tenant_id)

    def review_once() -> dict[str, Any]:
        package = _load_package(session, tenant_id=tenant_id, package_id=package_id)
        if package.review_state == decision:
            return LeadPackagePublic.model_validate(package).model_dump(mode="json")
        if package.review_state != "PENDING":
            raise HTTPException(status_code=409, detail="Package was already reviewed")
        package.review_state = decision
        session.add(package)
        append_audit_event_to_session(
            session,
            event_name=f"lead_preparation.package.{decision.lower()}",
            workspace_id=package.workspace_id,
            actor_id=user.id,
            actor_role=audit_actor_role(user),
            resource_type="lead_preparation_package",
            resource_id=str(package.id),
            payload={"reason": payload.reason, "tenant_id": str(tenant_id)},
        )
        session.flush()
        return LeadPackagePublic.model_validate(package).model_dump(mode="json")

    return await run_idempotent_mutation(
        request,
        session=session,
        idempotency_key=idempotency_key,
        workspace_id=str(tenant_id),
        operation=f"lead-preparation:package:{package_id}:{decision.lower()}",
        request_payload=payload.model_dump(mode="json"),
        mutation=review_once,
        safe_to_retry_on_failure=True,
    )


@router.post("/tenants/{tenant_id}/packages/{package_id}/approve")
async def approve_package(
    request: Request,
    *,
    session: SessionDep,
    user: CurrentUser,
    tenant_id: uuid.UUID,
    package_id: uuid.UUID,
    payload: LeadPackageDecision,
    idempotency_key: IdempotencyKeyDep,
) -> dict[str, Any]:
    return await _review_package(
        request,
        session=session,
        user=user,
        tenant_id=tenant_id,
        package_id=package_id,
        payload=payload,
        idempotency_key=idempotency_key,
        decision="APPROVED",
    )


@router.post("/tenants/{tenant_id}/packages/{package_id}/reject")
async def reject_package(
    request: Request,
    *,
    session: SessionDep,
    user: CurrentUser,
    tenant_id: uuid.UUID,
    package_id: uuid.UUID,
    payload: LeadPackageDecision,
    idempotency_key: IdempotencyKeyDep,
) -> dict[str, Any]:
    return await _review_package(
        request,
        session=session,
        user=user,
        tenant_id=tenant_id,
        package_id=package_id,
        payload=payload,
        idempotency_key=idempotency_key,
        decision="REJECTED",
    )


@router.post("/tenants/{tenant_id}/packages/{package_id}/route")
async def route_package(
    request: Request,
    *,
    session: SessionDep,
    user: CurrentUser,
    tenant_id: uuid.UUID,
    package_id: uuid.UUID,
    payload: LeadPackageRoute,
    idempotency_key: IdempotencyKeyDep,
) -> dict[str, Any]:
    _authorize_agent_admin(session, user, tenant_id)

    def route_once() -> dict[str, Any]:
        package = _load_package(session, tenant_id=tenant_id, package_id=package_id)
        _require_active_binding(
            session, tenant_id=tenant_id, workspace_id=package.workspace_id
        )
        if package.review_state == "ROUTED":
            return LeadPackagePublic.model_validate(package).model_dump(mode="json")
        if package.review_state != "APPROVED":
            raise HTTPException(status_code=409, detail="Package must be approved first")
        contact = session.get(Contact, package.contact_id)
        if (
            contact is None
            or contact.workspace_id != package.workspace_id
            or contact.suppressed
            or contact.do_not_contact
            or (payload.channel == "email" and not contact.consent_email)
            or (payload.channel == "voice" and not contact.consent_voice)
        ):
            raise HTTPException(status_code=409, detail="Contact is not eligible for channel")
        target_type = (
            AgentType.EMAIL_OUTREACH
            if payload.channel == "email"
            else AgentType.VOICE_CONVERSATION
        )
        dependencies = session.exec(
            select(AgentDependency).where(
                AgentDependency.tenant_id == tenant_id,
                AgentDependency.source_deployment_id == package.agent_deployment_id,
                AgentDependency.status == "ACTIVE",
            )
        ).all()
        target = next(
            (
                deployment
                for edge in dependencies
                if (deployment := session.get(AgentDeployment, edge.target_deployment_id))
                is not None
                and deployment.tenant_id == tenant_id
                and deployment.workspace_id == package.workspace_id
                and deployment.status == AgentDeploymentStatus.ACTIVE
                and deployment.agent_type == target_type
            ),
            None,
        )
        if target is None:
            raise HTTPException(
                status_code=409,
                detail=f"Active paid {payload.channel} agent dependency is required",
            )
        package.review_state = "ROUTED"
        package.draft_references = {
            **package.draft_references,
            payload.channel: {
                "target_deployment_id": str(target.id),
                "status": "PENDING_HANDOFF",
            },
        }
        session.add(package)
        job = session.exec(
            select(LeadPreparationJob).where(LeadPreparationJob.package_id == package.id)
        ).one_or_none()
        if job is not None:
            job.status = "ROUTED"
            session.add(job)
        append_audit_event_to_session(
            session,
            event_name="lead_preparation.package.routed",
            workspace_id=package.workspace_id,
            actor_id=user.id,
            actor_role=audit_actor_role(user),
            resource_type="lead_preparation_package",
            resource_id=str(package.id),
            payload={"channel": payload.channel, "target_deployment_id": str(target.id)},
        )
        session.flush()
        return LeadPackagePublic.model_validate(package).model_dump(mode="json")

    return await run_idempotent_mutation(
        request,
        session=session,
        idempotency_key=idempotency_key,
        workspace_id=str(tenant_id),
        operation=f"lead-preparation:package:{package_id}:route",
        request_payload=payload.model_dump(mode="json"),
        mutation=route_once,
        safe_to_retry_on_failure=True,
    )
