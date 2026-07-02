from __future__ import annotations

import json
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import settings
from app.core.db import engine
from app.domain_models import ContactProgression
from tests.utils.shared_records import (
    SharedRecordStore,
    install_shared_record_mocks,
)


def _headers(token_headers: dict[str, str], workspace_id: str, *, idempotency: bool = False) -> dict[str, str]:
    headers = {**token_headers, "X-Workspace-Id": workspace_id}
    if idempotency:
        headers["Idempotency-Key"] = f"test-{uuid.uuid4()}"
    return headers


@pytest.fixture(autouse=True)
def shared_records(monkeypatch: pytest.MonkeyPatch) -> SharedRecordStore:
    return install_shared_record_mocks(monkeypatch)


def test_contact_import_preview_and_commit(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    shared_records: SharedRecordStore,
) -> None:
    workspace_id = f"ws-contact-pool-{uuid.uuid4().hex[:8]}"
    email = f"lead-{uuid.uuid4().hex[:8]}@example.com"
    csv_content = (
        "emailAddress,first,last,companyName,phoneNumber,tz\n"
        f"{email},Ada,Lovelace,Analytical,+15551234567,America/New_York\n"
        "bad-email,Grace,Hopper,Compiler Co,+15557654321,UTC\n"
    )

    preview_response = client.post(
        f"{settings.API_V1_STR}/contacts/import",
        headers=_headers(superuser_token_headers, workspace_id),
        files={"file": ("leads.csv", csv_content, "text/csv")},
    )
    assert preview_response.status_code == 200
    preview = preview_response.json()
    assert preview["committed"] is False
    assert preview["valid_rows"] == 1
    assert preview["invalid_rows"] == 1
    assert preview["mapping"]["phone"] == "phoneNumber"
    assert preview["preview_rows"][0]["data"]["email"] == email

    commit_response = client.post(
        f"{settings.API_V1_STR}/contacts/import",
        headers=_headers(superuser_token_headers, workspace_id),
        data={"mapping_json": json.dumps(preview["mapping"]), "commit": "true"},
        files={"file": ("leads.csv", csv_content, "text/csv")},
    )
    assert commit_response.status_code == 200
    committed = commit_response.json()
    assert committed["committed"] is False
    assert committed["created_count"] == 0

    corrected_csv = (
        "emailAddress,first,last,companyName,phoneNumber,tz\n"
        f"{email},Ada,Lovelace,Analytical,+15551234567,America/New_York\n"
    )
    commit_response = client.post(
        f"{settings.API_V1_STR}/contacts/import",
        headers=_headers(superuser_token_headers, workspace_id),
        data={"mapping_json": json.dumps(preview["mapping"]), "commit": "true"},
        files={"file": ("leads.csv", corrected_csv, "text/csv")},
    )
    assert commit_response.status_code == 200
    committed = commit_response.json()
    assert committed["committed"] is True
    assert committed["created_count"] == 1

    list_response = client.get(
        f"{settings.API_V1_STR}/contacts/?search={email}",
        headers=_headers(superuser_token_headers, workspace_id),
    )
    assert list_response.status_code == 200
    listing = list_response.json()
    assert listing["count"] >= 1
    contact = next(item for item in listing["data"] if item["email"] == email)
    assert contact["first_name"] == "Ada"
    assert contact["phone"] == "+15551234567"

    persisted = shared_records.get(contact["id"])
    assert persisted is not None
    assert persisted["parentId"]
    assert contact["account_id"] == persisted["parentId"]
    account = shared_records.get(persisted["parentId"])
    assert account is not None
    assert account["data"]["workspaceId"] == workspace_id
    assert account["companyName"] == "Analytical"
    assert account["data"]["accountKey"] == "analytical"


def test_campaign_audience_can_select_existing_contacts_by_filter(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    shared_records: SharedRecordStore,
) -> None:
    workspace_id = f"ws-contact-pool-{uuid.uuid4().hex[:8]}"
    campaign_response = client.post(
        f"{settings.API_V1_STR}/campaigns/",
        headers=_headers(superuser_token_headers, workspace_id),
        json={"name": "Existing Pool Campaign"},
    )
    assert campaign_response.status_code == 200
    campaign_id = campaign_response.json()["id"]
    saas_contact_id = shared_records.register_contact(
        workspace_id=workspace_id,
        email=f"saas-{uuid.uuid4().hex[:6]}@example.com",
        company="Acme SaaS",
        phone="+15550000001",
    )
    shared_records.register_contact(
        workspace_id=workspace_id,
        email=f"retail-{uuid.uuid4().hex[:6]}@example.com",
        company="Retail Co",
    )

    response = client.post(
        f"{settings.API_V1_STR}/campaigns/{campaign_id}/audience",
        headers=_headers(superuser_token_headers, workspace_id),
        json={
            "segment_name": "SaaS leads",
            "rules": [{"field_name": "company", "operator": "contains", "value": "SaaS"}],
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["selected_count"] == 1
    assert payload["added_count"] == 1
    assert payload["segment_name"] == "SaaS leads"

    with Session(engine) as session:
        progressions = session.exec(
            select(ContactProgression).where(
                ContactProgression.campaign_id == uuid.UUID(campaign_id)
            )
        ).all()
    assert len(progressions) == 1
    assert progressions[0].contact_id == saas_contact_id
