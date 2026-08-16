"""Grounded-only generative proposal evaluation contracts."""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlmodel import Session, select

from app.domain.commercial_agents.models import (
    AgentDependency,
    AgentDeployment,
    AgentDeploymentStatus,
    AgentType,
)
from app.domain.proposal_agent.ecrm_adapter import EcrmProposalApprovalReceipt
from app.domain.proposal_agent.models import (
    ProposalEmailHandoff,
    ProposalGenerationJob,
    ProposalGenerationReceipt,
    ProposalJobStatus,
)

ClaimType = Literal[
    "PRICE",
    "LEGAL",
    "CLIENT_FACT",
    "DELIVERY_PROMISE",
    "COMPLIANCE",
    "PRODUCT_FACT",
]


class ProposalGenerationError(ValueError):
    """A generated proposal cannot pass the grounded-draft boundary."""


class GroundedSource(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    reference: str = Field(min_length=1, max_length=255)
    digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    allowed_claim_types: set[ClaimType] = Field(min_length=1)
    allowed_claim_digests: set[str] = Field(min_length=1)


class DraftClaim(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    claim_type: ClaimType
    text: str = Field(min_length=1, max_length=4000)
    source_references: list[str] = Field(min_length=1, max_length=20)

    @field_validator("source_references")
    @classmethod
    def unique_sources(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)) or any(not item.strip() for item in value):
            raise ValueError("claim source references must be unique and nonempty")
        return value


class ProposalDraft(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    prompt_version: str = Field(min_length=1, max_length=128)
    model_id: str = Field(min_length=1, max_length=255)
    claims: list[DraftClaim] = Field(min_length=1, max_length=200)


class ProposalDraftAssessment(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    grounded: bool
    review_state: Literal["DRAFT_REVIEW_REQUIRED"]
    prompt_version: str
    model_id: str
    draft_digest: str
    evidence_map: list[dict[str, str]]


def _digest(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def claim_digest(claim_type: ClaimType, text: str) -> str:
    """Digest an approved atomic claim without trusting model-provided references."""

    return _digest({"claim_type": claim_type, "text": text})


def assess_grounded_draft(
    *, draft: ProposalDraft, sources: list[GroundedSource]
) -> ProposalDraftAssessment:
    """Require every generated commercial assertion to cite an allowed source."""

    source_map = {source.reference: source for source in sources}
    if len(source_map) != len(sources):
        raise ProposalGenerationError("grounding sources must be unique")
    evidence: list[dict[str, str]] = []
    for claim in draft.claims:
        for reference in claim.source_references:
            source = source_map.get(reference)
            approved_digest = claim_digest(claim.claim_type, claim.text)
            if (
                source is None
                or claim.claim_type not in source.allowed_claim_types
                or approved_digest not in source.allowed_claim_digests
            ):
                raise ProposalGenerationError(
                    f"{claim.claim_type} claim is not grounded by an approved source"
                )
            evidence.append(
                {
                    "claim_type": claim.claim_type,
                    "claim_digest": approved_digest,
                    "source_reference": reference,
                    "source_digest": source.digest,
                }
            )
    return ProposalDraftAssessment(
        grounded=True,
        review_state="DRAFT_REVIEW_REQUIRED",
        prompt_version=draft.prompt_version,
        model_id=draft.model_id,
        draft_digest=_digest(draft.model_dump(mode="json")),
        evidence_map=evidence,
    )


def authorize_email_handoff(
    session: Session,
    *,
    job: ProposalGenerationJob,
    approval: EcrmProposalApprovalReceipt,
    email_deployment_id: uuid.UUID,
) -> ProposalEmailHandoff:
    """Authorize only the exact completed and eCRM-approved proposal version."""

    receipt = session.exec(
        select(ProposalGenerationReceipt).where(
            ProposalGenerationReceipt.job_id == job.id,
            ProposalGenerationReceipt.version_id == approval.version_id,
            ProposalGenerationReceipt.content_digest == approval.content_digest,
        )
    ).one_or_none()
    if (
        job.status != ProposalJobStatus.COMPLETED
        or receipt is None
        or approval.ecrm_cell_id != job.ecrm_cell_id
        or approval.proposal_id != job.proposal_id
    ):
        raise ProposalGenerationError(
            "approval must match the exact completed version and eCRM cell"
        )
    email = session.get(AgentDeployment, email_deployment_id)
    dependency = session.exec(
        select(AgentDependency).where(
            AgentDependency.tenant_id == job.tenant_id,
            AgentDependency.source_deployment_id == job.deployment_id,
            AgentDependency.target_deployment_id == email_deployment_id,
            AgentDependency.dependency_type == "PROPOSAL_DELIVERY",
            AgentDependency.status == "ACTIVE",
        )
    ).one_or_none()
    if (
        email is None
        or email.tenant_id != job.tenant_id
        or email.workspace_id != job.workspace_id
        or email.agent_type != AgentType.EMAIL_OUTREACH
        or email.status != AgentDeploymentStatus.ACTIVE
        or dependency is None
    ):
        raise ProposalGenerationError(
            "an active paid Email Agent dependency is required"
        )
    existing = session.exec(
        select(ProposalEmailHandoff).where(
            ProposalEmailHandoff.job_id == job.id,
            ProposalEmailHandoff.version_id == approval.version_id,
        )
    ).one_or_none()
    if existing is not None:
        if (
            existing.email_deployment_id != email_deployment_id
            or existing.approval_id != approval.approval_id
        ):
            raise ProposalGenerationError(
                "proposal handoff already has another approval"
            )
        return existing
    handoff = ProposalEmailHandoff(
        tenant_id=job.tenant_id,
        workspace_id=job.workspace_id,
        job_id=job.id,
        email_deployment_id=email_deployment_id,
        version_id=approval.version_id,
        content_digest=approval.content_digest,
        approval_id=approval.approval_id,
        approved_by=approval.approved_by,
    )
    session.add(handoff)
    session.flush()
    return handoff
