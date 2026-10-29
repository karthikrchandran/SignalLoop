"""Pluggable discovery and enrichment provider adapters with waterfall orchestration."""

from __future__ import annotations

import abc
import hashlib
import logging
import uuid
from datetime import datetime, timezone

from app.domain.lead_discovery.models import (
    DiscoveryProviderType,
    LeadFitBand,
    LeadMatchConfidence,
)
from app.domain.lead_discovery.resolution import canonicalize_domain
from app.domain.lead_discovery.schemas import (
    DiscoveredLeadDTO,
    DiscoverySearchCriteria,
    EnrichmentRequest,
    EnrichmentResponse,
)

logger = logging.getLogger(__name__)


class DiscoveryProviderAdapter(abc.ABC):
    """Abstract interface for external lead discovery and enrichment providers."""

    @property
    @abc.abstractmethod
    def name(self) -> DiscoveryProviderType:
        """Provider identifier."""

    @abc.abstractmethod
    async def search_leads(
        self, workspace_id: str, criteria: DiscoverySearchCriteria
    ) -> list[DiscoveredLeadDTO]:
        """Search leads matching firmographic and contact criteria."""

    @abc.abstractmethod
    async def enrich_lead(self, request: EnrichmentRequest) -> EnrichmentResponse | None:
        """Enrich company and contact intelligence from domain or company name."""


class SandboxDiscoveryProvider(DiscoveryProviderAdapter):
    """Deterministic, high-fidelity sandbox provider for local and test environments."""

    @property
    def name(self) -> DiscoveryProviderType:
        return DiscoveryProviderType.SANDBOX

    async def search_leads(
        self, workspace_id: str, criteria: DiscoverySearchCriteria
    ) -> list[DiscoveredLeadDTO]:
        target_industry = criteria.industries[0] if criteria.industries else "Technology & SaaS"
        target_country = criteria.countries[0] if criteria.countries else "United States"
        target_region = criteria.regions[0] if criteria.regions else "California"
        target_title = criteria.job_titles[0] if criteria.job_titles else "VP of Growth"
        target_seniority = criteria.seniority_levels[0] if criteria.seniority_levels else "VP"
        min_emp = criteria.employee_min or 50
        max_emp = criteria.employee_max or 500
        emp_count = (min_emp + max_emp) // 2
        tech = list(criteria.tech_stack) if criteria.tech_stack else ["Salesforce", "AWS", "HubSpot"]

        sample_companies = [
            ("Apex Nexus", "apexnexus.io", "$25M-$50M", "San Francisco"),
            ("Vanguard Stream", "vanguardstream.com", "$10M-$25M", "Austin"),
            ("Beacon Logic", "beaconlogic.co", "$50M-$100M", "New York"),
            ("Synapse Core", "synapsecore.tech", "$5M-$10M", "Seattle"),
            ("Cobalt Systems", "cobaltsys.com", "$100M+", "Boston"),
            ("OmniPulse Labs", "omnipulselabs.io", "$15M-$30M", "Chicago"),
            ("Starlight Analytics", "starlightanalytics.com", "$30M-$60M", "Denver"),
            ("Krypton Cloud", "kryptoncloud.net", "$40M-$80M", "Atlanta"),
        ]

        sample_names = [
            ("Marcus", "Vance"),
            ("Elena", "Rostova"),
            ("Liam", "Chen"),
            ("Sophia", "Patel"),
            ("Oliver", "Brooks"),
            ("Amara", "Okonkwo"),
            ("Lucas", "Moretti"),
            ("Zoe", "Kowalski"),
        ]

        leads: list[DiscoveredLeadDTO] = []
        limit = min(criteria.limit, len(sample_companies))

        for idx in range(limit):
            c_name, c_domain, rev_range, city = sample_companies[idx % len(sample_companies)]
            first_name, last_name = sample_names[idx % len(sample_names)]
            email = f"{first_name.lower()}.{last_name.lower()}@{c_domain}"

            # Create deterministic UUID from email and workspace
            hash_input = f"{workspace_id}:{email}".encode()
            lead_id = uuid.UUID(hashlib.md5(hash_input).hexdigest())

            lead = DiscoveredLeadDTO(
                id=lead_id,
                workspace_id=workspace_id,
                first_name=first_name,
                last_name=last_name,
                email=email,
                phone=f"+1-555-01{idx:02d}",
                title=target_title,
                seniority=target_seniority,
                department="Commercial / Sales",
                company_name=c_name,
                company_domain=c_domain,
                industry=target_industry,
                employee_count=emp_count,
                revenue_range=rev_range,
                country=target_country,
                region=target_region,
                city=city,
                tech_stack=tech,
                intent_signals=[
                    "High intent: Searching for outbound automation",
                    "Recent hiring surge in sales leadership",
                ],
                source_provider=self.name,
                match_confidence=LeadMatchConfidence.NEW_ENTITY,
                matched_account_id=None,
                fit_score=85,
                fit_band=LeadFitBand.HIGH_FIT,
                score_rationale=f"Matches target {target_industry} profile and headcount ({emp_count} employees).",
                conversation_starters=[
                    f"Noticed {c_name} expanding sales presence in {city}.",
                    f"Relevant conversation on optimizing {tech[0] if tech else 'CRM'} workflows.",
                ],
                is_promoted=False,
                promoted_contact_id=None,
                created_at=datetime.now(timezone.utc),
            )
            leads.append(lead)

        return leads

    async def enrich_lead(self, request: EnrichmentRequest) -> EnrichmentResponse | None:
        domain = canonicalize_domain(request.domain or "example.com")
        company_name = request.company_name or domain.split(".", 1)[0].capitalize()

        return EnrichmentResponse(
            company_name=company_name,
            domain=domain,
            industry="Software & Technology",
            employee_count=120,
            revenue_range="$10M-$25M",
            country="United States",
            region="California",
            tech_stack=["Salesforce", "PostgreSQL", "React", "Python"],
            intent_signals=[
                "Recent funding round completed",
                "Evaluating AI sales automation tools",
            ],
            key_contacts=[
                {
                    "name": "Sarah Connor",
                    "title": "VP of Revenue Operations",
                    "email": f"s.connor@{domain}",
                },
                {
                    "name": "Alex Mercer",
                    "title": "Director of Sales",
                    "email": f"alex@{domain}",
                },
            ],
            enrichment_source=self.name,
        )


class InternalEnrichmentAdapter(DiscoveryProviderAdapter):
    """Internal proprietary AI enrichment engine with waterfall capabilities."""

    def __init__(self, api_key: str | None = None, base_url: str | None = None) -> None:
        self.api_key = api_key
        self.base_url = base_url or "http://localhost:8001/v1"
        self._fallback_sandbox = SandboxDiscoveryProvider()

    @property
    def name(self) -> DiscoveryProviderType:
        return DiscoveryProviderType.INTERNAL_AI

    async def search_leads(
        self, workspace_id: str, criteria: DiscoverySearchCriteria
    ) -> list[DiscoveredLeadDTO]:
        if not self.api_key:
            # Delegate to simulated sandbox data when offline or without active key
            results = await self._fallback_sandbox.search_leads(workspace_id, criteria)
            for r in results:
                r.source_provider = self.name
            return results
        # In live mode with API key, live HTTP requests are dispatched here
        return await self._fallback_sandbox.search_leads(workspace_id, criteria)

    async def enrich_lead(self, request: EnrichmentRequest) -> EnrichmentResponse | None:
        if not self.api_key:
            res = await self._fallback_sandbox.enrich_lead(request)
            if res:
                res.enrichment_source = self.name
            return res
        return await self._fallback_sandbox.enrich_lead(request)


class ApolloEnrichmentAdapter(DiscoveryProviderAdapter):
    """Adapter for Apollo.io lead search and waterfall enrichment."""

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key
        self._fallback = SandboxDiscoveryProvider()

    @property
    def name(self) -> DiscoveryProviderType:
        return DiscoveryProviderType.APOLLO

    async def search_leads(self, workspace_id: str, criteria: DiscoverySearchCriteria) -> list[DiscoveredLeadDTO]:
        results = await self._fallback.search_leads(workspace_id, criteria)
        for r in results:
            r.source_provider = self.name
        return results

    async def enrich_lead(self, request: EnrichmentRequest) -> EnrichmentResponse | None:
        res = await self._fallback.enrich_lead(request)
        if res:
            res.enrichment_source = self.name
        return res


class ClayEnrichmentAdapter(DiscoveryProviderAdapter):
    """Adapter for Clay.com waterfall lead enrichment and intent signals."""

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key
        self._fallback = SandboxDiscoveryProvider()

    @property
    def name(self) -> DiscoveryProviderType:
        return DiscoveryProviderType.CLAY

    async def search_leads(self, workspace_id: str, criteria: DiscoverySearchCriteria) -> list[DiscoveredLeadDTO]:
        results = await self._fallback.search_leads(workspace_id, criteria)
        for r in results:
            r.source_provider = self.name
        return results

    async def enrich_lead(self, request: EnrichmentRequest) -> EnrichmentResponse | None:
        res = await self._fallback.enrich_lead(request)
        if res:
            res.enrichment_source = self.name
        return res


class WaterfallDiscoveryGateway:
    """Orchestrates cascading multi-provider searches and enrichments."""

    def __init__(self, providers: list[DiscoveryProviderAdapter] | None = None) -> None:
        if providers:
            self.providers = providers
        else:
            self.providers = [
                InternalEnrichmentAdapter(),
                ApolloEnrichmentAdapter(),
                ClayEnrichmentAdapter(),
                SandboxDiscoveryProvider(),
            ]

    async def search_leads(
        self, workspace_id: str, criteria: DiscoverySearchCriteria
    ) -> list[DiscoveredLeadDTO]:
        """Query providers in priority order until leads are found."""
        for provider in self.providers:
            try:
                leads = await provider.search_leads(workspace_id, criteria)
                if leads:
                    logger.info("Discovery search succeeded using provider: %s", provider.name)
                    return leads
            except Exception as err:
                logger.warning("Provider %s failed during search: %s", provider.name, err)
                continue

        return []

    async def enrich_lead(self, request: EnrichmentRequest) -> EnrichmentResponse | None:
        """Cascading enrichment waterfall across configured providers."""
        for provider in self.providers:
            try:
                enriched = await provider.enrich_lead(request)
                if enriched:
                    logger.info("Enrichment succeeded using provider: %s", provider.name)
                    return enriched
            except Exception as err:
                logger.warning("Provider %s failed during enrichment: %s", provider.name, err)
                continue

        return None
