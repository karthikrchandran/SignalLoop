"""Tenant-scoped governed Proposal Agent endpoints."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlmodel import select

from app.api.deps import CurrentUser, SessionDep
from app.api.request_context import IdempotencyKeyDep
from app.api.routes.commercial_agents import _authorize_agent_admin
from app.core.idempotency import run_idempotent_mutation
from app.domain.audit.audit_events import (
    append_audit_event_to_session,
    audit_actor_role,
)
from app.domain.proposal_agent.ecrm_adapter import (
    EcrmProposalAdapterConfigurationError,
    load_ecrm_proposal_adapter,
)
from app.domain.proposal_agent.generation import (
    ClaimType,
    GroundedSource,
    ProposalDraft,
    assess_grounded_draft,
)
from app.domain.proposal_agent.models import (
    ProposalDraftReview,
    ProposalGroundingSource,
)
from app.domain.proposal_agent.service import (
    ProposalAgentError,
    enqueue_proposal_job,
    reconcile_unknown_proposal_job,
    replay_dead_letter_proposal_job,
)

router = APIRouter(prefix="/proposal-agent", tags=["proposal-agent"])


class GenerativeProposalJobCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workspace_id: str = Field(min_length=1, max_length=64)
    deployment_id: uuid.UUID
    ecrm_cell_id: str = Field(min_length=1, max_length=128)
    client_account_id: str = Field(min_length=1, max_length=255)
    proposal_id: str = Field(min_length=1, max_length=255)
    command_key: str = Field(min_length=1, max_length=255)
    draft: ProposalDraft
    source_references: list[str] = Field(min_length=1, max_length=200)


class ProposalGroundingSourcePublish(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workspace_id: str = Field(min_length=1, max_length=64)
    ecrm_cell_id: str = Field(min_length=1, max_length=128)
    client_account_id: str = Field(min_length=1, max_length=255)
    reference: str = Field(min_length=1, max_length=255)
    source_version: str = Field(min_length=1, max_length=128)
    source_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    evidence_receipt_id: str = Field(min_length=1, max_length=255)
    allowed_claim_types: set[ClaimType] = Field(min_length=1)
    allowed_claim_digests: set[str] = Field(min_length=1)

    @field_validator("allowed_claim_digests")
    @classmethod
    def validate_claim_digests(cls, value: set[str]) -> set[str]:
        if any(
            len(item) != 64 or any(char not in "0123456789abcdef" for char in item)
            for item in value
        ):
            raise ValueError("approved claim digests must be lowercase SHA-256 values")
        return value


class ProposalGroundingSourceApproval(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workspace_id: str = Field(min_length=1, max_length=64)
    ecrm_cell_id: str = Field(min_length=1, max_length=128)
    client_account_id: str = Field(min_length=1, max_length=255)
    source_version: str = Field(min_length=1, max_length=128)
    source_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    evidence_receipt_id: str = Field(min_length=1, max_length=255)


class GenerativeProposalJobPublic(BaseModel):
    job_id: uuid.UUID
    status: str
    review_state: str
    draft_digest: str
    prompt_version: str
    model_id: str


class ProposalJobReconciliation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workspace_id: str = Field(min_length=1, max_length=64)
    accepted: bool
    evidence_receipt_id: str | None = Field(default=None, min_length=1, max_length=255)
    reason: str = Field(min_length=1, max_length=1000)


class ProposalDeadLetterReplay(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workspace_id: str = Field(min_length=1, max_length=64)
    reason: str = Field(min_length=1, max_length=1000)


def _digest(value: object) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _load_adapter():
    try:
        return load_ecrm_proposal_adapter()
    except EcrmProposalAdapterConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/tenants/{tenant_id}/jobs/{job_id}/reconcile")
async def reconcile_proposal_job(
    request: Request,
    *,
    session: SessionDep,
    user: CurrentUser,
    tenant_id: uuid.UUID,
    job_id: uuid.UUID,
    payload: ProposalJobReconciliation,
    idempotency_key: IdempotencyKeyDep,
) -> dict[str, Any]:
    _authorize_agent_admin(session, user, tenant_id)

    def reconcile_once() -> dict[str, Any]:
        adapter = _load_adapter()
        try:
            job = reconcile_unknown_proposal_job(
                session,
                tenant_id=tenant_id,
                workspace_id=payload.workspace_id,
                job_id=job_id,
                adapter=adapter,
                accepted=payload.accepted,
                evidence_receipt_id=payload.evidence_receipt_id,
                reason=payload.reason,
                actor_id=user.id,
                actor_role=audit_actor_role(user),
                capabilities={"agents.admin.manage"},
            )
        except ProposalAgentError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"job_id": str(job.id), "status": job.status.value}

    return await run_idempotent_mutation(
        request,
        session=session,
        idempotency_key=idempotency_key,
        workspace_id=str(tenant_id),
        operation=f"proposal-agent:job:{job_id}:reconcile",
        request_payload=payload.model_dump(mode="json"),
        mutation=reconcile_once,
        safe_to_retry_on_failure=True,
    )


@router.post("/tenants/{tenant_id}/jobs/{job_id}/replay")
async def replay_proposal_dead_letter(
    request: Request,
    *,
    session: SessionDep,
    user: CurrentUser,
    tenant_id: uuid.UUID,
    job_id: uuid.UUID,
    payload: ProposalDeadLetterReplay,
    idempotency_key: IdempotencyKeyDep,
) -> dict[str, Any]:
    _authorize_agent_admin(session, user, tenant_id)

    def replay_once() -> dict[str, Any]:
        try:
            job = replay_dead_letter_proposal_job(
                session,
                tenant_id=tenant_id,
                workspace_id=payload.workspace_id,
                job_id=job_id,
                actor_id=user.id,
                actor_role=audit_actor_role(user),
                capabilities={"agents.admin.manage"},
                reason=payload.reason,
            )
        except ProposalAgentError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"job_id": str(job.id), "status": job.status.value}

    return await run_idempotent_mutation(
        request,
        session=session,
        idempotency_key=idempotency_key,
        workspace_id=str(tenant_id),
        operation=f"proposal-agent:job:{job_id}:replay",
        request_payload=payload.model_dump(mode="json"),
        mutation=replay_once,
        safe_to_retry_on_failure=True,
    )


@router.post(
    "/tenants/{tenant_id}/generative-jobs",
    response_model=GenerativeProposalJobPublic,
    status_code=status.HTTP_201_CREATED,
)
async def create_generative_job(
    request: Request,
    *,
    session: SessionDep,
    user: CurrentUser,
    tenant_id: uuid.UUID,
    payload: GenerativeProposalJobCreate,
    idempotency_key: IdempotencyKeyDep,
) -> dict[str, Any]:
    _authorize_agent_admin(session, user, tenant_id)
    stored_sources = session.exec(
        select(ProposalGroundingSource).where(
            ProposalGroundingSource.tenant_id == tenant_id,
            ProposalGroundingSource.workspace_id == payload.workspace_id,
            ProposalGroundingSource.ecrm_cell_id == payload.ecrm_cell_id,
            ProposalGroundingSource.client_account_id == payload.client_account_id,
            ProposalGroundingSource.reference.in_(payload.source_references),
            ProposalGroundingSource.status == "PUBLISHED",
            ProposalGroundingSource.approved_by.is_not(None),
        )
    ).all()
    if len(stored_sources) != len(set(payload.source_references)):
        raise HTTPException(
            status_code=409, detail="All grounding sources must be published"
        )
    approved_sources = [
        GroundedSource(
            reference=source.reference,
            digest=source.source_digest,
            allowed_claim_types=set(source.allowed_claim_types),
            allowed_claim_digests=set(source.allowed_claim_digests),
        )
        for source in stored_sources
    ]
    assessment = assess_grounded_draft(draft=payload.draft, sources=approved_sources)

    def create_once() -> dict[str, Any]:
        source_values = [source.model_dump(mode="json") for source in approved_sources]
        job = enqueue_proposal_job(
            session,
            tenant_id=tenant_id,
            workspace_id=payload.workspace_id,
            deployment_id=payload.deployment_id,
            ecrm_cell_id=payload.ecrm_cell_id,
            client_account_id=payload.client_account_id,
            proposal_id=payload.proposal_id,
            mode="GENERATIVE",
            command_key=payload.command_key,
            input_digest=assessment.draft_digest,
            source_digest=_digest(source_values),
            request_payload={
                "draft": payload.draft.model_dump(mode="json"),
                "sources": source_values,
            },
        )
        existing = session.exec(
            select(ProposalDraftReview).where(ProposalDraftReview.job_id == job.id)
        ).one_or_none()
        if existing is not None:
            return GenerativeProposalJobPublic(
                job_id=job.id,
                status=job.status.value,
                review_state=existing.review_state,
                draft_digest=existing.draft_digest,
                prompt_version=existing.prompt_version,
                model_id=existing.model_id,
            ).model_dump(mode="json")
        review = ProposalDraftReview(
            tenant_id=tenant_id,
            workspace_id=payload.workspace_id,
            job_id=job.id,
            prompt_version=assessment.prompt_version,
            model_id=assessment.model_id,
            draft_digest=assessment.draft_digest,
            evidence_map=assessment.evidence_map,
            review_state=assessment.review_state,
        )
        session.add(review)
        session.flush()
        return GenerativeProposalJobPublic(
            job_id=job.id,
            status=job.status.value,
            review_state=review.review_state,
            draft_digest=review.draft_digest,
            prompt_version=review.prompt_version,
            model_id=review.model_id,
        ).model_dump(mode="json")

    return await run_idempotent_mutation(
        request,
        session=session,
        idempotency_key=idempotency_key,
        workspace_id=str(tenant_id),
        operation="proposal-agent:generative-job:create",
        request_payload=payload.model_dump(mode="json"),
        mutation=create_once,
        safe_to_retry_on_failure=True,
    )


@router.post(
    "/tenants/{tenant_id}/grounding-sources",
    status_code=status.HTTP_201_CREATED,
)
async def publish_grounding_source(
    request: Request,
    *,
    session: SessionDep,
    user: CurrentUser,
    tenant_id: uuid.UUID,
    payload: ProposalGroundingSourcePublish,
    idempotency_key: IdempotencyKeyDep,
) -> dict[str, Any]:
    _authorize_agent_admin(session, user, tenant_id)

    def publish_once() -> dict[str, Any]:
        source = ProposalGroundingSource(
            tenant_id=tenant_id,
            workspace_id=payload.workspace_id,
            ecrm_cell_id=payload.ecrm_cell_id,
            client_account_id=payload.client_account_id,
            reference=payload.reference,
            source_version=payload.source_version,
            source_digest=payload.source_digest,
            evidence_receipt_id=payload.evidence_receipt_id,
            allowed_claim_types=sorted(payload.allowed_claim_types),
            allowed_claim_digests=sorted(payload.allowed_claim_digests),
            published_by=user.id,
        )
        session.add(source)
        session.flush()
        append_audit_event_to_session(
            session,
            event_name="proposal_agent.grounding_source.published",
            workspace_id=payload.workspace_id,
            actor_id=user.id,
            actor_role=audit_actor_role(user),
            resource_type="proposal_grounding_source",
            resource_id=str(source.id),
            payload={
                "tenant_id": str(tenant_id),
                "reference": source.reference,
                "source_digest": source.source_digest,
            },
        )
        return {"id": str(source.id), "status": source.status}

    return await run_idempotent_mutation(
        request,
        session=session,
        idempotency_key=idempotency_key,
        workspace_id=str(tenant_id),
        operation="proposal-agent:grounding-source:publish",
        request_payload=payload.model_dump(mode="json"),
        mutation=publish_once,
        safe_to_retry_on_failure=True,
    )


@router.post("/tenants/{tenant_id}/grounding-sources/{source_id}/approve")
async def approve_grounding_source(
    request: Request,
    *,
    session: SessionDep,
    user: CurrentUser,
    tenant_id: uuid.UUID,
    source_id: uuid.UUID,
    payload: ProposalGroundingSourceApproval,
    idempotency_key: IdempotencyKeyDep,
) -> dict[str, Any]:
    _authorize_agent_admin(session, user, tenant_id)

    def approve_once() -> dict[str, Any]:
        source = session.exec(
            select(ProposalGroundingSource)
            .where(
                ProposalGroundingSource.id == source_id,
                ProposalGroundingSource.tenant_id == tenant_id,
                ProposalGroundingSource.workspace_id == payload.workspace_id,
            )
            .with_for_update()
        ).one_or_none()
        if source is None:
            raise HTTPException(status_code=404, detail="Grounding source not found")
        expected = (
            source.ecrm_cell_id,
            source.client_account_id,
            source.source_version,
            source.source_digest,
            source.evidence_receipt_id,
        )
        supplied = (
            payload.ecrm_cell_id,
            payload.client_account_id,
            payload.source_version,
            payload.source_digest,
            payload.evidence_receipt_id,
        )
        if expected != supplied:
            raise HTTPException(
                status_code=409, detail="Source attestation does not match"
            )
        if source.published_by == user.id:
            raise HTTPException(
                status_code=409, detail="Source submitter cannot approve"
            )
        if source.status == "PUBLISHED":
            return {"id": str(source.id), "status": source.status}
        if source.status != "DRAFT":
            raise HTTPException(
                status_code=409, detail="Only draft sources can be approved"
            )
        source.status = "PUBLISHED"
        source.approved_by = user.id
        source.approved_at = datetime.now(timezone.utc)
        session.add(source)
        append_audit_event_to_session(
            session,
            event_name="proposal_agent.grounding_source.approved",
            workspace_id=source.workspace_id,
            actor_id=user.id,
            actor_role=audit_actor_role(user),
            resource_type="proposal_grounding_source",
            resource_id=str(source.id),
            payload={
                "tenant_id": str(tenant_id),
                "ecrm_cell_id": source.ecrm_cell_id,
                "client_account_id": source.client_account_id,
                "source_version": source.source_version,
                "source_digest": source.source_digest,
                "evidence_receipt_id": source.evidence_receipt_id,
            },
        )
        session.flush()
        return {"id": str(source.id), "status": source.status}

    return await run_idempotent_mutation(
        request,
        session=session,
        idempotency_key=idempotency_key,
        workspace_id=str(tenant_id),
        operation=f"proposal-agent:grounding-source:{source_id}:approve",
        request_payload=payload.model_dump(mode="json"),
        mutation=approve_once,
        safe_to_retry_on_failure=True,
    )
