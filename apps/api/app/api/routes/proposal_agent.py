"""Tenant-scoped governed Proposal Agent endpoints."""

from __future__ import annotations

import hashlib
import json
import uuid
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
from app.domain.proposal_agent.service import enqueue_proposal_job

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
    reference: str = Field(min_length=1, max_length=255)
    source_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
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


class GenerativeProposalJobPublic(BaseModel):
    job_id: uuid.UUID
    status: str
    review_state: str
    draft_digest: str
    prompt_version: str
    model_id: str


def _digest(value: object) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


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
            ProposalGroundingSource.reference.in_(payload.source_references),
            ProposalGroundingSource.status == "PUBLISHED",
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
            reference=payload.reference,
            source_digest=payload.source_digest,
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
