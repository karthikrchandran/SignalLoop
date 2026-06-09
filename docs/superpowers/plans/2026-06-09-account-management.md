# Account Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add account create/edit and contact assignment workflows on top of the Customer 360 account model.

**Architecture:** Keep Customer 360 as the read/profile surface and add a focused `/api/v1/accounts` command API for writes. Frontend changes stay inside `apps/web/src/features/customer-360/`, reusing the current list/detail pages and existing UI primitives.

**Tech Stack:** FastAPI, SQLModel, pytest, React, TanStack Router, Vite, Playwright, PowerShell.

---

## Preflight

Run:

```powershell
git status --short
```

Expected: clean except for this plan/spec branch work. Do not mix unrelated changes into Account Management commits.

At execution time, create an isolated worktree from `main` before making code changes:

```powershell
git worktree add ..\eMailVoice-account-management -b account-management
```

## File Structure

Backend:

- Modify `apps/api/app/domain_models.py`: add account create/update/assignment schemas.
- Modify `apps/api/app/domain/accounts/service.py`: add create/update/assign/unassign helpers.
- Create `apps/api/app/api/routes/accounts.py`: account command endpoints.
- Modify `apps/api/app/api/main.py`: include account command router.
- Test `apps/api/tests/api/routes/test_accounts.py`.
- Extend `apps/api/tests/domain/test_accounts_service.py`.

Frontend:

- Modify `apps/web/src/features/customer-360/api.ts`: add account command API calls and contact list types.
- Create `apps/web/src/features/customer-360/AccountFormDialog.tsx`.
- Create `apps/web/src/features/customer-360/AssignContactsDialog.tsx`.
- Modify `apps/web/src/features/customer-360/Customer360AccountsPage.tsx`.
- Modify `apps/web/src/features/customer-360/Customer360AccountProfilePage.tsx`.
- Extend `apps/web/tests/customer-360.spec.ts`.

## Task 1: Backend Account Command Schemas

**Files:**
- Modify: `apps/api/app/domain_models.py`
- Test: `apps/api/tests/api/routes/test_accounts.py`

- [ ] **Step 1: Write failing API tests for create and duplicate create**

Create `apps/api/tests/api/routes/test_accounts.py` with:

```python
from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings


def _headers(token_headers: dict[str, str], workspace_id: str) -> dict[str, str]:
    return {**token_headers, "X-Workspace-Id": workspace_id}


def test_create_account(client: TestClient, superuser_token_headers: dict[str, str]) -> None:
    workspace_id = f"ws-account-{uuid.uuid4().hex[:8]}"
    response = client.post(
        f"{settings.API_V1_STR}/accounts",
        headers=_headers(superuser_token_headers, workspace_id),
        json={
            "name": "Analytical Health",
            "website_url": "https://analytical.example",
            "industry": "Healthcare",
            "status": "active",
            "summary": "Regional healthcare buyer.",
            "tags": ["pricing", "voice-ready"],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["workspace_id"] == workspace_id
    assert body["name"] == "Analytical Health"
    assert body["account_key"] == "analytical-health"
    assert body["tags"] == ["pricing", "voice-ready"]


def test_create_account_rejects_duplicate_key(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    workspace_id = f"ws-account-{uuid.uuid4().hex[:8]}"
    headers = _headers(superuser_token_headers, workspace_id)
    payload = {"name": "Analytical Health"}

    first = client.post(f"{settings.API_V1_STR}/accounts", headers=headers, json=payload)
    second = client.post(
        f"{settings.API_V1_STR}/accounts",
        headers=headers,
        json={"name": "Analytical   Health!!!"},
    )

    assert first.status_code == 200
    assert second.status_code == 409
    assert second.json()["detail"] == "Account already exists"
```

- [ ] **Step 2: Run the failing tests**

Run:

```powershell
uv run pytest tests/api/routes/test_accounts.py -q
```

Expected: FAIL because `/api/v1/accounts` does not exist.

- [ ] **Step 3: Add request/response schemas**

In `apps/api/app/domain_models.py`, add near `AccountPublic`:

```python
class AccountCreate(SQLModel):
    """Request payload for creating an account."""

    name: str = Field(min_length=1, max_length=255)
    website_url: str | None = None
    industry: str | None = Field(default=None, max_length=255)
    status: str = Field(default="active", max_length=64)
    summary: str | None = None
    tags: list[str] = Field(default_factory=list)


class AccountUpdate(SQLModel):
    """Request payload for updating an account."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    website_url: str | None = None
    industry: str | None = Field(default=None, max_length=255)
    status: str | None = Field(default=None, max_length=64)
    summary: str | None = None
    tags: list[str] | None = None


class AccountContactAssignment(SQLModel):
    """Request payload for assigning contacts to an account."""

    contact_ids: list[uuid.UUID] = Field(min_length=1, max_length=100)


class AccountContactAssignmentPublic(SQLModel):
    """Response payload for account contact assignment changes."""

    account_id: uuid.UUID
    assigned_count: int = 0
    unassigned_count: int = 0
    contact_ids: list[uuid.UUID] = Field(default_factory=list)
```

- [ ] **Step 4: Run tests and commit**

Run:

```powershell
uv run pytest tests/api/routes/test_accounts.py -q
```

Expected: still FAIL because routes are not implemented.

Do not commit yet. Task 2 turns these tests green and commits the schema with the route implementation.

## Task 2: Backend Account Create And Update

**Files:**
- Modify: `apps/api/app/domain/accounts/service.py`
- Create: `apps/api/app/api/routes/accounts.py`
- Modify: `apps/api/app/api/main.py`
- Test: `apps/api/tests/api/routes/test_accounts.py`

- [ ] **Step 1: Extend failing tests for patch behavior**

Append to `apps/api/tests/api/routes/test_accounts.py`:

```python
def test_update_account_metadata(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    workspace_id = f"ws-account-{uuid.uuid4().hex[:8]}"
    headers = _headers(superuser_token_headers, workspace_id)
    create = client.post(f"{settings.API_V1_STR}/accounts", headers=headers, json={"name": "Old Name"})
    account_id = create.json()["id"]

    response = client.patch(
        f"{settings.API_V1_STR}/accounts/{account_id}",
        headers=headers,
        json={"name": "New Name", "industry": "Healthcare", "tags": ["tier-1"]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "New Name"
    assert body["account_key"] == "new-name"
    assert body["industry"] == "Healthcare"
    assert body["tags"] == ["tier-1"]


def test_update_account_rejects_cross_workspace(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    owner_workspace = f"ws-owner-{uuid.uuid4().hex[:8]}"
    other_workspace = f"ws-other-{uuid.uuid4().hex[:8]}"
    create = client.post(
        f"{settings.API_V1_STR}/accounts",
        headers=_headers(superuser_token_headers, owner_workspace),
        json={"name": "Owner Account"},
    )
    account_id = create.json()["id"]

    response = client.patch(
        f"{settings.API_V1_STR}/accounts/{account_id}",
        headers=_headers(superuser_token_headers, other_workspace),
        json={"name": "Wrong Workspace"},
    )

    assert response.status_code == 404
```

- [ ] **Step 2: Implement service helpers**

Add to `apps/api/app/domain/accounts/service.py`:

```python
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException

from app.domain_models import AccountCreate, AccountUpdate


def get_account_for_workspace(
    session: Session,
    *,
    workspace_id: str,
    account_id: uuid.UUID,
) -> Account | None:
    return session.exec(
        select(Account).where(Account.id == account_id, Account.workspace_id == workspace_id)
    ).first()


def _clean_tags(tags: list[str] | None) -> list[str]:
    cleaned: list[str] = []
    for tag in tags or []:
        value = tag.strip()
        if value and value not in cleaned:
            cleaned.append(value)
    return cleaned


def create_account(
    session: Session,
    *,
    workspace_id: str,
    account_in: AccountCreate,
) -> Account:
    name = account_in.name.strip()
    account_key = generate_account_key(name)
    if not account_key:
        raise HTTPException(status_code=400, detail="Account name is required")
    if _find_account_by_key(session, workspace_id=workspace_id, account_key=account_key):
        raise HTTPException(status_code=409, detail="Account already exists")
    account = Account(
        workspace_id=workspace_id,
        name=name,
        account_key=account_key,
        website_url=account_in.website_url,
        industry=account_in.industry,
        status=account_in.status or "active",
        summary=account_in.summary,
        tags_json=_clean_tags(account_in.tags),
    )
    session.add(account)
    session.commit()
    session.refresh(account)
    return account


def update_account(
    session: Session,
    *,
    workspace_id: str,
    account_id: uuid.UUID,
    account_in: AccountUpdate,
) -> Account:
    account = get_account_for_workspace(session, workspace_id=workspace_id, account_id=account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")
    old_name = account.name
    if account_in.name is not None:
        name = account_in.name.strip()
        account_key = generate_account_key(name)
        if not account_key:
            raise HTTPException(status_code=400, detail="Account name is required")
        existing = _find_account_by_key(session, workspace_id=workspace_id, account_key=account_key)
        if existing is not None and existing.id != account.id:
            raise HTTPException(status_code=409, detail="Account already exists")
        account.name = name
        account.account_key = account_key
    if account_in.website_url is not None:
        account.website_url = account_in.website_url
    if account_in.industry is not None:
        account.industry = account_in.industry
    if account_in.status is not None:
        account.status = account_in.status
    if account_in.summary is not None:
        account.summary = account_in.summary
    if account_in.tags is not None:
        account.tags_json = _clean_tags(account_in.tags)
    account.updated_at = datetime.now(timezone.utc)
    session.add(account)
    if account.name != old_name:
        from app.domain_models import Contact

        contacts = session.exec(
            select(Contact).where(Contact.workspace_id == workspace_id, Contact.account_id == account.id)
        ).all()
        for contact in contacts:
            if contact.company == old_name:
                contact.company = account.name
                session.add(contact)
    session.commit()
    session.refresh(account)
    return account
```

- [ ] **Step 3: Add account routes**

Create `apps/api/app/api/routes/accounts.py`:

```python
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends

from app.api.deps import SessionDep, require_admin
from app.api.request_context import WorkspaceIdDep
from app.domain.accounts.service import account_to_public, create_account, update_account
from app.domain_models import AccountCreate, AccountPublic, AccountUpdate

router = APIRouter(prefix="/accounts", tags=["accounts"], dependencies=[Depends(require_admin)])


@router.post("", response_model=AccountPublic)
def create_account_route(
    account_in: AccountCreate,
    session: SessionDep,
    workspace_id: WorkspaceIdDep,
) -> AccountPublic:
    account = create_account(session, workspace_id=workspace_id, account_in=account_in)
    return account_to_public(account)


@router.patch("/{account_id}", response_model=AccountPublic)
def update_account_route(
    account_id: uuid.UUID,
    account_in: AccountUpdate,
    session: SessionDep,
    workspace_id: WorkspaceIdDep,
) -> AccountPublic:
    account = update_account(
        session,
        workspace_id=workspace_id,
        account_id=account_id,
        account_in=account_in,
    )
    return account_to_public(account)
```

In `apps/api/app/api/main.py`, add `accounts` to the existing route import list and include the router:

```python
from app.api.routes import accounts

api_router.include_router(accounts.router)
```

- [ ] **Step 4: Run backend account tests**

Run:

```powershell
uv run pytest tests/api/routes/test_accounts.py -q
```

Expected: create/update tests PASS.

- [ ] **Step 5: Commit**

Run:

```powershell
git add apps/api/app/domain_models.py apps/api/app/domain/accounts/service.py apps/api/app/api/routes/accounts.py apps/api/app/api/main.py apps/api/tests/api/routes/test_accounts.py
git commit -m "feat: add account management api"
```

## Task 3: Backend Contact Assignment Commands

**Files:**
- Modify: `apps/api/app/domain/accounts/service.py`
- Modify: `apps/api/app/api/routes/accounts.py`
- Test: `apps/api/tests/api/routes/test_accounts.py`

- [ ] **Step 1: Add failing assignment tests**

Append to `apps/api/tests/api/routes/test_accounts.py`:

```python
from app.domain_models import Contact


def test_assign_contacts_to_account(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    workspace_id = f"ws-assign-{uuid.uuid4().hex[:8]}"
    headers = _headers(superuser_token_headers, workspace_id)
    account_response = client.post(
        f"{settings.API_V1_STR}/accounts",
        headers=headers,
        json={"name": "Analytical Health"},
    )
    account_id = account_response.json()["id"]
    contacts = [
        Contact(workspace_id=workspace_id, email=f"ada-{uuid.uuid4().hex[:8]}@example.com"),
        Contact(workspace_id=workspace_id, email=f"grace-{uuid.uuid4().hex[:8]}@example.com"),
    ]
    db.add_all(contacts)
    db.commit()
    for contact in contacts:
        db.refresh(contact)

    response = client.post(
        f"{settings.API_V1_STR}/accounts/{account_id}/contacts",
        headers=headers,
        json={"contact_ids": [str(contact.id) for contact in contacts]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["assigned_count"] == 2
    profile = client.get(
        f"{settings.API_V1_STR}/customer-360/accounts/{account_id}",
        headers=headers,
    )
    assert profile.status_code == 200
    assert len(profile.json()["contacts"]) == 2
    db.refresh(contacts[0])
    assert str(contacts[0].account_id) == account_id
    assert contacts[0].company == "Analytical Health"


def test_unassign_contact_from_account(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    workspace_id = f"ws-unassign-{uuid.uuid4().hex[:8]}"
    headers = _headers(superuser_token_headers, workspace_id)
    account_response = client.post(
        f"{settings.API_V1_STR}/accounts",
        headers=headers,
        json={"name": "Analytical Health"},
    )
    account_id = account_response.json()["id"]
    contact = Contact(
        workspace_id=workspace_id,
        email=f"ada-{uuid.uuid4().hex[:8]}@example.com",
        company="Analytical Health",
    )
    db.add(contact)
    db.commit()
    db.refresh(contact)
    assign = client.post(
        f"{settings.API_V1_STR}/accounts/{account_id}/contacts",
        headers=headers,
        json={"contact_ids": [str(contact.id)]},
    )
    assert assign.status_code == 200

    response = client.delete(
        f"{settings.API_V1_STR}/accounts/{account_id}/contacts/{contact.id}",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["unassigned_count"] == 1
    db.refresh(contact)
    assert contact.account_id is None
    assert contact.company == "Analytical Health"
```

- [ ] **Step 2: Implement assignment helpers**

Add to `apps/api/app/domain/accounts/service.py`:

```python
from app.domain_models import AccountContactAssignmentPublic, Contact


def assign_contacts_to_account(
    session: Session,
    *,
    workspace_id: str,
    account_id: uuid.UUID,
    contact_ids: list[uuid.UUID],
) -> AccountContactAssignmentPublic:
    account = get_account_for_workspace(session, workspace_id=workspace_id, account_id=account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")

    contacts = list(
        session.exec(
            select(Contact).where(
                Contact.workspace_id == workspace_id,
                Contact.id.in_(contact_ids),
            )
        ).all()
    )
    if len(contacts) != len(set(contact_ids)):
        raise HTTPException(status_code=404, detail="Contact not found")

    for contact in contacts:
        contact.account_id = account.id
        contact.company = account.name
        session.add(contact)
    session.commit()
    return AccountContactAssignmentPublic(
        account_id=account.id,
        assigned_count=len(contacts),
        contact_ids=[contact.id for contact in contacts],
    )


def unassign_contact_from_account(
    session: Session,
    *,
    workspace_id: str,
    account_id: uuid.UUID,
    contact_id: uuid.UUID,
) -> AccountContactAssignmentPublic:
    account = get_account_for_workspace(session, workspace_id=workspace_id, account_id=account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")
    contact = session.exec(
        select(Contact).where(
            Contact.workspace_id == workspace_id,
            Contact.id == contact_id,
            Contact.account_id == account.id,
        )
    ).first()
    if contact is None:
        raise HTTPException(status_code=404, detail="Contact not found")
    contact.account_id = None
    session.add(contact)
    session.commit()
    return AccountContactAssignmentPublic(
        account_id=account.id,
        unassigned_count=1,
        contact_ids=[contact.id],
    )
```

- [ ] **Step 3: Add assignment routes**

Add to `accounts.py`:

```python
from app.domain.accounts.service import assign_contacts_to_account, unassign_contact_from_account
from app.domain_models import AccountContactAssignment, AccountContactAssignmentPublic


@router.post("/{account_id}/contacts", response_model=AccountContactAssignmentPublic)
def assign_contacts_route(
    account_id: uuid.UUID,
    assignment: AccountContactAssignment,
    session: SessionDep,
    workspace_id: WorkspaceIdDep,
) -> AccountContactAssignmentPublic:
    return assign_contacts_to_account(
        session,
        workspace_id=workspace_id,
        account_id=account_id,
        contact_ids=assignment.contact_ids,
    )


@router.delete("/{account_id}/contacts/{contact_id}", response_model=AccountContactAssignmentPublic)
def unassign_contact_route(
    account_id: uuid.UUID,
    contact_id: uuid.UUID,
    session: SessionDep,
    workspace_id: WorkspaceIdDep,
) -> AccountContactAssignmentPublic:
    return unassign_contact_from_account(
        session,
        workspace_id=workspace_id,
        account_id=account_id,
        contact_id=contact_id,
    )
```

- [ ] **Step 4: Run backend tests**

Run:

```powershell
uv run pytest tests/api/routes/test_accounts.py tests/api/routes/test_customer_360.py tests/domain/test_accounts_service.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add apps/api/app/domain/accounts/service.py apps/api/app/api/routes/accounts.py apps/api/tests/api/routes/test_accounts.py
git commit -m "feat: manage account contacts"
```

## Task 4: Frontend Account Create/Edit Dialog

**Files:**
- Modify: `apps/web/src/features/customer-360/api.ts`
- Create: `apps/web/src/features/customer-360/AccountFormDialog.tsx`
- Modify: `apps/web/src/features/customer-360/Customer360AccountsPage.tsx`
- Modify: `apps/web/src/features/customer-360/Customer360AccountProfilePage.tsx`
- Test: `apps/web/tests/customer-360.spec.ts`

- [ ] **Step 1: Add failing Playwright tests**

Extend `customer-360.spec.ts` with mocked routes for `POST /api/v1/accounts` and `PATCH /api/v1/accounts/{id}`. Test that the list page opens a `New account` dialog, submits `Analytical Health`, and navigates to `/customer-360/<new-id>`. Test that the profile page opens `Edit account`, changes industry, and shows refreshed account metadata.

- [ ] **Step 2: Add API client functions**

Add `createAccount(input)` and `updateAccount(accountId, input)` to `api.ts`, using `engagehubRequest` with JSON bodies.

- [ ] **Step 3: Add `AccountFormDialog`**

Create a controlled dialog component with fields for name, website, industry, status, summary, and comma-separated tags. It receives `mode`, optional `account`, `open`, `onOpenChange`, and `onSaved`.

- [ ] **Step 4: Wire create/edit into pages**

Add `New account` to the list header. On create, refresh the list and navigate to the new profile. Add `Edit account` to the profile header. On edit, reload the profile.

- [ ] **Step 5: Run frontend tests and commit**

```powershell
npx playwright test tests/customer-360.spec.ts --project=chromium --reporter=line
git add apps/web/src/features/customer-360 apps/web/tests/customer-360.spec.ts
git commit -m "feat: add account create edit ui"
```

## Task 5: Frontend Contact Assignment Dialog

**Files:**
- Modify: `apps/web/src/features/customer-360/api.ts`
- Create: `apps/web/src/features/customer-360/AssignContactsDialog.tsx`
- Modify: `apps/web/src/features/customer-360/Customer360AccountProfilePage.tsx`
- Test: `apps/web/tests/customer-360.spec.ts`

- [ ] **Step 1: Add failing Playwright assignment tests**

Mock `GET /api/v1/contacts/`, `POST /api/v1/accounts/{id}/contacts`, and `DELETE /api/v1/accounts/{id}/contacts/{contactId}`. Assert the profile can assign one available contact and can unlink an existing contact.

- [ ] **Step 2: Add API client functions**

Add `listContacts(search)`, `assignContactsToAccount(accountId, contactIds)`, and `unassignContactFromAccount(accountId, contactId)` to `api.ts`.

- [ ] **Step 3: Add assignment dialog**

Create `AssignContactsDialog.tsx` with search input, checkbox rows, selected count, and disabled assign button when nothing is selected.

- [ ] **Step 4: Wire assignment into profile**

Add `Assign contacts` beside the contacts panel title. Add an unlink icon button to each contact row. Refresh the profile after each mutation.

- [ ] **Step 5: Run frontend tests and commit**

```powershell
npx playwright test tests/customer-360.spec.ts --project=chromium --reporter=line
git add apps/web/src/features/customer-360 apps/web/tests/customer-360.spec.ts
git commit -m "feat: assign contacts to accounts"
```

## Task 6: Final Verification

**Files:**
- Verify all touched files.

- [ ] **Step 1: Backend verification**

```powershell
uv run pytest tests/api/routes/test_accounts.py tests/api/routes/test_customer_360.py tests/domain/test_accounts_service.py
```

Expected: all tests pass.

- [ ] **Step 2: Frontend verification**

```powershell
npx playwright test tests/customer-360.spec.ts --project=chromium --reporter=line
npm run build
```

Expected: Customer 360 Playwright tests pass and Vite build succeeds.

- [ ] **Step 3: Live smoke**

With Postgres/API/web running, log in as `admin@example.com`, open `/customer-360`, create a test account, edit it, assign an existing contact, unlink it, and confirm no console errors.

- [ ] **Step 4: Final status**

```powershell
git status --short
git diff --check
```

Expected: clean status after final commit and no whitespace errors.
