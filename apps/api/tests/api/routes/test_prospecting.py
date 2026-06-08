from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import settings
from app.domain.audit.audit_events import AuditEvent
from app.domain_models import Contact, ProspectingSnapshot
from app.infrastructure.rag.crawler import CrawledPage


def _headers(token_headers: dict[str, str], workspace_id: str, *, idempotency: bool = False) -> dict[str, str]:
    headers = {**token_headers, "X-Workspace-Id": workspace_id}
    if idempotency:
        headers["Idempotency-Key"] = f"prospecting-{uuid.uuid4()}"
    return headers


def test_run_prospecting_research_persists_snapshot_and_audit_event(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
    monkeypatch,
) -> None:
    async def fake_crawl_website(url: str, *, depth: int = 1, max_pages: int = 10) -> list[CrawledPage]:
        return [
            CrawledPage(
                url=url,
                title="Analytical Revenue Automation",
                text="Analytical improves outbound conversion with automated follow-up for revenue teams.",
            )
        ]

    monkeypatch.setattr("app.domain.prospecting.service.crawl_website", fake_crawl_website)

    workspace_id = f"ws-prospecting-{uuid.uuid4().hex[:8]}"
    contact = Contact(
        workspace_id=workspace_id,
        email=f"ada-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Ada",
        last_name="Lovelace",
        company="Analytical",
        tags_json=["chatbot-lead"],
        intent_json=["pricing-request"],
    )
    db.add(contact)
    db.commit()
    db.refresh(contact)

    response = client.post(
        f"{settings.API_V1_STR}/prospecting/research",
        headers=_headers(superuser_token_headers, workspace_id, idempotency=True),
        json={
            "contact_id": str(contact.id),
            "company_url": "https://example.com",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["contact_id"] == str(contact.id)
    assert payload["company_url"] == "https://example.com"
    assert "Analytical" in payload["account_summary"]
    assert "Subject:" in payload["email_draft"]
    assert "Ada" in payload["voice_opener"]

    snapshot = db.exec(
        select(ProspectingSnapshot).where(ProspectingSnapshot.id == uuid.UUID(payload["id"]))
    ).first()
    assert snapshot is not None
    assert snapshot.workspace_id == workspace_id
    assert snapshot.contact_id == contact.id

    audit_event = db.exec(
        select(AuditEvent).where(
            AuditEvent.workspace_id == workspace_id,
            AuditEvent.event_name == "prospect.researched",
            AuditEvent.resource_id == str(snapshot.id),
        )
    ).first()
    assert audit_event is not None
    assert audit_event.payload["contact_id"] == str(contact.id)


def test_run_prospecting_research_enforces_workspace_isolation(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    owner_workspace_id = f"ws-prospecting-owner-{uuid.uuid4().hex[:8]}"
    other_workspace_id = f"ws-prospecting-other-{uuid.uuid4().hex[:8]}"
    contact = Contact(
        workspace_id=owner_workspace_id,
        email=f"grace-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Grace",
        last_name="Hopper",
        company="Compiler Co",
    )
    db.add(contact)
    db.commit()
    db.refresh(contact)

    response = client.post(
        f"{settings.API_V1_STR}/prospecting/research",
        headers=_headers(superuser_token_headers, other_workspace_id, idempotency=True),
        json={"contact_id": str(contact.id)},
    )

    assert response.status_code == 404
