"""Lead Discovery and AI Enrichment service layer."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlmodel import Session, select

from app.domain.audit.audit_events import append_audit_event_to_session
from app.domain.lead_discovery.models import (
    DiscoveredLeadRecord,
    DiscoveryProviderType,
    DiscoverySearchQueryLog,
    utc_now,
)
from app.domain.lead_discovery.providers import (
    WaterfallDiscoveryGateway,
)
from app.domain.lead_discovery.resolution import resolve_lead_entity
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
from app.domain.lead_discovery.scoring import score_discovered_lead
from app.domain_models import Contact

logger = logging.getLogger(__name__)


class LeadNotFoundError(Exception):
    """Raised when the requested discovered lead is not found in the workspace."""


class LeadAlreadyPromotedError(Exception):
    """Raised when attempting to re-promote an already promoted lead."""


def _lead_to_dto(record: DiscoveredLeadRecord) -> DiscoveredLeadDTO:
    return DiscoveredLeadDTO(
        id=record.id,
        workspace_id=record.workspace_id,
        first_name=record.first_name,
        last_name=record.last_name,
        email=record.email,
        phone=record.phone,
        title=record.title,
        seniority=record.seniority,
        department=record.department,
        company_name=record.company_name,
        company_domain=record.company_domain,
        industry=record.industry,
        employee_count=record.employee_count,
        revenue_range=record.revenue_range,
        country=record.country,
        region=record.region,
        city=record.city,
        tech_stack=list(record.tech_stack_json or []),
        intent_signals=list(record.intent_signals_json or []),
        source_provider=record.source_provider,
        match_confidence=record.match_confidence,
        matched_account_id=record.matched_account_id,
        fit_score=record.fit_score,
        fit_band=record.fit_band,
        score_rationale=record.score_rationale,
        conversation_starters=list(record.conversation_starters_json or []),
        is_promoted=record.is_promoted,
        promoted_contact_id=record.promoted_contact_id,
        created_at=record.created_at,
    )


async def search_leads_for_workspace(
    session: Session,
    *,
    workspace_id: str,
    criteria: DiscoverySearchCriteria,
    gateway: WaterfallDiscoveryGateway | None = None,
) -> DiscoverySearchResponse:
    """Discover, resolve, score, and persist high-fit prospects for a workspace."""
    gw = gateway or WaterfallDiscoveryGateway()

    # 1. Gather existing workspace CRM context for entity resolution
    try:
        existing_contacts = session.exec(
            select(Contact).where(Contact.workspace_id == workspace_id)
        ).all()
    except Exception:
        existing_contacts = []

    accounts_data: list[dict[str, Any]] = []
    contacts_data: list[dict[str, Any]] = []

    for c in existing_contacts:
        domain = c.email.split("@", 1)[1] if "@" in c.email else None
        contacts_data.append({"email": c.email, "account_id": getattr(c, "shared_account_id", None)})
        if c.company and domain:
            accounts_data.append({
                "id": str(getattr(c, "shared_account_id", None) or ""),
                "name": c.company,
                "domain": domain,
            })

    # 2. Query discovery gateway
    leads_raw = await gw.search_leads(workspace_id, criteria)

    for lead_dto in leads_raw:
        if lead_dto.workspace_id != workspace_id:
            raise ValueError("Discovery provider returned a lead for another workspace")
        existing = session.get(DiscoveredLeadRecord, lead_dto.id)
        if existing is not None and existing.workspace_id != workspace_id:
            raise ValueError("Discovery provider returned an ID belonging to another workspace")

    processed_leads: list[DiscoveredLeadDTO] = []
    for lead_dto in leads_raw:
        # 3. Entity resolution vs CRM
        confidence, match = resolve_lead_entity(
            domain=lead_dto.company_domain,
            company_name=lead_dto.company_name,
            existing_accounts=accounts_data,
            existing_contacts=contacts_data,
        )
        lead_dto.match_confidence = confidence
        if match:
            lead_dto.matched_account_id = str(match.get("id") or "")

        # 4. Internal AI Multi-Dimensional Scoring
        scoring_res = score_discovered_lead(
            lead_dto,
            target_industries=criteria.industries,
            ideal_employee_range=(criteria.employee_min or 50, criteria.employee_max or 500),
        )
        lead_dto.fit_score = scoring_res.fit_score
        lead_dto.fit_band = scoring_res.fit_band
        lead_dto.score_rationale = scoring_res.rationale
        lead_dto.conversation_starters = scoring_res.conversation_starters

        # 5. Upsert to DiscoveredLeadRecord in DB
        existing_rec = session.exec(
            select(DiscoveredLeadRecord).where(
                DiscoveredLeadRecord.id == lead_dto.id,
                DiscoveredLeadRecord.workspace_id == workspace_id,
            )
        ).first()
        if not existing_rec:
            existing_rec = session.exec(
                select(DiscoveredLeadRecord).where(
                    DiscoveredLeadRecord.workspace_id == workspace_id,
                    DiscoveredLeadRecord.email == lead_dto.email,
                )
            ).first()

        if existing_rec:
            existing_rec.fit_score = lead_dto.fit_score
            existing_rec.fit_band = lead_dto.fit_band
            existing_rec.score_rationale = lead_dto.score_rationale
            existing_rec.conversation_starters_json = lead_dto.conversation_starters
            existing_rec.match_confidence = lead_dto.match_confidence
            existing_rec.matched_account_id = lead_dto.matched_account_id
            existing_rec.updated_at = utc_now()
            session.add(existing_rec)
        else:
            rec = DiscoveredLeadRecord(
                id=lead_dto.id,
                workspace_id=workspace_id,
                first_name=lead_dto.first_name,
                last_name=lead_dto.last_name,
                email=lead_dto.email,
                phone=lead_dto.phone,
                title=lead_dto.title,
                seniority=lead_dto.seniority,
                department=lead_dto.department,
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
                matched_account_id=lead_dto.matched_account_id,
                fit_score=lead_dto.fit_score,
                fit_band=lead_dto.fit_band,
                score_rationale=lead_dto.score_rationale,
                conversation_starters_json=lead_dto.conversation_starters,
                is_promoted=False,
            )
            session.add(rec)

        processed_leads.append(lead_dto)

    # 6. Log query
    query_log = DiscoverySearchQueryLog(
        workspace_id=workspace_id,
        criteria_json=criteria.model_dump(),
        results_count=len(processed_leads),
        provider_used=processed_leads[0].source_provider if processed_leads else DiscoveryProviderType.SANDBOX,
    )
    session.add(query_log)
    session.commit()

    return DiscoverySearchResponse(
        total=len(processed_leads),
        leads=processed_leads,
        provider_used=query_log.provider_used,
        criteria=criteria,
    )


async def enrich_entity_for_workspace(
    session: Session,
    *,
    workspace_id: str,
    request: EnrichmentRequest,
    gateway: WaterfallDiscoveryGateway | None = None,
) -> EnrichmentResponse | None:
    """Enrich entity via waterfall provider gateway."""
    gw = gateway or WaterfallDiscoveryGateway()
    result = await gw.enrich_lead(request)
    append_audit_event_to_session(
        session,
        event_name="lead_discovery.enriched",
        workspace_id=workspace_id,
        payload={"found": result is not None},
    )
    session.commit()
    return result


def score_lead_for_workspace(
    session: Session,
    *,
    workspace_id: str,
    lead_id: uuid.UUID,
    target_industries: list[str] | None = None,
    ideal_employee_range: tuple[int, int] | None = None,
) -> LeadScoringResponse:
    """Recalculate AI score and opportunity brief for a stored discovered lead."""
    lead = session.exec(
        select(DiscoveredLeadRecord).where(
            DiscoveredLeadRecord.id == lead_id,
            DiscoveredLeadRecord.workspace_id == workspace_id,
        )
    ).first()
    if not lead:
        raise LeadNotFoundError(f"Discovered lead {lead_id} not found in workspace {workspace_id}")

    dto = _lead_to_dto(lead)
    target_inds = target_industries or ([lead.industry] if lead.industry else None)
    return score_discovered_lead(
        dto,
        target_industries=target_inds,
        ideal_employee_range=ideal_employee_range,
    )


def promote_lead_to_contact(
    session: Session,
    *,
    workspace_id: str,
    request: LeadPromotionRequest,
) -> LeadPromotionResponse:
    """Promote a discovered lead into workspace CRM Contact and optionally enroll in sequence."""
    lead = session.exec(
        select(DiscoveredLeadRecord).where(
            DiscoveredLeadRecord.id == request.lead_id,
            DiscoveredLeadRecord.workspace_id == workspace_id,
        )
    ).first()
    if not lead:
        raise LeadNotFoundError(f"Discovered lead {request.lead_id} not found in workspace {workspace_id}")

    # Check if contact already exists
    contact = session.exec(
        select(Contact).where(
            Contact.workspace_id == workspace_id,
            Contact.email == lead.email,
        )
    ).first()

    assigned_tags = list(request.tags) if request.tags else ["discovered-lead", "ai-qualified"]

    if not contact:
        contact = Contact(
            workspace_id=workspace_id,
            email=lead.email,
            first_name=lead.first_name,
            last_name=lead.last_name,
            company=lead.company_name,
            phone=lead.phone,
            source_channel="lead-discovery",
            tags_json=assigned_tags,
            intent_json=list(lead.intent_signals_json or []),
        )
        session.add(contact)
        session.flush()
    else:
        # Merge tags
        current_tags = set(contact.tags_json or [])
        current_tags.update(assigned_tags)
        contact.tags_json = list(current_tags)
        session.add(contact)
        session.flush()

    lead.is_promoted = True
    lead.promoted_contact_id = contact.id
    lead.promoted_at = utc_now()
    session.add(lead)

    append_audit_event_to_session(
        session=session,
        workspace_id=workspace_id,
        event_name="lead_discovery.promoted",
        payload={
            "lead_id": str(lead.id),
            "contact_id": str(contact.id),
            "fit_score": lead.fit_score,
        },
    )

    session.commit()

    return LeadPromotionResponse(
        lead_id=lead.id,
        contact_id=contact.id,
        workspace_id=workspace_id,
        enrolled_campaign_id=request.campaign_id,
        enrolled_sequence_id=request.sequence_id,
        status="PROMOTED",
        message="Discovered lead successfully promoted to CRM contact.",
    )
