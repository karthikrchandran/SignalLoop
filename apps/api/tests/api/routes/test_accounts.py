from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import settings
from app.domain.accounts.service import generate_account_key
from app.domain_models import Account, Contact


def _headers(token_headers: dict[str, str], workspace_id: str) -> dict[str, str]:
    return {**token_headers, "X-Workspace-Id": workspace_id}


def test_account_create_persists_workspace_scoped_account(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
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

    account = db.get(Account, uuid.UUID(payload["id"]))
    assert account is not None
    assert account.workspace_id == workspace_id
    assert account.website_url == "https://analytical.example"
    assert account.tags_json == ["priority", "voice-ready"]


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


def test_account_update_metadata_regenerates_key_and_updates_linked_contact_company(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    workspace_id = f"ws-accounts-{uuid.uuid4().hex[:8]}"
    old_name = f"Legacy Health {uuid.uuid4().hex[:8]}"
    account = Account(
        workspace_id=workspace_id,
        name=old_name,
        account_key=generate_account_key(old_name),
    )
    db.add(account)
    db.commit()
    db.refresh(account)

    contact = Contact(
        workspace_id=workspace_id,
        account_id=account.id,
        email=f"ada-{uuid.uuid4().hex[:8]}@example.com",
        company=old_name,
    )
    manually_named_contact = Contact(
        workspace_id=workspace_id,
        account_id=account.id,
        email=f"grace-{uuid.uuid4().hex[:8]}@example.com",
        company="Keep Manual Company",
    )
    db.add(contact)
    db.add(manually_named_contact)
    db.commit()

    new_name = f"Modern Health {uuid.uuid4().hex[:8]}"
    response = client.patch(
        f"{settings.API_V1_STR}/accounts/{account.id}",
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

    db.refresh(contact)
    db.refresh(manually_named_contact)
    assert contact.company == new_name
    assert manually_named_contact.company == "Keep Manual Company"

    db.expire_all()
    persisted = db.exec(select(Account).where(Account.id == account.id)).one()
    assert persisted.tags_json == ["strategic", "renewal"]


def test_account_update_is_workspace_scoped(
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

    response = client.patch(
        f"{settings.API_V1_STR}/accounts/{account.id}",
        headers=_headers(superuser_token_headers, other_workspace_id),
        json={"summary": "Should not update"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Account not found"
