from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from app.domain.lead_discovery.models import (
    DiscoveredLeadRecord,
    DiscoveryProviderType,
    LeadFitBand,
    LeadMatchConfidence,
)
from app.domain.lead_discovery.resolution import (
    canonicalize_domain,
    fuzzy_company_similarity,
    normalize_company_name,
    resolve_lead_entity,
)
from app.domain.lead_discovery.schemas import (
    DiscoveredLeadDTO,
    DiscoverySearchCriteria,
)


def test_canonicalize_domain_handles_variations() -> None:
    assert canonicalize_domain("https://www.acme-corp.com/about/team?ref=1") == "acme-corp.com"
    assert canonicalize_domain("HTTP://APP.STRIPE.COM/") == "stripe.com"
    assert canonicalize_domain("sub.dev.salesforce.com") == "salesforce.com"
    assert canonicalize_domain("  google.co.uk  ") == "google.co.uk"
    assert canonicalize_domain("invalid-domain") == "invalid-domain"


def test_normalize_company_name_removes_corporate_suffixes() -> None:
    assert normalize_company_name("Acme Corporation, Inc.") == "acme"
    assert normalize_company_name("Datadog LLC") == "datadog"
    assert normalize_company_name("Global Payments Limited") == "global payments"
    assert normalize_company_name("SAP SE & Co. KG") == "sap"
    assert normalize_company_name("TechCorp Solutions") == "techcorp solutions"


def test_fuzzy_company_similarity_matches_relevant_names() -> None:
    score1 = fuzzy_company_similarity("Acme Corp", "Acme Inc")
    assert score1 >= 0.9

    score2 = fuzzy_company_similarity("Microsoft", "Micro-Soft Corporation")
    assert score2 >= 0.8

    score3 = fuzzy_company_similarity("Apple", "Google")
    assert score3 < 0.4


def test_resolve_lead_entity_matches_exact_domain() -> None:
    existing_accounts = [
        {"id": "acc-1", "name": "Acme Corp", "domain": "acme.com"},
        {"id": "acc-2", "name": "Beta Technologies", "domain": "betatech.io"},
    ]
    existing_contacts = [
        {"email": "john@acme.com", "account_id": "acc-1"},
    ]

    confidence, match = resolve_lead_entity(
        domain="https://www.acme.com/contact",
        company_name="Acme Inc.",
        existing_accounts=existing_accounts,
        existing_contacts=existing_contacts,
    )

    assert confidence == LeadMatchConfidence.EXACT_MATCH
    assert match is not None
    assert match["id"] == "acc-1"


def test_resolve_lead_entity_flags_fuzzy_and_new_entities() -> None:
    existing_accounts = [
        {"id": "acc-1", "name": "Zenith Cloud Solutions", "domain": "zenithcloud.com"},
    ]

    # Fuzzy match by company name with missing/different subdomain
    conf_fuzzy, match_fuzzy = resolve_lead_entity(
        domain="zenith.ai",
        company_name="Zenith Cloud Solutions LLC",
        existing_accounts=existing_accounts,
        existing_contacts=[],
    )
    assert conf_fuzzy in (LeadMatchConfidence.HIGH_CONFIDENCE_FUZZY, LeadMatchConfidence.AMBIGUOUS_CONFLICT)

    # Brand new entity
    conf_new, match_new = resolve_lead_entity(
        domain="totallynewstartup.io",
        company_name="Totally New Startup",
        existing_accounts=existing_accounts,
        existing_contacts=[],
    )
    assert conf_new == LeadMatchConfidence.NEW_ENTITY
    assert match_new is None


def test_discovered_lead_model_creation() -> None:
    record = DiscoveredLeadRecord(
        id=uuid.uuid4(),
        workspace_id="test-workspace",
        first_name="Elena",
        last_name="Rostova",
        email="elena@cloudscale.io",
        title="VP of Engineering",
        company_name="CloudScale Systems Inc",
        company_domain="cloudscale.io",
        industry="Cloud Infrastructure",
        employee_count=180,
        revenue_range="$20M-$50M",
        country="United States",
        region="California",
        city="San Francisco",
        tech_stack_json=["Kubernetes", "PostgreSQL", "FastAPI"],
        intent_signals_json=["Hiring DevOps", "Expanded to AWS"],
        match_confidence=LeadMatchConfidence.NEW_ENTITY,
        fit_score=88,
        fit_band=LeadFitBand.HOT_OPPORTUNITY,
        score_rationale="High ICP match: target cloud infra industry with >150 headcount and active hiring signals.",
        conversation_starters_json=["Noticed CloudScale is scaling engineering in SF."],
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    assert record.email == "elena@cloudscale.io"
    assert record.fit_band == LeadFitBand.HOT_OPPORTUNITY
    assert "Kubernetes" in record.tech_stack_json


@pytest.mark.anyio
async def test_sandbox_provider_generates_matching_leads() -> None:
    from app.domain.lead_discovery.providers import SandboxDiscoveryProvider

    provider = SandboxDiscoveryProvider()
    criteria = DiscoverySearchCriteria(
        industries=["Fintech"],
        employee_min=50,
        employee_max=500,
        job_titles=["VP of Sales"],
        countries=["United States"],
        tech_stack=["Salesforce"],
        limit=5,
    )

    results = await provider.search_leads("test-ws", criteria)
    assert len(results) == 5
    for lead in results:
        assert lead.workspace_id == "test-ws"
        assert lead.source_provider == DiscoveryProviderType.SANDBOX
        assert lead.industry == "Fintech"
        assert 50 <= (lead.employee_count or 0) <= 500
        assert "VP of Sales" in (lead.title or "")
        assert "Salesforce" in lead.tech_stack


@pytest.mark.anyio
async def test_waterfall_gateway_falls_back_when_primary_fails() -> None:
    from app.domain.lead_discovery.providers import (
        DiscoveryProviderAdapter,
        SandboxDiscoveryProvider,
        WaterfallDiscoveryGateway,
    )
    from app.domain.lead_discovery.schemas import EnrichmentRequest

    class FailingProvider(DiscoveryProviderAdapter):
        @property
        def name(self) -> DiscoveryProviderType:
            return DiscoveryProviderType.APOLLO

        async def search_leads(self, workspace_id: str, criteria: DiscoverySearchCriteria) -> list[DiscoveredLeadDTO]:
            raise RuntimeError("API rate limit exceeded")

        async def enrich_lead(self, request: EnrichmentRequest) -> EnrichmentResponse | None:
            return None

    sandbox = SandboxDiscoveryProvider()
    gateway = WaterfallDiscoveryGateway(providers=[FailingProvider(), sandbox])

    # Search should seamlessly fall back to Sandbox
    results = await gateway.search_leads(
        "test-ws",
        DiscoverySearchCriteria(industries=["Healthcare"], limit=3),
    )
    assert len(results) == 3
    assert results[0].source_provider == DiscoveryProviderType.SANDBOX

    # Enrichment fallback
    enrich_result = await gateway.enrich_lead(EnrichmentRequest(domain="acmecorp.com"))
    assert enrich_result is not None
    assert enrich_result.domain == "acmecorp.com"


def test_ai_lead_scorer_evaluates_four_pillars() -> None:
    from app.domain.lead_discovery.scoring import score_discovered_lead

    lead = DiscoveredLeadDTO(
        id=uuid.uuid4(),
        workspace_id="test-ws",
        first_name="Marcus",
        last_name="Vance",
        email="marcus.vance@apex.io",
        phone="+1-555-0100",
        title="VP of Sales",
        seniority="VP",
        department="Commercial",
        company_name="Apex Nexus",
        company_domain="apex.io",
        industry="Technology & SaaS",
        employee_count=150,
        revenue_range="$25M-$50M",
        country="United States",
        region="California",
        city="San Francisco",
        tech_stack=["Salesforce", "AWS", "HubSpot"],
        intent_signals=[
            "High intent: Searching for outbound automation",
            "Recent hiring surge in sales leadership",
        ],
        source_provider=DiscoveryProviderType.SANDBOX,
        match_confidence=LeadMatchConfidence.NEW_ENTITY,
        fit_score=0,
        fit_band=LeadFitBand.UNQUALIFIED,
        created_at=datetime.now(timezone.utc),
    )

    score_result = score_discovered_lead(
        lead,
        target_industries=["Technology & SaaS"],
        ideal_employee_range=(50, 300),
    )

    # 4 pillars: firmographic + intent + role + completeness
    assert score_result.fit_score >= 80
    assert score_result.fit_band == LeadFitBand.HOT_OPPORTUNITY
    assert len(score_result.contributions) == 4
    pillars = {c.pillar for c in score_result.contributions}
    assert pillars == {"firmographic_fit", "intent_signals", "role_authority", "data_completeness"}
    assert len(score_result.conversation_starters) >= 2
    assert "Apex Nexus" in score_result.rationale


@pytest.mark.anyio
async def test_search_and_persist_leads_in_workspace() -> None:
    from sqlmodel import Session, SQLModel, create_engine
    from app.domain.lead_discovery.service import search_leads_for_workspace
    from app.domain_models import Contact

    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        # Pre-populate one existing contact to test entity resolution
        session.add(
            Contact(
                workspace_id="ws-alpha",
                email="marcus.vance@apexnexus.io",
                first_name="Marcus",
                last_name="Vance",
                company="Apex Nexus",
            )
        )
        session.commit()

        criteria = DiscoverySearchCriteria(
            industries=["Technology & SaaS"],
            limit=3,
        )
        response = await search_leads_for_workspace(
            session,
            workspace_id="ws-alpha",
            criteria=criteria,
        )

        assert response.total == 3
        assert len(response.leads) == 3
        # First lead is apexnexus.io -> should be flagged as EXACT_MATCH because of domain match
        first = response.leads[0]
        assert first.company_domain == "apexnexus.io"
        assert first.match_confidence == LeadMatchConfidence.EXACT_MATCH
        assert first.fit_score > 0
        assert first.fit_band in (LeadFitBand.HOT_OPPORTUNITY, LeadFitBand.HIGH_FIT)


@pytest.mark.anyio
async def test_promote_discovered_lead_creates_crm_contact() -> None:
    from sqlmodel import Session, SQLModel, create_engine
    from app.domain.lead_discovery.schemas import LeadPromotionRequest
    from app.domain.lead_discovery.service import (
        promote_lead_to_contact,
        search_leads_for_workspace,
    )
    from app.domain_models import Contact

    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        search_res = await search_leads_for_workspace(
            session,
            workspace_id="ws-bravo",
            criteria=DiscoverySearchCriteria(limit=2),
        )
        target_lead = search_res.leads[1]

        # Promote lead
        promo_res = promote_lead_to_contact(
            session,
            workspace_id="ws-bravo",
            request=LeadPromotionRequest(
                lead_id=target_lead.id,
                tags=["lead-discovery", "high-fit"],
            ),
        )

        assert promo_res.status == "PROMOTED"
        assert promo_res.contact_id is not None

        # Verify contact created in Contact table
        contact = session.get(Contact, promo_res.contact_id)
        assert contact is not None
        assert contact.email == target_lead.email
        assert contact.company == target_lead.company_name
        assert "lead-discovery" in (contact.tags_json or [])


def test_cross_workspace_promotion_denied() -> None:
    from sqlmodel import Session, SQLModel, create_engine
    from app.domain.lead_discovery.models import DiscoveredLeadRecord
    from app.domain.lead_discovery.schemas import LeadPromotionRequest
    from app.domain.lead_discovery.service import (
        LeadNotFoundError,
        promote_lead_to_contact,
    )

    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        lead_id = uuid.uuid4()
        session.add(
            DiscoveredLeadRecord(
                id=lead_id,
                workspace_id="ws-owner",
                email="owner@test.com",
                company_name="Owner Co",
                company_domain="owner.co",
            )
        )
        session.commit()

        with pytest.raises(LeadNotFoundError):
            promote_lead_to_contact(
                session,
                workspace_id="ws-intruder",
                request=LeadPromotionRequest(lead_id=lead_id),
            )



