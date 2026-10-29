from __future__ import annotations

import uuid
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.api.deps import get_current_user, get_db
from app.api.routes import lead_discovery
from app.domain.lead_discovery.models import (
    DiscoveredLeadRecord,
    DiscoveryProviderType,
    LeadFitBand,
    LeadMatchConfidence,
)
from app.domain_models import Contact
from app.models import User


def _sqlite_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def _admin_user() -> User:
    return User(
        email="admin@example.com",
        hashed_password="not-used",
        is_superuser=True,
        role="admin",
    )


def _lead_discovery_app(session: Session, user: User | None = None) -> FastAPI:
    app = FastAPI()
    app.include_router(lead_discovery.router)

    def override_get_db() -> Session:
        return session

    app.dependency_overrides[get_db] = override_get_db

    admin = user or _admin_user()

    def override_get_current_user() -> User:
        return admin

    app.dependency_overrides[get_current_user] = override_get_current_user
    return app


def test_list_discovery_providers_route() -> None:
    session = _sqlite_session()
    app = _lead_discovery_app(session)
    client = TestClient(app)

    response = client.get("/lead-discovery/providers")
    assert response.status_code == 200
    providers = response.json()
    assert "SANDBOX" in providers
    assert "INTERNAL_AI" in providers


def test_search_and_score_leads_route() -> None:
    session = _sqlite_session()
    app = _lead_discovery_app(session)
    client = TestClient(app)

    search_payload = {
        "industries": ["Fintech"],
        "employee_min": 50,
        "employee_max": 250,
        "job_titles": ["VP of Sales"],
        "countries": ["United States"],
        "limit": 3,
    }
    response = client.post(
        "/lead-discovery/search",
        headers={"X-Workspace-Id": "ws-fintech"},
        json=search_payload,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3
    assert len(data["leads"]) == 3

    lead = data["leads"][0]
    assert lead["workspace_id"] == "ws-fintech"
    assert lead["fit_score"] > 0
    assert len(lead["conversation_starters"]) > 0

    # Test score route
    score_resp = client.post(
        f"/lead-discovery/score/{lead['id']}",
        headers={"X-Workspace-Id": "ws-fintech"},
    )
    assert score_resp.status_code == 200
    score_data = score_resp.json()
    assert score_data["fit_score"] >= 80
    assert score_data["fit_band"] == lead["fit_band"]
    assert len(score_data["contributions"]) == 4


def test_enrich_lead_entity_route() -> None:
    session = _sqlite_session()
    app = _lead_discovery_app(session)
    client = TestClient(app)

    enrich_payload = {
        "domain": "stripe.com",
        "company_name": "Stripe Inc",
    }
    response = client.post(
        "/lead-discovery/enrich",
        headers={"X-Workspace-Id": "ws-enrich"},
        json=enrich_payload,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["domain"] == "stripe.com"
    assert len(data["tech_stack"]) > 0
    assert len(data["key_contacts"]) > 0


def test_promote_lead_route() -> None:
    session = _sqlite_session()
    app = _lead_discovery_app(session)
    client = TestClient(app)

    # First perform search to create a lead
    search_response = client.post(
        "/lead-discovery/search",
        headers={"X-Workspace-Id": "ws-promo"},
        json={"industries": ["Healthcare"], "limit": 1},
    )
    assert search_response.status_code == 200
    lead = search_response.json()["leads"][0]

    # Promote the lead
    promote_payload = {
        "lead_id": lead["id"],
        "tags": ["healthcare-priority", "q4-pipeline"],
    }
    promo_response = client.post(
        "/lead-discovery/promote",
        headers={"X-Workspace-Id": "ws-promo"},
        json=promote_payload,
    )
    assert promo_response.status_code == 200
    promo_data = promo_response.json()
    assert promo_data["status"] == "PROMOTED"
    assert promo_data["contact_id"] is not None

    # Verify contact in DB
    contact = session.get(Contact, uuid.UUID(promo_data["contact_id"]))
    assert contact is not None
    assert contact.email == lead["email"]
    assert "healthcare-priority" in (contact.tags_json or [])


def test_lead_discovery_webhook_ingestion_route() -> None:
    session = _sqlite_session()
    app = _lead_discovery_app(session)
    client = TestClient(app)

    webhook_payload = {
        "email": "sarah.lead@innovate.tech",
        "first_name": "Sarah",
        "last_name": "Connor",
        "title": "VP of Revenue Operations",
        "company_name": "Innovate Tech",
        "domain": "innovate.tech",
        "industry": "Software & Technology",
        "employee_count": 150,
        "revenue_range": "$20M-$50M",
        "tech_stack": ["Salesforce", "FastAPI"],
        "intent_signals": ["Evaluating outbound automation platforms", "Active hiring"],
    }

    response = client.post(
        "/lead-discovery/webhooks/internal",
        headers={"X-Workspace-Id": "ws-webhook"},
        json=webhook_payload,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ACCEPTED"
    assert data["fit_score"] >= 80
    assert data["fit_band"] == "HOT_OPPORTUNITY"

    # Verify persisted in DiscoveredLeadRecord
    lead_rec = session.get(DiscoveredLeadRecord, uuid.UUID(data["lead_id"]))
    assert lead_rec is not None
    assert lead_rec.email == "sarah.lead@innovate.tech"
    assert lead_rec.company_name == "Innovate Tech"
    assert len(lead_rec.conversation_starters_json) > 0
