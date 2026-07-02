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
from tests.utils.utils import get_superuser_token_headers


def _headers(token_headers: dict[str, str], workspace_id: str) -> dict[str, str]:
    return {**token_headers, "X-Workspace-Id": workspace_id}


@pytest.fixture(autouse=True)
def shared_records(monkeypatch: pytest.MonkeyPatch) -> SharedRecordStore:
    return install_shared_record_mocks(monkeypatch)


@pytest.fixture
def superuser_token_headers(client: TestClient) -> dict[str, str]:
    return get_superuser_token_headers(client)


def test_account_create_persists_workspace_scoped_account(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    shared_records: SharedRecordStore,
) -> None:
    workspace_id = f"ws-accounts-{uuid.uuid4().hex[:8]}"
    name = f"Analytical Health {uuid.uuid4().hex[:8]}"

    response = client.post(
        f"{settings.API_V1_STR}/accounts",
        headers=_headers(superuser_token_headers, workspace_id),
        json={
            "name": name,
            "website_url": "https://analytical.example",
            "industry": "Healthcare",
            "summary": "Multi-location account.",
            "tags": [" priority ", "", "voice-ready", "priority"],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["workspace_id"] == workspace_id
    assert payload["name"] == name
    assert payload["account_key"] == generate_account_key(name)
    assert payload["tags"] == ["priority", "voice-ready"]

    account = shared_records.get(payload["id"])
    assert account is not None
    assert account["data"]["workspaceId"] == workspace_id
    assert account["data"]["websiteUrl"] == "https://analytical.example"
    assert account["data"]["tags"] == ["priority", "voice-ready"]


def test_account_create_rejects_duplicate_normalized_name_in_workspace(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    workspace_id = f"ws-accounts-{uuid.uuid4().hex[:8]}"
    name = f"Compiler Co {uuid.uuid4().hex[:8]}"

    create_response = client.post(
        f"{settings.API_V1_STR}/accounts",
        headers=_headers(superuser_token_headers, workspace_id),
        json={"name": name},
    )
    assert create_response.status_code == 200

    duplicate_response = client.post(
        f"{settings.API_V1_STR}/accounts",
        headers=_headers(superuser_token_headers, workspace_id),
        json={"name": name.replace(" ", "   ")},
    )

    assert duplicate_response.status_code == 409
    assert duplicate_response.json()["detail"] == "Account already exists"


def test_account_create_rejects_empty_normalized_name(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    workspace_id = f"ws-accounts-{uuid.uuid4().hex[:8]}"

    response = client.post(
        f"{settings.API_V1_STR}/accounts",
        headers=_headers(superuser_token_headers, workspace_id),
        json={"name": " !!! --- "},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Account name is required"


def test_account_update_metadata_regenerates_key_and_updates_linked_contact_company(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    shared_records: SharedRecordStore,
) -> None:
    workspace_id = f"ws-accounts-{uuid.uuid4().hex[:8]}"
    old_name = f"Legacy Health {uuid.uuid4().hex[:8]}"
    account_id = shared_records.register_account(
        workspace_id=workspace_id,
        name=old_name,
        account_key=generate_account_key(old_name),
    )
    contact_id = shared_records.register_contact(
        workspace_id=workspace_id,
        parent_id=account_id,
        email=f"ada-{uuid.uuid4().hex[:8]}@example.com",
        company=old_name,
    )
    manual_contact_id = shared_records.register_contact(
        workspace_id=workspace_id,
        parent_id=account_id,
        email=f"grace-{uuid.uuid4().hex[:8]}@example.com",
        company="Keep Manual Company",
    )

    new_name = f"Modern Health {uuid.uuid4().hex[:8]}"
    response = client.patch(
        f"{settings.API_V1_STR}/accounts/{account_id}",
        headers=_headers(superuser_token_headers, workspace_id),
        json={
            "name": new_name,
            "industry": "Life Sciences",
            "status": "target",
            "summary": "Expanded buying committee.",
            "tags": [" strategic ", "strategic", "", "renewal"],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == new_name
    assert payload["account_key"] == generate_account_key(new_name)
    assert payload["industry"] == "Life Sciences"
    assert payload["status"] == "target"
    assert payload["summary"] == "Expanded buying committee."
    assert payload["tags"] == ["strategic", "renewal"]

    linked_contact = shared_records.get(contact_id)
    manual_contact = shared_records.get(manual_contact_id)
    account = shared_records.get(account_id)
    assert linked_contact is not None
    assert manual_contact is not None
    assert account is not None
    assert linked_contact["companyName"] == new_name
    assert manual_contact["companyName"] == "Keep Manual Company"
    assert account["data"]["tags"] == ["strategic", "renewal"]


def test_account_update_rejects_empty_normalized_name(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    shared_records: SharedRecordStore,
) -> None:
    workspace_id = f"ws-accounts-{uuid.uuid4().hex[:8]}"
    name = f"Compiler Co {uuid.uuid4().hex[:8]}"
    account_id = shared_records.register_account(
        workspace_id=workspace_id,
        name=name,
        account_key=generate_account_key(name),
    )

    response = client.patch(
        f"{settings.API_V1_STR}/accounts/{account_id}",
        headers=_headers(superuser_token_headers, workspace_id),
        json={"name": " ... !!! "},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Account name is required"


def test_account_update_rejects_duplicate_normalized_name(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    shared_records: SharedRecordStore,
) -> None:
    workspace_id = f"ws-accounts-{uuid.uuid4().hex[:8]}"
    suffix = uuid.uuid4().hex[:8]
    existing_name = f"Analytical Health {suffix}"
    shared_records.register_account(
        workspace_id=workspace_id,
        name=existing_name,
        account_key=generate_account_key(existing_name),
    )
    account_name = f"Compiler Co {suffix}"
    account_id = shared_records.register_account(
        workspace_id=workspace_id,
        name=account_name,
        account_key=generate_account_key(account_name),
    )

    response = client.patch(
        f"{settings.API_V1_STR}/accounts/{account_id}",
        headers=_headers(superuser_token_headers, workspace_id),
        json={"name": f"Analytical   Health {suffix}"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Account already exists"


def test_account_update_ignores_explicit_null_metadata_fields(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    shared_records: SharedRecordStore,
) -> None:
    workspace_id = f"ws-accounts-{uuid.uuid4().hex[:8]}"
    name = f"Compiler Co {uuid.uuid4().hex[:8]}"
    account_id = shared_records.register_account(
        workspace_id=workspace_id,
        name=name,
        account_key=generate_account_key(name),
        website_url="https://compiler.example",
        industry="Healthcare",
        status="target",
        summary="Existing summary.",
        tags=["priority"],
    )

    response = client.patch(
        f"{settings.API_V1_STR}/accounts/{account_id}",
        headers=_headers(superuser_token_headers, workspace_id),
        json={
            "website_url": None,
            "industry": None,
            "status": None,
            "summary": None,
            "tags": None,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["website_url"] == "https://compiler.example"
    assert payload["industry"] == "Healthcare"
    assert payload["status"] == "target"
    assert payload["summary"] == "Existing summary."
    assert payload["tags"] == ["priority"]


def test_account_update_is_workspace_scoped(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    shared_records: SharedRecordStore,
) -> None:
    owner_workspace_id = f"ws-owner-{uuid.uuid4().hex[:8]}"
    other_workspace_id = f"ws-other-{uuid.uuid4().hex[:8]}"
    name = f"Compiler Co {uuid.uuid4().hex[:8]}"
    account_id = shared_records.register_account(
        workspace_id=owner_workspace_id,
        name=name,
        account_key=generate_account_key(name),
    )

    response = client.patch(
        f"{settings.API_V1_STR}/accounts/{account_id}",
        headers=_headers(superuser_token_headers, other_workspace_id),
        json={"summary": "Should not update"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Account not found"


def test_account_contact_assignment_links_contacts_and_updates_customer_360_detail(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    shared_records: SharedRecordStore,
) -> None:
    workspace_id = f"ws-assign-{uuid.uuid4().hex[:8]}"
    account_name = f"Assignment Health {uuid.uuid4().hex[:8]}"
    account_id = shared_records.register_account(
        workspace_id=workspace_id,
        name=account_name,
        account_key=generate_account_key(account_name),
    )
    first_contact_id = shared_records.register_contact(
        workspace_id=workspace_id,
        email=f"ada-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Ada",
        last_name="Lovelace",
        company="Old Company",
    )
    second_contact_id = shared_records.register_contact(
        workspace_id=workspace_id,
        email=f"grace-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Grace",
        last_name="Hopper",
    )

    response = client.post(
        f"{settings.API_V1_STR}/accounts/{account_id}/contacts",
        headers=_headers(superuser_token_headers, workspace_id),
        json={"contact_ids": [str(first_contact_id), str(second_contact_id)]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["account_id"] == str(account_id)
    assert payload["assigned_count"] == 2
    assert payload["unassigned_count"] == 0
    assert payload["contact_ids"] == [str(first_contact_id), str(second_contact_id)]

    first_contact = shared_records.get(first_contact_id)
    second_contact = shared_records.get(second_contact_id)
    assert first_contact is not None
    assert second_contact is not None
    assert first_contact["parentId"] == str(account_id)
    assert first_contact["companyName"] == account_name
    assert second_contact["parentId"] == str(account_id)
    assert second_contact["companyName"] == account_name

    detail_response = client.get(
        f"{settings.API_V1_STR}/customer-360/accounts/{account_id}",
        headers=_headers(superuser_token_headers, workspace_id),
    )
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert {contact["id"] for contact in detail["contacts"]} == {
        str(first_contact_id),
        str(second_contact_id),
    }


def test_account_contact_assignment_rejects_contact_outside_active_workspace(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    shared_records: SharedRecordStore,
) -> None:
    workspace_id = f"ws-assign-{uuid.uuid4().hex[:8]}"
    other_workspace_id = f"ws-other-{uuid.uuid4().hex[:8]}"
    account_name = f"Assignment Health {uuid.uuid4().hex[:8]}"
    account_id = shared_records.register_account(
        workspace_id=workspace_id,
        name=account_name,
        account_key=generate_account_key(account_name),
    )
    other_contact_id = shared_records.register_contact(
        workspace_id=other_workspace_id,
        email=f"ada-{uuid.uuid4().hex[:8]}@example.com",
    )

    response = client.post(
        f"{settings.API_V1_STR}/accounts/{account_id}/contacts",
        headers=_headers(superuser_token_headers, workspace_id),
        json={"contact_ids": [str(other_contact_id)]},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Contact not found"


def test_account_contact_assignment_deduplicates_requested_contact_ids(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    shared_records: SharedRecordStore,
) -> None:
    workspace_id = f"ws-assign-{uuid.uuid4().hex[:8]}"
    account_name = f"Assignment Health {uuid.uuid4().hex[:8]}"
    account_id = shared_records.register_account(
        workspace_id=workspace_id,
        name=account_name,
        account_key=generate_account_key(account_name),
    )
    contact_id = shared_records.register_contact(
        workspace_id=workspace_id,
        email=f"ada-{uuid.uuid4().hex[:8]}@example.com",
    )

    response = client.post(
        f"{settings.API_V1_STR}/accounts/{account_id}/contacts",
        headers=_headers(superuser_token_headers, workspace_id),
        json={"contact_ids": [str(contact_id), str(contact_id)]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["account_id"] == str(account_id)
    assert payload["assigned_count"] == 1
    assert payload["contact_ids"] == [str(contact_id)]


def test_account_contact_assignment_rejects_missing_account(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    workspace_id = f"ws-assign-{uuid.uuid4().hex[:8]}"

    response = client.post(
        f"{settings.API_V1_STR}/accounts/{uuid.uuid4()}/contacts",
        headers=_headers(superuser_token_headers, workspace_id),
        json={"contact_ids": [str(uuid.uuid4())]},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Account not found"


def test_account_contact_unassignment_unlinks_contact_and_keeps_company(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    shared_records: SharedRecordStore,
) -> None:
    workspace_id = f"ws-unassign-{uuid.uuid4().hex[:8]}"
    account_name = f"Assignment Health {uuid.uuid4().hex[:8]}"
    account_id = shared_records.register_account(
        workspace_id=workspace_id,
        name=account_name,
        account_key=generate_account_key(account_name),
    )
    contact_id = shared_records.register_contact(
        workspace_id=workspace_id,
        parent_id=account_id,
        email=f"ada-{uuid.uuid4().hex[:8]}@example.com",
        company="Keep Existing Company",
    )

    response = client.delete(
        f"{settings.API_V1_STR}/accounts/{account_id}/contacts/{contact_id}",
        headers=_headers(superuser_token_headers, workspace_id),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["account_id"] == str(account_id)
    assert payload["assigned_count"] == 0
    assert payload["unassigned_count"] == 1
    assert payload["contact_ids"] == [str(contact_id)]

    contact = shared_records.get(contact_id)
    assert contact is not None
    assert "parentId" not in contact
    assert contact["companyName"] == "Keep Existing Company"


def test_account_contact_unassignment_rejects_missing_account(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    workspace_id = f"ws-unassign-{uuid.uuid4().hex[:8]}"

    response = client.delete(
        f"{settings.API_V1_STR}/accounts/{uuid.uuid4()}/contacts/{uuid.uuid4()}",
        headers=_headers(superuser_token_headers, workspace_id),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Account not found"


def test_account_contact_unassignment_rejects_contact_on_different_account(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    shared_records: SharedRecordStore,
) -> None:
    workspace_id = f"ws-unassign-{uuid.uuid4().hex[:8]}"
    target_name = f"Target Health {uuid.uuid4().hex[:8]}"
    target_account_id = shared_records.register_account(
        workspace_id=workspace_id,
        name=target_name,
        account_key=generate_account_key(target_name),
    )
    other_name = f"Other Health {uuid.uuid4().hex[:8]}"
    other_account_id = shared_records.register_account(
        workspace_id=workspace_id,
        name=other_name,
        account_key=generate_account_key(other_name),
    )
    contact_id = shared_records.register_contact(
        workspace_id=workspace_id,
        parent_id=other_account_id,
        email=f"ada-{uuid.uuid4().hex[:8]}@example.com",
    )

    response = client.delete(
        f"{settings.API_V1_STR}/accounts/{target_account_id}/contacts/{contact_id}",
        headers=_headers(superuser_token_headers, workspace_id),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Contact not found"
