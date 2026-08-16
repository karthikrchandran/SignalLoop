from __future__ import annotations

import pytest
from sqlmodel import Session, select

from app.domain.proposal_agent.ecrm_adapter import EcrmProposalApprovalReceipt
from app.domain.proposal_agent.generation import (
    DraftClaim,
    GroundedSource,
    ProposalDraft,
    ProposalGenerationError,
    assess_grounded_draft,
    authorize_email_handoff,
    claim_digest,
)
from app.domain.proposal_agent.models import ProposalGenerationReceipt
from tests.domain.test_proposal_agent import AcceptingAdapter, _context, _session


def _sources() -> list[GroundedSource]:
    return [
        GroundedSource(
            reference="price-book:managed-services:v3",
            digest="a" * 64,
            allowed_claim_types={"PRICE", "DELIVERY_PROMISE"},
            allowed_claim_digests={
                claim_digest(
                    "PRICE",
                    "Managed services are priced at the approved annual amount.",
                )
            },
        ),
        GroundedSource(
            reference="client:ara-global:approved-facts:v2",
            digest="b" * 64,
            allowed_claim_types={"CLIENT_FACT"},
            allowed_claim_digests={
                claim_digest("CLIENT_FACT", "ARA Global is the named client.")
            },
        ),
        GroundedSource(
            reference="clause:confidentiality:v4",
            digest="c" * 64,
            allowed_claim_types={"LEGAL"},
            allowed_claim_digests={
                claim_digest("LEGAL", "Approved confidentiality applies.")
            },
        ),
    ]


def test_grounded_draft_records_prompt_model_and_evidence_map() -> None:
    draft = ProposalDraft(
        prompt_version="proposal-grounded.v1",
        model_id="approved-model-2026-08",
        claims=[
            DraftClaim(
                claim_type="PRICE",
                text="Managed services are priced at the approved annual amount.",
                source_references=["price-book:managed-services:v3"],
            ),
            DraftClaim(
                claim_type="CLIENT_FACT",
                text="ARA Global is the named client.",
                source_references=["client:ara-global:approved-facts:v2"],
            ),
        ],
    )

    result = assess_grounded_draft(draft=draft, sources=_sources())

    assert result.grounded is True
    assert result.review_state == "DRAFT_REVIEW_REQUIRED"
    assert result.prompt_version == draft.prompt_version
    assert result.model_id == draft.model_id
    assert result.evidence_map[0]["source_digest"] == "a" * 64


@pytest.mark.parametrize(
    ("claim_type", "text"),
    [
        ("PRICE", "The price is INR 1,000,000."),
        ("LEGAL", "The agreement includes unlimited indemnity."),
        ("CLIENT_FACT", "The client has 5,000 employees."),
        ("DELIVERY_PROMISE", "Production will launch in seven days."),
        ("COMPLIANCE", "The service is SOC 2 certified."),
    ],
)
def test_invented_commercial_claims_are_rejected(claim_type: str, text: str) -> None:
    draft = ProposalDraft(
        prompt_version="proposal-grounded.v1",
        model_id="approved-model-2026-08",
        claims=[
            DraftClaim(
                claim_type=claim_type,
                text=text,
                source_references=["client:ara-global:approved-facts:v2"],
            )
        ],
    )

    with pytest.raises(ProposalGenerationError, match="not grounded"):
        assess_grounded_draft(draft=draft, sources=_sources())


def test_freeform_content_outside_claim_evidence_is_not_supported() -> None:
    with pytest.raises(ValueError):
        ProposalDraft.model_validate(
            {
                "prompt_version": "proposal-grounded.v1",
                "model_id": "approved-model-2026-08",
                "claims": [],
                "freeform_content": "Invent an attractive guarantee.",
            }
        )


def test_only_exact_ecrm_approved_version_can_route_to_paid_email_agent() -> None:
    with _session() as session:
        proposal_deployment, job = _context(session)
        adapter = AcceptingAdapter()
        from app.domain.proposal_agent.service import run_proposal_batch

        run_proposal_batch(session, adapter=adapter)
        receipt = session.exec(select(ProposalGenerationReceipt)).one()
        email_deployment = _email_dependency(session, proposal_deployment)
        approval = EcrmProposalApprovalReceipt(
            ecrm_cell_id=job.ecrm_cell_id,
            proposal_id=job.proposal_id,
            version_id=receipt.version_id,
            content_digest=receipt.content_digest,
            approval_id="approval-1",
            approved_by="ara-admin",
        )

        handoff = authorize_email_handoff(
            session,
            job=job,
            approval=approval,
            email_deployment_id=email_deployment.id,
        )
        session.commit()
        assert handoff.version_id == receipt.version_id

        with pytest.raises(ProposalGenerationError, match="exact completed version"):
            authorize_email_handoff(
                session,
                job=job,
                approval=approval.model_copy(update={"version_id": "other-version"}),
                email_deployment_id=email_deployment.id,
            )


def _email_dependency(session: Session, proposal_deployment):
    from app.domain.commercial_agents.models import (
        AgentCatalogDefinition,
        AgentDependency,
        AgentDeployment,
        AgentDeploymentStatus,
        AgentType,
    )

    catalog = AgentCatalogDefinition(
        agent_type=AgentType.EMAIL_OUTREACH,
        catalog_version=9_000_001,
        display_name="Email Agent",
        sellable_outcome="Send approved proposal",
        default_capacity_metric="email_recipient",
        default_capacity_amount=5000,
        configuration_schema_version="email.v1",
    )
    session.add(catalog)
    session.flush()
    email = AgentDeployment(
        tenant_id=proposal_deployment.tenant_id,
        installation_id=proposal_deployment.installation_id,
        workspace_id=proposal_deployment.workspace_id,
        catalog_definition_id=catalog.id,
        agent_type=AgentType.EMAIL_OUTREACH,
        name="Proposal delivery email agent",
        status=AgentDeploymentStatus.ACTIVE,
        configuration={},
        configuration_digest="d" * 64,
    )
    session.add(email)
    session.flush()
    session.add(
        AgentDependency(
            tenant_id=proposal_deployment.tenant_id,
            source_deployment_id=proposal_deployment.id,
            target_deployment_id=email.id,
            dependency_type="PROPOSAL_DELIVERY",
        )
    )
    session.commit()
    return email
