from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings


WORKSPACE_ID = "ws-story-1-2"


def _headers(token_headers: dict[str, str], *, idempotency: bool = False) -> dict[str, str]:
    headers = {**token_headers, "X-Workspace-Id": WORKSPACE_ID}
    if idempotency:
        headers["Idempotency-Key"] = "test-idempotency-key"
    return headers


def test_campaign_end_to_end_intake_flow_contract(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    _ = db
    create_response = client.post(
        f"{settings.API_V1_STR}/campaigns/",
        headers=_headers(superuser_token_headers, idempotency=True),
        json={"name": "Spring Outreach"},
    )
    assert create_response.status_code == 200
    campaign = create_response.json()
    campaign_id = campaign["id"]
    assert campaign["status"] == "draft"

    csv_content = (
        "emailAddress,first,companyName,tz,industry\n"
        "john@example.com,John,Acme,UTC,SaaS\n"
        ",Jane,Globex,UTC,Manufacturing\n"
    )
    import_response = client.post(
        f"{settings.API_V1_STR}/campaigns/{campaign_id}/contacts/import",
        headers=_headers(superuser_token_headers, idempotency=True),
        files={"file": ("contacts.csv", csv_content, "text/csv")},
    )
    assert import_response.status_code == 200
    intake = import_response.json()
    assert intake["requires_mapping"] is True
    assert intake["total_rows"] == 2
    assert len(intake["errors"]) >= 1
    first_error = intake["errors"][0]
    assert set(first_error.keys()) == {"row_number", "column", "semantic_error", "message"}

    mapping_response = client.post(
        f"{settings.API_V1_STR}/campaigns/{campaign_id}/contacts/mapping",
        headers=_headers(superuser_token_headers, idempotency=True),
        json={
            "mapping": {
                "email": "emailAddress",
                "firstName": "first",
                "company": "companyName",
                "timezone": "tz",
            }
        },
    )
    assert mapping_response.status_code == 200
    mapping_payload = mapping_response.json()
    assert len(mapping_payload["preview_rows"]) == 1
    preview_row = mapping_payload["preview_rows"][0]
    assert preview_row["data"]["email"] == "john@example.com"
    assert preview_row["data"]["firstName"] == "John"

    segment_response = client.post(
        f"{settings.API_V1_STR}/campaigns/{campaign_id}/segments",
        headers=_headers(superuser_token_headers, idempotency=True),
        json={
            "name": "SaaS Segment",
            "rules": [
                {
                    "field_name": "company",
                    "operator": "contains",
                    "value": "Acme",
                }
            ],
        },
    )
    assert segment_response.status_code == 200
    segment = segment_response.json()
    assert segment["estimated_count"] == 1

    strategy_response = client.post(
        f"{settings.API_V1_STR}/campaigns/{campaign_id}/strategy",
        headers=_headers(superuser_token_headers, idempotency=True),
        json={"channel_strategy": {"channel": "email", "cadence": "weekly"}},
    )
    assert strategy_response.status_code == 200
    strategy = strategy_response.json()
    assert strategy["campaign_id"] == campaign_id
    assert strategy["strategy_json"]["channel"] == "email"

    list_response = client.get(
        f"{settings.API_V1_STR}/campaigns/",
        headers=_headers(superuser_token_headers),
    )
    assert list_response.status_code == 200
    listing = list_response.json()
    assert listing["count"] >= 1
    assert any(item["id"] == campaign_id and item["status"] == "draft" for item in listing["data"])


def test_idempotency_key_required_for_mutations(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/campaigns/",
        headers=_headers(superuser_token_headers, idempotency=False),
        json={"name": "Missing Idempotency"},
    )
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["error"]["code"] == "IDEMPOTENCY_KEY_REQUIRED"
    assert detail["error"]["semantic"] == "POLICY_VIOLATION"
