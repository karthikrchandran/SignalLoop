from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.domain_models import Account, Contact


def _headers(token_headers: dict[str, str], workspace_id: str) -> dict[str, str]:
    return {**token_headers, "X-Workspace-Id": workspace_id}


def test_customer_360_account_list_and_detail(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    workspace_id = f"ws-c360-{uuid.uuid4().hex[:8]}"
    account = Account(
        workspace_id=workspace_id,
        name=f"Analytical {uuid.uuid4().hex[:8]}",
        account_key=f"analytical-{uuid.uuid4().hex[:8]}",
    )
    db.add(account)
    db.commit()
    db.refresh(account)

    contact = Contact(
        workspace_id=workspace_id,
        account_id=account.id,
        email=f"ada-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Ada",
        last_name="Lovelace",
        company=account.name,
    )
    db.add(contact)
    db.commit()
    db.refresh(contact)

    list_response = client.get(
        f"{settings.API_V1_STR}/customer-360/accounts",
        headers=_headers(superuser_token_headers, workspace_id),
    )

    assert list_response.status_code == 200
    listing = list_response.json()
    assert listing["count"] == 1
    row = listing["data"][0]
    assert row["name"] == account.name
    assert row["contact_count"] == 1

    detail_response = client.get(
        f"{settings.API_V1_STR}/customer-360/accounts/{account.id}",
        headers=_headers(superuser_token_headers, workspace_id),
    )

    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["account"]["name"] == account.name
    assert detail["contacts"][0]["display_name"] == "Ada Lovelace"
    assert detail["channel_summaries"]["chatbot"]["count"] == 0


def test_customer_360_account_detail_is_workspace_scoped(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    owner_workspace_id = f"ws-owner-{uuid.uuid4().hex[:8]}"
    other_workspace_id = f"ws-other-{uuid.uuid4().hex[:8]}"
    account = Account(
        workspace_id=owner_workspace_id,
        name=f"Compiler Co {uuid.uuid4().hex[:8]}",
        account_key=f"compiler-co-{uuid.uuid4().hex[:8]}",
    )
    db.add(account)
    db.commit()
    db.refresh(account)

    response = client.get(
        f"{settings.API_V1_STR}/customer-360/accounts/{account.id}",
        headers=_headers(superuser_token_headers, other_workspace_id),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Account not found"
