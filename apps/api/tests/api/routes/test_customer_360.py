from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.domain.accounts.service import generate_account_key
from tests.utils.shared_records import (
    SharedRecordStore,
    install_shared_record_mocks,
)


def _headers(token_headers: dict[str, str], workspace_id: str) -> dict[str, str]:
    return {**token_headers, "X-Workspace-Id": workspace_id}


@pytest.fixture(autouse=True)
def shared_records(monkeypatch: pytest.MonkeyPatch) -> SharedRecordStore:
    return install_shared_record_mocks(monkeypatch)


def test_customer_360_account_list_and_detail(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    shared_records: SharedRecordStore,
) -> None:
    workspace_id = f"ws-c360-{uuid.uuid4().hex[:8]}"
    account_name = f"Analytical {uuid.uuid4().hex[:8]}"
    account_id = shared_records.register_account(
        workspace_id=workspace_id,
        name=account_name,
        account_key=generate_account_key(account_name),
    )
    shared_records.register_contact(
        workspace_id=workspace_id,
        parent_id=account_id,
        email=f"ada-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Ada",
        last_name="Lovelace",
        company=account_name,
    )

    list_response = client.get(
        f"{settings.API_V1_STR}/customer-360/accounts",
        headers=_headers(superuser_token_headers, workspace_id),
    )

    assert list_response.status_code == 200
    listing = list_response.json()
    assert listing["count"] == 1
    row = listing["data"][0]
    assert row["name"] == account_name
    assert row["contact_count"] == 1

    detail_response = client.get(
        f"{settings.API_V1_STR}/customer-360/accounts/{account_id}",
        headers=_headers(superuser_token_headers, workspace_id),
    )

    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["account"]["name"] == account_name
    assert detail["contacts"][0]["display_name"] == "Ada Lovelace"
    assert detail["channel_summaries"]["chatbot"]["count"] == 0


def test_customer_360_account_detail_is_workspace_scoped(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    shared_records: SharedRecordStore,
) -> None:
    owner_workspace_id = f"ws-owner-{uuid.uuid4().hex[:8]}"
    other_workspace_id = f"ws-other-{uuid.uuid4().hex[:8]}"
    account_name = f"Compiler Co {uuid.uuid4().hex[:8]}"
    account_id = shared_records.register_account(
        workspace_id=owner_workspace_id,
        name=account_name,
        account_key=generate_account_key(account_name),
    )

    response = client.get(
        f"{settings.API_V1_STR}/customer-360/accounts/{account_id}",
        headers=_headers(superuser_token_headers, other_workspace_id),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Account not found"
