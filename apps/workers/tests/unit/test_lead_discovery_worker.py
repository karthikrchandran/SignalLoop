from __future__ import annotations

import uuid
from sqlmodel import Session, SQLModel, create_engine

from app.domain.lead_discovery.models import (
    DiscoveredLeadRecord,
    LeadFitBand,
    LeadMatchConfidence,
)
from app.domain_models import Contact
from worker_app.lead_discovery_worker import process_lead_discovery_batch


def test_process_lead_discovery_batch_resolves_and_scores_leads() -> None:
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        # 1. Existing contact for matching
        session.add(
            Contact(
                workspace_id="ws-test",
                email="director@techcorp.io",
                company="TechCorp Inc",
            )
        )

        # 2. Unscored lead matching domain
        lead1 = DiscoveredLeadRecord(
            id=uuid.uuid4(),
            workspace_id="ws-test",
            first_name="Jane",
            last_name="Doe",
            email="jane.doe@techcorp.io",
            title="VP of Engineering",
            company_name="TechCorp",
            company_domain="techcorp.io",
            industry="Software & Technology",
            employee_count=120,
            revenue_range="$10M-$25M",
            tech_stack_json=["Salesforce", "AWS"],
            intent_signals_json=["Hiring sales leadership", "Expanding outbound automation"],
            fit_score=0,
            fit_band=LeadFitBand.UNQUALIFIED,
        )

        # 3. Unscored lead that is a new entity
        lead2 = DiscoveredLeadRecord(
            id=uuid.uuid4(),
            workspace_id="ws-test",
            first_name="Bob",
            last_name="Smith",
            email="bob@freshventures.com",
            title="Head of Sales",
            company_name="Fresh Ventures",
            company_domain="freshventures.com",
            industry="Venture Capital",
            employee_count=40,
            fit_score=0,
            fit_band=LeadFitBand.UNQUALIFIED,
        )

        session.add_all([lead1, lead2])
        session.commit()

        # Run worker batch
        count = process_lead_discovery_batch(session, limit=10)
        assert count == 2

        # Check results
        updated1 = session.get(DiscoveredLeadRecord, lead1.id)
        assert updated1 is not None
        assert updated1.match_confidence == LeadMatchConfidence.EXACT_MATCH
        assert updated1.fit_score > 0
        assert updated1.fit_band in (LeadFitBand.HOT_OPPORTUNITY, LeadFitBand.HIGH_FIT)
        assert len(updated1.conversation_starters_json) > 0

        updated2 = session.get(DiscoveredLeadRecord, lead2.id)
        assert updated2 is not None
        assert updated2.match_confidence == LeadMatchConfidence.NEW_ENTITY
        assert updated2.fit_score > 0
