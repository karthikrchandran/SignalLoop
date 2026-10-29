import asyncio
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.domain.audit.audit_events import AuditEvent
from app.domain.lead_discovery.models import DiscoveredLeadRecord
from app.domain.lead_discovery.providers import SandboxDiscoveryProvider
from app.domain.lead_discovery.schemas import (
    DiscoverySearchCriteria,
    EnrichmentRequest,
    LeadPromotionRequest,
)
from app.domain.lead_discovery.service import (
    enrich_entity_for_workspace,
    promote_lead_to_contact,
    search_leads_for_workspace,
)


@pytest.mark.parametrize("collision", [False, True])
def test_search_rejects_foreign_workspace_results(db: Session, collision: bool) -> None:
    workspace_id = f"gate-{uuid.uuid4()}"
    criteria = DiscoverySearchCriteria(limit=1)
    lead = asyncio.run(SandboxDiscoveryProvider().search_leads(workspace_id, criteria))[0]
    if collision:
        db.add(DiscoveredLeadRecord(
            id=lead.id,
            workspace_id="foreign-workspace",
            email=lead.email,
            company_name=lead.company_name,
            company_domain=lead.company_domain,
            fit_score=17,
        ))
        db.commit()
    else:
        lead.workspace_id = "foreign-workspace"
    gateway = SimpleNamespace(search_leads=AsyncMock(return_value=[lead]))
    with pytest.raises(ValueError, match="another workspace"):
        asyncio.run(search_leads_for_workspace(
            db, workspace_id=workspace_id, criteria=criteria, gateway=gateway,
        ))
    db.expire_all()
    stored = db.get(DiscoveredLeadRecord, lead.id)
    if collision:
        assert stored is not None
        assert stored.workspace_id == "foreign-workspace"
        assert stored.fit_score == 17
    else:
        assert stored is None


def test_enrichment_records_workspace_audit(db: Session) -> None:
    workspace_id = f"gate-{uuid.uuid4()}"
    result = asyncio.run(enrich_entity_for_workspace(
        db, workspace_id=workspace_id, request=EnrichmentRequest(domain="example.com"),
    ))
    assert result is not None
    event = db.exec(select(AuditEvent).where(
        AuditEvent.workspace_id == workspace_id,
        AuditEvent.event_name == "lead_discovery.enriched",
    )).one()
    assert event.payload == {"found": True}


def test_promotion_records_workspace_audit(db: Session) -> None:
    workspace_id = f"gate-{uuid.uuid4()}"
    result = asyncio.run(search_leads_for_workspace(
        db, workspace_id=workspace_id, criteria=DiscoverySearchCriteria(limit=1),
    ))
    promotion = promote_lead_to_contact(
        db, workspace_id=workspace_id,
        request=LeadPromotionRequest(lead_id=result.leads[0].id),
    )
    event = db.exec(select(AuditEvent).where(
        AuditEvent.workspace_id == workspace_id,
        AuditEvent.event_name == "lead_discovery.promoted",
    )).one()
    assert event.payload["contact_id"] == str(promotion.contact_id)


def test_webhook_requires_authentication(client: TestClient) -> None:
    response = client.post(
        "/api/v1/lead-discovery/webhooks/internal",
        params={"workspace_id": "foreign-workspace"},
        json={"email": "gate@example.com"},
    )
    assert response.status_code == 401


def test_webhook_requires_verified_workspace(
    client: TestClient, superuser_token_headers: dict[str, str],
) -> None:
    response = client.post(
        "/api/v1/lead-discovery/webhooks/internal",
        headers=superuser_token_headers,
        params={"workspace_id": "foreign-workspace"},
        json={"email": "gate@example.com"},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["error"]["code"] == "WORKSPACE_REQUIRED"


def test_webhook_denies_nonmember_workspace(
    client: TestClient, normal_user_token_headers: dict[str, str],
) -> None:
    response = client.post(
        "/api/v1/lead-discovery/webhooks/internal",
        headers={**normal_user_token_headers, "X-Workspace-Id": "foreign-workspace"},
        json={"email": "gate@example.com"},
    )
    assert response.status_code == 403
