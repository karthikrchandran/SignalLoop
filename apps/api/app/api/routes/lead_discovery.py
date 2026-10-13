"""HTTP API routes for Lead Discovery and AI Enrichment."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import CurrentUser, SessionDep, require_admin
from app.api.request_context import WorkspaceIdDep
from app.domain.lead_discovery.models import (
    DiscoveredLeadRecord,
    DiscoveryProviderType,
    LeadFitBand,
    LeadMatchConfidence,
)
from app.domain.lead_discovery.scoring import score_discovered_lead
from app.domain.lead_discovery.schemas import (
    DiscoveredLeadDTO,
    DiscoverySearchCriteria,
    DiscoverySearchResponse,
    EnrichmentRequest,
    EnrichmentResponse,
    LeadPromotionRequest,
    LeadPromotionResponse,
    LeadScoringResponse,
)
from app.domain.lead_discovery.service import (
    LeadNotFoundError,
    enrich_entity_for_workspace,
    promote_lead_to_contact,
    score_lead_for_workspace,
    search_leads_for_workspace,
)

router = APIRouter(prefix="/lead-discovery", tags=["lead-discovery"])


@router.post(
    "/search",
    response_model=DiscoverySearchResponse,
    dependencies=[Depends(require_admin)],
)
async def search_discovered_leads(
    *,
    session: SessionDep,
    workspace_id: WorkspaceIdDep,
    current_user: CurrentUser,
    criteria: DiscoverySearchCriteria,
) -> DiscoverySearchResponse:
    """Search, resolve, and AI-score leads based on firmographic and contact parameters."""
    return await search_leads_for_workspace(
        session,
        workspace_id=workspace_id,
        criteria=criteria,
    )


@router.post(
    "/enrich",
    response_model=EnrichmentResponse,
    dependencies=[Depends(require_admin)],
)
async def enrich_lead_entity(
    *,
    session: SessionDep,
    workspace_id: WorkspaceIdDep,
    current_user: CurrentUser,
    request: EnrichmentRequest,
) -> EnrichmentResponse:
    """Enrich company firmographics, tech stack, and verified contacts via waterfall engine."""
    res = await enrich_entity_for_workspace(
        session,
        workspace_id=workspace_id,
        request=request,
    )
    if not res:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Enrichment intelligence not found for requested target",
        )
    return res


@router.post(
    "/score/{lead_id}",
    response_model=LeadScoringResponse,
    dependencies=[Depends(require_admin)],
)
def score_lead(
    *,
    session: SessionDep,
    workspace_id: WorkspaceIdDep,
    current_user: CurrentUser,
    lead_id: uuid.UUID,
) -> LeadScoringResponse:
    """Compute AI fit scoring breakdown and synthesized sales conversation starters."""
    try:
        return score_lead_for_workspace(
            session,
            workspace_id=workspace_id,
            lead_id=lead_id,
        )
    except LeadNotFoundError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(err),
        ) from err


@router.post(
    "/promote",
    response_model=LeadPromotionResponse,
    dependencies=[Depends(require_admin)],
)
def promote_lead(
    *,
    session: SessionDep,
    workspace_id: WorkspaceIdDep,
    current_user: CurrentUser,
    request: LeadPromotionRequest,
) -> LeadPromotionResponse:
    """Promote a discovered lead into the workspace CRM contacts with sequence enrollment."""
    try:
        return promote_lead_to_contact(
            session,
            workspace_id=workspace_id,
            request=request,
        )
    except LeadNotFoundError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(err),
        ) from err


@router.post(
    "/webhooks/{provider}",
    response_model=dict,
)
async def ingest_lead_webhook(
    *,
    session: SessionDep,
    provider: str,
    payload: dict,
    workspace_id: str = Query(..., description="Target workspace ID for incoming lead"),
) -> dict:
    """Ingest external lead discovery webhook (e.g. from internal pipelines or Apollo)."""
    email = payload.get("email")
    if not email or "@" not in email:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Valid email is required in webhook payload",
        )

    company_domain = payload.get("domain") or email.split("@", 1)[1]
    company_name = payload.get("company_name") or company_domain.split(".", 1)[0].capitalize()

    lead_dto = DiscoveredLeadDTO(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        first_name=payload.get("first_name", ""),
        last_name=payload.get("last_name", ""),
        email=email,
        phone=payload.get("phone"),
        title=payload.get("title"),
        seniority=payload.get("seniority"),
        company_name=company_name,
        company_domain=company_domain,
        industry=payload.get("industry"),
        employee_count=payload.get("employee_count"),
        revenue_range=payload.get("revenue_range"),
        country=payload.get("country"),
        region=payload.get("region"),
        tech_stack=payload.get("tech_stack", []),
        intent_signals=payload.get("intent_signals", []),
        source_provider=DiscoveryProviderType.INTERNAL_AI if "internal" in provider.lower() else DiscoveryProviderType.SANDBOX,
        match_confidence=LeadMatchConfidence.NEW_ENTITY,
        fit_score=0,
        fit_band=LeadFitBand.UNQUALIFIED,
        created_at=datetime.now(timezone.utc),
    )

    scoring_res = score_discovered_lead(lead_dto)
    lead_dto.fit_score = scoring_res.fit_score
    lead_dto.fit_band = scoring_res.fit_band
    lead_dto.score_rationale = scoring_res.rationale
    lead_dto.conversation_starters = scoring_res.conversation_starters

    rec = DiscoveredLeadRecord(
        id=lead_dto.id,
        workspace_id=workspace_id,
        first_name=lead_dto.first_name,
        last_name=lead_dto.last_name,
        email=lead_dto.email,
        phone=lead_dto.phone,
        title=lead_dto.title,
        seniority=lead_dto.seniority,
        company_name=lead_dto.company_name,
        company_domain=lead_dto.company_domain,
        industry=lead_dto.industry,
        employee_count=lead_dto.employee_count,
        revenue_range=lead_dto.revenue_range,
        country=lead_dto.country,
        region=lead_dto.region,
        city=lead_dto.city,
        tech_stack_json=lead_dto.tech_stack,
        intent_signals_json=lead_dto.intent_signals,
        source_provider=lead_dto.source_provider,
        match_confidence=lead_dto.match_confidence,
        fit_score=lead_dto.fit_score,
        fit_band=lead_dto.fit_band,
        score_rationale=lead_dto.score_rationale,
        conversation_starters_json=lead_dto.conversation_starters,
        is_promoted=False,
    )
    session.add(rec)
    session.commit()

    return {
        "status": "ACCEPTED",
        "lead_id": str(rec.id),
        "fit_score": rec.fit_score,
        "fit_band": rec.fit_band.value,
    }


@router.get(
    "/providers",
    response_model=list[str],
    dependencies=[Depends(require_admin)],
)
def list_available_providers(
    *,
    current_user: CurrentUser,
) -> list[str]:
    """List configured and supported discovery / enrichment provider adapters."""
    return [p.value for p in DiscoveryProviderType]
