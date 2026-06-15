# Customer 360 Account Profile Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a first-class account-based Customer 360 profile that combines contacts, chatbot, email, voice, prospecting, next actions, open work, and account timeline activity.

**Architecture:** Add an `accounts` table and attach contacts through `contacts.account_id`. Implement Customer 360 as a backend read service over account-scoped contacts and existing channel tables, then render it through new account list/detail routes in the frontend.

**Tech Stack:** FastAPI, SQLModel, Alembic, pytest, React, TanStack Router, Vite, Playwright, PowerShell.

---

## Preflight

The worktree may contain unrelated user changes. At the time this plan was written, `tooling/engagehub-release-check.ps1` was modified and unrelated to Customer 360. Do not stage or commit that file unless the user explicitly asks.

Run before Task 1:

```powershell
git status --short
```

Expected: no Customer 360 implementation files are modified yet. Unrelated modified files can remain unstaged.

Run before creating the migration:

```powershell
uv run alembic heads
```

Expected current head for the main schema line includes `u6j7k8l9m0n1`. If a newer migration exists, set the Customer 360 migration `down_revision` to that newer head instead of `u6j7k8l9m0n1`.

## File Structure

Backend files:

- Modify `apps/api/app/domain_models.py`: add `Account`, `AccountPublic`, list/detail public schemas, and `Contact.account_id`.
- Modify `apps/api/app/models.py`: import `Account` so SQLModel metadata includes the table.
- Create `apps/api/app/domain/accounts/__init__.py`: package marker.
- Create `apps/api/app/domain/accounts/service.py`: account key generation, find/create account for a company name, and account public conversion.
- Create `apps/api/app/domain/customer_360/__init__.py`: package marker.
- Create `apps/api/app/domain/customer_360/service.py`: account list/detail aggregation service.
- Create `apps/api/app/api/routes/customer_360.py`: `/customer-360/accounts` API routes.
- Modify `apps/api/app/api/main.py`: include the Customer 360 router.
- Modify `apps/api/app/api/routes/contacts.py`: attach imported contacts to accounts.
- Create `apps/api/app/alembic/versions/v7k8l9m0n1o2_add_accounts_and_customer_360.py`: accounts migration and backfill.

Backend tests:

- Create `apps/api/tests/domain/test_accounts_service.py`.
- Modify `apps/api/tests/api/routes/test_contacts.py`.
- Create `apps/api/tests/unit/test_customer_360_service.py`.
- Create `apps/api/tests/api/routes/test_customer_360.py`.

Frontend files:

- Create `apps/web/src/features/customer-360/api.ts`.
- Create `apps/web/src/features/customer-360/Customer360AccountsPage.tsx`.
- Create `apps/web/src/features/customer-360/Customer360AccountProfilePage.tsx`.
- Create `apps/web/src/routes/_layout/customer-360.tsx`.
- Create `apps/web/src/routes/_layout/customer-360.$accountId.tsx`.
- Modify `apps/web/src/components/Sidebar/AppSidebar.tsx`: add Customer 360 navigation item.
- Do not hand-edit `apps/web/src/routeTree.gen.ts`; run the frontend build and commit generated route-tree changes if the router plugin updates it.

Frontend tests:

- Create `apps/web/tests/customer-360.spec.ts`.

## Task 1: Account Domain Model And Service

**Files:**
- Modify: `apps/api/app/domain_models.py`
- Modify: `apps/api/app/models.py`
- Create: `apps/api/app/domain/accounts/__init__.py`
- Create: `apps/api/app/domain/accounts/service.py`
- Test: `apps/api/tests/domain/test_accounts_service.py`

- [ ] **Step 1: Write failing account service tests**

Create `apps/api/tests/domain/test_accounts_service.py`:

```python
from __future__ import annotations

from sqlmodel import Session, SQLModel, create_engine, select

from app.domain.accounts.service import (
    account_to_public,
    find_or_create_account_for_company,
    generate_account_key,
)
from app.domain_models import Account


def _session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def test_generate_account_key_normalizes_company_name() -> None:
    assert generate_account_key("  Analytical Health, Inc.  ") == "analytical-health-inc"
    assert generate_account_key("ACME___Clinic!!!") == "acme-clinic"


def test_find_or_create_account_reuses_account_by_workspace_and_key() -> None:
    with _session() as session:
        first = find_or_create_account_for_company(
            session,
            workspace_id="ws-a",
            company_name="Analytical Health, Inc.",
        )
        second = find_or_create_account_for_company(
            session,
            workspace_id="ws-a",
            company_name="Analytical Health Inc",
        )
        other_workspace = find_or_create_account_for_company(
            session,
            workspace_id="ws-b",
            company_name="Analytical Health Inc",
        )
        session.commit()

        accounts = session.exec(select(Account)).all()

    assert first.id == second.id
    assert other_workspace.id != first.id
    assert len(accounts) == 2
    assert first.name == "Analytical Health, Inc."
    assert first.account_key == "analytical-health-inc"


def test_find_or_create_account_ignores_blank_company() -> None:
    with _session() as session:
        account = find_or_create_account_for_company(
            session,
            workspace_id="ws-a",
            company_name=" ",
        )

    assert account is None


def test_account_to_public_maps_fields() -> None:
    account = Account(
        workspace_id="ws-a",
        name="Analytical Health",
        account_key="analytical-health",
        website_url="https://analytical.example",
        industry="Healthcare",
        status="active",
        summary="Multi-location buyer.",
        tags_json=["pricing", "voice-ready"],
    )

    public = account_to_public(account)

    assert public.name == "Analytical Health"
    assert public.website_url == "https://analytical.example"
    assert public.tags == ["pricing", "voice-ready"]
```

- [ ] **Step 2: Run the failing account service tests**

Run:

```powershell
uv run pytest apps/api/tests/domain/test_accounts_service.py -q
```

Expected: FAIL because `app.domain.accounts.service` or `Account` is not defined.

- [ ] **Step 3: Add `Account` model and public schema**

In `apps/api/app/domain_models.py`, add imports if missing:

```python
from sqlalchemy import Column, DateTime, Index, JSON, String, Text, UniqueConstraint
```

Add this model near `Contact`:

```python
class Account(SQLModel, table=True):
    """First-class customer account."""

    __tablename__ = "accounts"
    __table_args__ = (
        UniqueConstraint("workspace_id", "account_key", name="uq_account_workspace_key"),
        Index("idx_accounts_workspace_name", "workspace_id", "name"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workspace_id: str = Field(sa_type=String(64), index=True)
    name: str = Field(sa_type=String(255))
    account_key: str = Field(sa_type=String(255), index=True)
    website_url: str | None = Field(default=None, sa_type=Text)
    industry: str | None = Field(default=None, max_length=255)
    status: str = Field(default="active", max_length=64)
    summary: str | None = Field(default=None, sa_type=Text)
    tags_json: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))
    updated_at: datetime = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))
```

Add `account_id` to `Contact`:

```python
    account_id: uuid.UUID | None = Field(default=None, foreign_key="accounts.id", index=True)
```

Add public schemas near `ContactPublic`:

```python
class AccountPublic(SQLModel):
    """API response model: account."""

    id: uuid.UUID
    workspace_id: str
    name: str
    account_key: str
    website_url: str | None = None
    industry: str | None = None
    status: str
    summary: str | None = None
    tags: list[str] = []
    created_at: datetime
    updated_at: datetime
```

Add `account_id` to `ContactPublic`:

```python
    account_id: uuid.UUID | None = None
```

In `apps/api/app/models.py`, add `Account` to the `from app.domain_models import (...)` block.

- [ ] **Step 4: Add account service implementation**

Create `apps/api/app/domain/accounts/__init__.py`:

```python
"""Account domain package."""
```

Create `apps/api/app/domain/accounts/service.py`:

```python
from __future__ import annotations

import re

from sqlmodel import Session, select

from app.domain_models import Account, AccountPublic


def generate_account_key(name: str) -> str:
    """Return a deterministic account key for a display name."""
    normalized = re.sub(r"[^a-z0-9]+", "-", name.strip().lower())
    return normalized.strip("-")


def find_or_create_account_for_company(
    session: Session,
    *,
    workspace_id: str,
    company_name: str | None,
) -> Account | None:
    """Find or create an account from a contact company name."""
    name = (company_name or "").strip()
    if not name:
        return None
    account_key = generate_account_key(name)
    if not account_key:
        return None

    account = session.exec(
        select(Account).where(
            Account.workspace_id == workspace_id,
            Account.account_key == account_key,
        )
    ).first()
    if account is not None:
        return account

    account = Account(
        workspace_id=workspace_id,
        name=name,
        account_key=account_key,
    )
    session.add(account)
    session.flush()
    return account


def account_to_public(account: Account) -> AccountPublic:
    """Map an Account row to the public schema."""
    return AccountPublic(
        id=account.id,
        workspace_id=account.workspace_id,
        name=account.name,
        account_key=account.account_key,
        website_url=account.website_url,
        industry=account.industry,
        status=account.status,
        summary=account.summary,
        tags=account.tags_json or [],
        created_at=account.created_at,
        updated_at=account.updated_at,
    )
```

- [ ] **Step 5: Run account service tests**

Run:

```powershell
uv run pytest apps/api/tests/domain/test_accounts_service.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit account model and service**

Run:

```powershell
git add apps/api/app/domain_models.py apps/api/app/models.py apps/api/app/domain/accounts/__init__.py apps/api/app/domain/accounts/service.py apps/api/tests/domain/test_accounts_service.py
git commit -m "Add account domain model and service"
```

## Task 2: Accounts Migration And Backfill

**Files:**
- Create: `apps/api/app/alembic/versions/v7k8l9m0n1o2_add_accounts_and_customer_360.py`

- [ ] **Step 1: Create the migration file**

Create `apps/api/app/alembic/versions/v7k8l9m0n1o2_add_accounts_and_customer_360.py`:

```python
"""add accounts and customer 360

Revision ID: v7k8l9m0n1o2
Revises: u6j7k8l9m0n1
Create Date: 2026-06-08 00:00:00.000000
"""

from __future__ import annotations

import re
import uuid

import sqlalchemy as sa
from alembic import op

revision: str = "v7k8l9m0n1o2"
down_revision: str | tuple[str, ...] | None = "u6j7k8l9m0n1"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def _account_key(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.strip().lower())
    return normalized.strip("-")


def upgrade() -> None:
    op.create_table(
        "accounts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("account_key", sa.String(length=255), nullable=False),
        sa.Column("website_url", sa.Text(), nullable=True),
        sa.Column("industry", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=False, server_default="active"),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("tags_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "account_key", name="uq_account_workspace_key"),
    )
    op.create_index("ix_accounts_workspace_id", "accounts", ["workspace_id"])
    op.create_index("ix_accounts_account_key", "accounts", ["account_key"])
    op.create_index("idx_accounts_workspace_name", "accounts", ["workspace_id", "name"])

    op.add_column("contacts", sa.Column("account_id", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_contacts_account_id_accounts", "contacts", "accounts", ["account_id"], ["id"])
    op.create_index("ix_contacts_account_id", "contacts", ["account_id"])

    bind = op.get_bind()
    contact_rows = bind.execute(
        sa.text(
            """
            SELECT workspace_id, company
            FROM contacts
            WHERE company IS NOT NULL AND trim(company) <> ''
            GROUP BY workspace_id, company
            """
        )
    ).mappings()
    account_ids: dict[tuple[str, str], str] = {}
    for row in contact_rows:
        workspace_id = row["workspace_id"]
        company = row["company"].strip()
        key = _account_key(company)
        if not key:
            continue
        map_key = (workspace_id, key)
        if map_key in account_ids:
            continue
        account_id = str(uuid.uuid4())
        account_ids[map_key] = account_id
        bind.execute(
            sa.text(
                """
                INSERT INTO accounts (id, workspace_id, name, account_key, status, created_at, updated_at)
                VALUES (:id, :workspace_id, :name, :account_key, 'active', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """
            ),
            {
                "id": account_id,
                "workspace_id": workspace_id,
                "name": company,
                "account_key": key,
            },
        )

    contacts = bind.execute(
        sa.text(
            """
            SELECT id, workspace_id, company
            FROM contacts
            WHERE company IS NOT NULL AND trim(company) <> ''
            """
        )
    ).mappings()
    for contact in contacts:
        key = _account_key(contact["company"])
        account_id = account_ids.get((contact["workspace_id"], key))
        if account_id:
            bind.execute(
                sa.text("UPDATE contacts SET account_id = :account_id WHERE id = :contact_id"),
                {"account_id": account_id, "contact_id": contact["id"]},
            )


def downgrade() -> None:
    op.drop_index("ix_contacts_account_id", table_name="contacts")
    op.drop_constraint("fk_contacts_account_id_accounts", "contacts", type_="foreignkey")
    op.drop_column("contacts", "account_id")
    op.drop_index("idx_accounts_workspace_name", table_name="accounts")
    op.drop_index("ix_accounts_account_key", table_name="accounts")
    op.drop_index("ix_accounts_workspace_id", table_name="accounts")
    op.drop_table("accounts")
```

- [ ] **Step 2: Validate migration syntax**

Run:

```powershell
uv run python -m py_compile apps/api/app/alembic/versions/v7k8l9m0n1o2_add_accounts_and_customer_360.py
```

Expected: no output and exit code 0.

- [ ] **Step 3: Run account service tests after migration file exists**

Run:

```powershell
uv run pytest apps/api/tests/domain/test_accounts_service.py -q
```

Expected: PASS.

- [ ] **Step 4: Commit migration**

Run:

```powershell
git add apps/api/app/alembic/versions/v7k8l9m0n1o2_add_accounts_and_customer_360.py
git commit -m "Add accounts migration"
```

## Task 3: Contact Import Account Assignment

**Files:**
- Modify: `apps/api/app/api/routes/contacts.py`
- Modify: `apps/api/tests/api/routes/test_contacts.py`

- [ ] **Step 1: Extend contact import test to assert account assignment**

In `apps/api/tests/api/routes/test_contacts.py`, update imports:

```python
from app.domain_models import Account, Contact, ContactProgression
```

At the end of `test_contact_import_preview_and_commit`, after asserting `contact["phone"]`, add:

```python
    persisted = db.exec(select(Contact).where(Contact.email == email)).first()
    assert persisted is not None
    assert persisted.account_id is not None
    account = db.get(Account, persisted.account_id)
    assert account is not None
    assert account.workspace_id == workspace_id
    assert account.name == "Analytical"
    assert account.account_key == "analytical"
```

Add `db: Session` to that test signature:

```python
def test_contact_import_preview_and_commit(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
```

- [ ] **Step 2: Run contact import test to verify it fails**

Run:

```powershell
uv run pytest apps/api/tests/api/routes/test_contacts.py::test_contact_import_preview_and_commit -q
```

Expected: FAIL because imported contacts do not set `account_id`.

- [ ] **Step 3: Attach accounts during contact upsert**

In `apps/api/app/api/routes/contacts.py`, add:

```python
from app.domain.accounts.service import find_or_create_account_for_company
```

Inside `_upsert_contacts`, before setting contact fields, add:

```python
        account = find_or_create_account_for_company(
            session,
            workspace_id=workspace_id,
            company_name=row.get("company"),
        )
```

Then set contact account fields:

```python
        if account is not None:
            contact.account_id = account.id
            contact.company = account.name
        else:
            contact.company = row.get("company") or contact.company
```

Replace the existing company assignment:

```python
        contact.company = row.get("company") or contact.company
```

with the conditional assignment above. Keep first name, last name, phone, and timezone assignments unchanged.

- [ ] **Step 4: Run the contact import test**

Run:

```powershell
uv run pytest apps/api/tests/api/routes/test_contacts.py::test_contact_import_preview_and_commit -q
```

Expected: PASS.

- [ ] **Step 5: Run account service tests**

Run:

```powershell
uv run pytest apps/api/tests/domain/test_accounts_service.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit contact import account assignment**

Run:

```powershell
git add apps/api/app/api/routes/contacts.py apps/api/tests/api/routes/test_contacts.py
git commit -m "Attach imported contacts to accounts"
```

## Task 4: Customer 360 Backend Read Service

**Files:**
- Create: `apps/api/app/domain/customer_360/__init__.py`
- Create: `apps/api/app/domain/customer_360/service.py`
- Modify: `apps/api/app/domain_models.py`
- Test: `apps/api/tests/unit/test_customer_360_service.py`

- [ ] **Step 1: Write failing Customer 360 service tests**

Create `apps/api/tests/unit/test_customer_360_service.py`:

```python
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, SQLModel, create_engine

from app.domain.chatbot.models import (
    ChatbotChannelType,
    ChatbotConversation,
    ChatbotConversationStatus,
    ChatbotMessage,
    ChatbotMessageDirection,
    ChatbotMessageSender,
)
from app.domain.customer_360.service import get_account_profile, list_customer_360_accounts
from app.domain.sequences.models import ContactSequenceState, EmailEvent, EmailSequence, SendRequest, SendRequestStatus
from app.domain.voice.models import CallOutcome, CallRequest, CallSession, VoiceScript
from app.domain_models import Account, Campaign, Contact, ProspectingSnapshot


def _session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def _seed_account(session: Session, *, workspace_id: str = "ws-a") -> tuple[Account, Contact, Contact]:
    owner_id = uuid.uuid4()
    account = Account(
        workspace_id=workspace_id,
        name="Analytical Health",
        account_key="analytical-health",
        summary="Multi-location healthcare buyer.",
        tags_json=["pricing", "voice-ready"],
    )
    session.add(account)
    session.flush()

    ada = Contact(
        workspace_id=workspace_id,
        account_id=account.id,
        email="ada@example.com",
        first_name="Ada",
        last_name="Lovelace",
        company="Analytical Health",
        phone="+15551234567",
    )
    grace = Contact(
        workspace_id=workspace_id,
        account_id=account.id,
        email="grace@example.com",
        first_name="Grace",
        last_name="Hopper",
        company="Analytical Health",
    )
    session.add(ada)
    session.add(grace)
    session.flush()

    campaign = Campaign(name="Q2 Outreach", workspace_id=workspace_id, created_by=owner_id)
    session.add(campaign)
    session.flush()

    conversation = ChatbotConversation(
        workspace_id=workspace_id,
        channel_type=ChatbotChannelType.whatsapp_business,
        visitor_id="visitor-ada",
        contact_id=ada.id,
        status=ChatbotConversationStatus.escalated,
        escalated=True,
        escalation_reason="Pricing question needs a human",
        last_message_at=datetime.now(timezone.utc) - timedelta(minutes=20),
    )
    session.add(conversation)
    session.flush()
    session.add(
        ChatbotMessage(
            workspace_id=workspace_id,
            conversation_id=conversation.id,
            direction=ChatbotMessageDirection.inbound,
            sender=ChatbotMessageSender.visitor,
            content="Can you explain pricing for three locations?",
            created_at=datetime.now(timezone.utc) - timedelta(minutes=20),
        )
    )

    script = VoiceScript(campaign_id=campaign.id, name="Discovery", content="Hi.", created_by=owner_id)
    session.add(script)
    session.flush()
    call_request = CallRequest(
        contact_id=ada.id,
        campaign_id=campaign.id,
        voice_script_id=script.id,
        trigger_reason="manual_test_call",
        scheduled_at=datetime.now(timezone.utc) - timedelta(minutes=15),
    )
    session.add(call_request)
    session.flush()
    session.add(
        CallSession(
            call_request_id=call_request.id,
            outcome=CallOutcome.answered,
            duration_seconds=96,
            transcript="Ada needs implementation pricing clarity before booking.",
            unanswered_questions={"questions": ["implementation pricing clarity"]},
            scheduling_interest=True,
            created_at=datetime.now(timezone.utc) - timedelta(minutes=12),
        )
    )

    sequence = EmailSequence(campaign_id=campaign.id, name="Welcome", active=True, created_by=owner_id)
    session.add(sequence)
    session.flush()
    sequence_state = ContactSequenceState(contact_id=grace.id, sequence_id=sequence.id)
    session.add(sequence_state)
    session.flush()
    send_request = SendRequest(
        contact_sequence_state_id=sequence_state.id,
        step_order=1,
        idempotency_key=f"{workspace_id}-grace-step-1",
        status=SendRequestStatus.sent,
        sent_at=datetime.now(timezone.utc) - timedelta(days=1),
    )
    session.add(send_request)
    session.flush()
    session.add(
        EmailEvent(
            send_request_id=send_request.id,
            event_type="opened",
            timestamp=datetime.now(timezone.utc) - timedelta(hours=23),
        )
    )

    session.add(
        ProspectingSnapshot(
            workspace_id=workspace_id,
            contact_id=ada.id,
            company_url="https://analytical.example",
            sources_json=[{"label": "CRM contact", "summary": "Ada at Analytical Health"}],
            research_json={
                "account_summary": "Analytical Health is evaluating cross-channel outreach.",
                "suggested_next_action": "Reply with pricing clarity, then queue a call.",
            },
            email_draft="Subject: Analytical Health follow-up",
            voice_opener="Hi Ada, following up on pricing.",
            created_at=datetime.now(timezone.utc) - timedelta(days=2),
        )
    )
    session.commit()
    return account, ada, grace


def test_list_customer_360_accounts_returns_account_rollups() -> None:
    with _session() as session:
        account, _ada, _grace = _seed_account(session)

        result = list_customer_360_accounts(session, workspace_id="ws-a")

    assert result.count == 1
    row = result.data[0]
    assert row.id == account.id
    assert row.name == "Analytical Health"
    assert row.contact_count == 2
    assert row.channel_counts["chatbot"] == 1
    assert row.channel_counts["email"] == 1
    assert row.channel_counts["voice"] == 1
    assert row.channel_counts["prospecting"] == 1
    assert row.top_next_action == "Reply with pricing clarity, then queue a call."


def test_get_account_profile_aggregates_contacts_channels_and_timeline() -> None:
    with _session() as session:
        account, ada, grace = _seed_account(session)

        profile = get_account_profile(session, workspace_id="ws-a", account_id=account.id)

    assert profile.account.id == account.id
    assert {contact.email for contact in profile.contacts} == {"ada@example.com", "grace@example.com"}
    assert profile.channel_summaries["chatbot"].count == 1
    assert profile.channel_summaries["email"].count == 1
    assert profile.channel_summaries["voice"].count == 1
    assert profile.channel_summaries["prospecting"].count == 1
    assert profile.next_best_action is not None
    assert profile.next_best_action.title == "Reply with pricing clarity, then queue a call"
    assert profile.prospecting_brief is not None
    assert profile.prospecting_brief.account_summary == "Analytical Health is evaluating cross-channel outreach."
    assert {event.contact_id for event in profile.timeline} == {ada.id, grace.id}
    assert [event.timestamp for event in profile.timeline] == sorted(
        [event.timestamp for event in profile.timeline],
        reverse=True,
    )


def test_get_account_profile_returns_none_for_wrong_workspace() -> None:
    with _session() as session:
        account, _ada, _grace = _seed_account(session)

        profile = get_account_profile(session, workspace_id="ws-b", account_id=account.id)

    assert profile is None
```

- [ ] **Step 2: Run Customer 360 service tests to verify they fail**

Run:

```powershell
uv run pytest apps/api/tests/unit/test_customer_360_service.py -q
```

Expected: FAIL because `app.domain.customer_360.service` and Customer 360 schemas are not defined.

- [ ] **Step 3: Add Customer 360 public schemas**

In `apps/api/app/domain_models.py`, add these schemas after `AccountPublic`:

```python
class Customer360AccountRowPublic(AccountPublic):
    """Customer 360 account list row."""

    contact_count: int
    last_activity_at: datetime | None = None
    channel_counts: dict[str, int]
    top_next_action: str | None = None


class Customer360AccountsPublic(SQLModel):
    """Customer 360 account list response."""

    data: list[Customer360AccountRowPublic]
    count: int


class Customer360ContactPublic(ContactPublic):
    """Contact shown inside a Customer 360 account."""

    display_name: str


class Customer360ChannelSummaryPublic(SQLModel):
    """One channel summary card."""

    channel: str
    label: str
    count: int
    status: str
    detail: str


class Customer360NextActionPublic(SQLModel):
    """Recommended account-level follow-up."""

    title: str
    reason: str
    source: str
    priority: str


class Customer360OpenWorkPublic(SQLModel):
    """Open work item for an account."""

    id: str
    source: str
    title: str
    contact_id: uuid.UUID | None = None
    contact_name: str | None = None
    status: str
    created_at: datetime


class Customer360ProspectingBriefPublic(SQLModel):
    """Latest prospecting brief for an account."""

    snapshot_id: uuid.UUID
    contact_id: uuid.UUID
    account_summary: str
    suggested_next_action: str | None = None
    email_draft_available: bool
    voice_opener_available: bool
    created_at: datetime


class Customer360TimelineEventPublic(SQLModel):
    """Account-level timeline event."""

    id: str
    source: str
    event_type: str
    title: str
    detail: str
    contact_id: uuid.UUID | None = None
    contact_name: str | None = None
    timestamp: datetime


class Customer360AccountProfilePublic(SQLModel):
    """Full Account Command Center payload."""

    account: AccountPublic
    contacts: list[Customer360ContactPublic]
    channel_summaries: dict[str, Customer360ChannelSummaryPublic]
    next_best_action: Customer360NextActionPublic | None = None
    open_work: list[Customer360OpenWorkPublic]
    prospecting_brief: Customer360ProspectingBriefPublic | None = None
    timeline: list[Customer360TimelineEventPublic]
```

- [ ] **Step 4: Add Customer 360 service implementation**

Create `apps/api/app/domain/customer_360/__init__.py`:

```python
"""Customer 360 domain package."""
```

Create `apps/api/app/domain/customer_360/service.py` with focused helpers:

```python
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func
from sqlmodel import Session, select

from app.domain.accounts.service import account_to_public
from app.domain.chatbot.models import ChatbotConversation, ChatbotConversationStatus, ChatbotMessage
from app.domain.sequences.models import ContactSequenceState, EmailEvent, SendRequest
from app.domain.voice.models import CallRequest, CallSession
from app.domain_models import (
    Account,
    Contact,
    Customer360AccountProfilePublic,
    Customer360AccountRowPublic,
    Customer360AccountsPublic,
    Customer360ChannelSummaryPublic,
    Customer360ContactPublic,
    Customer360NextActionPublic,
    Customer360OpenWorkPublic,
    Customer360ProspectingBriefPublic,
    Customer360TimelineEventPublic,
    ProspectingSnapshot,
)


def _contact_name(contact: Contact) -> str:
    name = f"{contact.first_name or ''} {contact.last_name or ''}".strip()
    return name or contact.email


def _contact_public(contact: Contact) -> Customer360ContactPublic:
    return Customer360ContactPublic(
        id=contact.id,
        workspace_id=contact.workspace_id,
        account_id=contact.account_id,
        email=contact.email,
        first_name=contact.first_name,
        last_name=contact.last_name,
        company=contact.company,
        phone=contact.phone,
        timezone=contact.timezone,
        created_at=contact.created_at,
        display_name=_contact_name(contact),
    )


def _status_value(value: object) -> str:
    return str(getattr(value, "value", value) or "unknown")


def _latest_message(session: Session, conversation: ChatbotConversation) -> ChatbotMessage | None:
    return session.exec(
        select(ChatbotMessage)
        .where(ChatbotMessage.conversation_id == conversation.id)
        .order_by(ChatbotMessage.created_at.desc())
    ).first()


def _snapshot_summary(snapshot: ProspectingSnapshot) -> str:
    value = (snapshot.research_json or {}).get("account_summary")
    return value if isinstance(value, str) and value.strip() else "Prospecting research is ready."


def _snapshot_next_action(snapshot: ProspectingSnapshot) -> str | None:
    value = (snapshot.research_json or {}).get("suggested_next_action")
    return value if isinstance(value, str) and value.strip() else None


def _load_contacts(session: Session, *, workspace_id: str, account_id: uuid.UUID) -> list[Contact]:
    return list(
        session.exec(
            select(Contact)
            .where(Contact.workspace_id == workspace_id, Contact.account_id == account_id)
            .order_by(Contact.created_at.desc())
        ).all()
    )


def _empty_summary(channel: str, label: str) -> Customer360ChannelSummaryPublic:
    return Customer360ChannelSummaryPublic(
        channel=channel,
        label=label,
        count=0,
        status="empty",
        detail="No activity yet.",
    )


def list_customer_360_accounts(
    session: Session,
    *,
    workspace_id: str,
    search: str | None = None,
    limit: int = 50,
) -> Customer360AccountsPublic:
    stmt = select(Account).where(Account.workspace_id == workspace_id).order_by(Account.name)
    if search and search.strip():
        stmt = stmt.where(Account.name.ilike(f"%{search.strip()}%"))
    accounts = list(session.exec(stmt.limit(limit)).all())
    rows: list[Customer360AccountRowPublic] = []
    for account in accounts:
        contacts = _load_contacts(session, workspace_id=workspace_id, account_id=account.id)
        contact_ids = [contact.id for contact in contacts]
        profile = _build_profile_parts(session, account=account, contacts=contacts, contact_ids=contact_ids)
        public = account_to_public(account)
        rows.append(
            Customer360AccountRowPublic(
                **public.model_dump(),
                contact_count=len(contacts),
                last_activity_at=profile["last_activity_at"],
                channel_counts={key: value.count for key, value in profile["channel_summaries"].items()},
                top_next_action=profile["next_best_action"].title if profile["next_best_action"] else None,
            )
        )
    return Customer360AccountsPublic(data=rows, count=len(rows))


def get_account_profile(
    session: Session,
    *,
    workspace_id: str,
    account_id: uuid.UUID,
) -> Customer360AccountProfilePublic | None:
    account = session.exec(
        select(Account).where(Account.id == account_id, Account.workspace_id == workspace_id)
    ).first()
    if account is None:
        return None
    contacts = _load_contacts(session, workspace_id=workspace_id, account_id=account.id)
    contact_ids = [contact.id for contact in contacts]
    parts = _build_profile_parts(session, account=account, contacts=contacts, contact_ids=contact_ids)
    return Customer360AccountProfilePublic(
        account=account_to_public(account),
        contacts=[_contact_public(contact) for contact in contacts],
        channel_summaries=parts["channel_summaries"],
        next_best_action=parts["next_best_action"],
        open_work=parts["open_work"],
        prospecting_brief=parts["prospecting_brief"],
        timeline=parts["timeline"],
    )


def _build_profile_parts(
    session: Session,
    *,
    account: Account,
    contacts: list[Contact],
    contact_ids: list[uuid.UUID],
) -> dict[str, object]:
    if not contact_ids:
        return {
            "channel_summaries": {
                "chatbot": _empty_summary("chatbot", "Chatbot"),
                "email": _empty_summary("email", "Email"),
                "voice": _empty_summary("voice", "Voice"),
                "prospecting": _empty_summary("prospecting", "Prospecting"),
            },
            "next_best_action": None,
            "open_work": [],
            "prospecting_brief": None,
            "timeline": [],
            "last_activity_at": None,
        }

    contact_map = {contact.id: contact for contact in contacts}
    conversations = list(
        session.exec(
            select(ChatbotConversation)
            .where(ChatbotConversation.contact_id.in_(contact_ids), ChatbotConversation.deleted_at.is_(None))
            .order_by(ChatbotConversation.last_message_at.desc())
        ).all()
    )
    call_rows = list(
        session.exec(
            select(CallRequest, CallSession)
            .outerjoin(CallSession, CallRequest.id == CallSession.call_request_id)
            .where(CallRequest.contact_id.in_(contact_ids))
            .order_by(CallRequest.created_at.desc())
        ).all()
    )
    sequence_states = list(
        session.exec(
            select(ContactSequenceState)
            .where(ContactSequenceState.contact_id.in_(contact_ids))
            .order_by(ContactSequenceState.created_at.desc())
        ).all()
    )
    snapshots = list(
        session.exec(
            select(ProspectingSnapshot)
            .where(ProspectingSnapshot.contact_id.in_(contact_ids))
            .order_by(ProspectingSnapshot.created_at.desc())
        ).all()
    )

    send_count = 0
    opened_count = 0
    if sequence_states:
        state_ids = [state.id for state in sequence_states]
        send_requests = list(
            session.exec(select(SendRequest).where(SendRequest.contact_sequence_state_id.in_(state_ids))).all()
        )
        send_count = len(send_requests)
        if send_requests:
            send_ids = [send.id for send in send_requests]
            opened_count = int(
                session.exec(
                    select(func.count(EmailEvent.id)).where(
                        EmailEvent.send_request_id.in_(send_ids),
                        EmailEvent.event_type.in_(["opened", "clicked"]),
                    )
                ).one()
            )

    channel_summaries = {
        "chatbot": Customer360ChannelSummaryPublic(
            channel="chatbot",
            label="Chatbot",
            count=len(conversations),
            status="active" if conversations else "empty",
            detail=f"{len([item for item in conversations if item.escalated])} escalated thread(s)",
        ),
        "email": Customer360ChannelSummaryPublic(
            channel="email",
            label="Email",
            count=send_count,
            status="active" if send_count else "empty",
            detail=f"{opened_count} open or click event(s)",
        ),
        "voice": Customer360ChannelSummaryPublic(
            channel="voice",
            label="Voice",
            count=len(call_rows),
            status="active" if call_rows else "empty",
            detail=f"{len([row for row in call_rows if row[1] and row[1].scheduling_interest])} follow-up call(s)",
        ),
        "prospecting": Customer360ChannelSummaryPublic(
            channel="prospecting",
            label="Prospecting",
            count=len(snapshots),
            status="ready" if snapshots else "empty",
            detail="Latest brief has drafts." if snapshots else "No research brief yet.",
        ),
    }

    open_work: list[Customer360OpenWorkPublic] = []
    timeline: list[Customer360TimelineEventPublic] = []

    for conversation in conversations:
        contact = contact_map.get(conversation.contact_id) if conversation.contact_id else None
        message = _latest_message(session, conversation)
        timestamp = conversation.last_message_at or conversation.created_at
        if conversation.escalated or conversation.status in {
            ChatbotConversationStatus.open,
            ChatbotConversationStatus.agent_active,
            ChatbotConversationStatus.bot_paused,
        }:
            open_work.append(
                Customer360OpenWorkPublic(
                    id=f"chatbot-{conversation.id}",
                    source="chatbot",
                    title="Chatbot escalation" if conversation.escalated else "Open chatbot thread",
                    contact_id=conversation.contact_id,
                    contact_name=_contact_name(contact) if contact else None,
                    status=_status_value(conversation.status),
                    created_at=timestamp,
                )
            )
        timeline.append(
            Customer360TimelineEventPublic(
                id=f"chatbot-{conversation.id}",
                source="chatbot",
                event_type="chatbot_thread",
                title="Chatbot escalation" if conversation.escalated else "Chatbot conversation",
                detail=conversation.escalation_reason or (message.content if message else "Chatbot activity"),
                contact_id=conversation.contact_id,
                contact_name=_contact_name(contact) if contact else None,
                timestamp=timestamp,
            )
        )

    for call_request, call_session in call_rows:
        contact = contact_map.get(call_request.contact_id)
        timestamp = call_session.created_at if call_session else call_request.created_at
        if call_session and call_session.scheduling_interest:
            open_work.append(
                Customer360OpenWorkPublic(
                    id=f"voice-{call_request.id}",
                    source="voice",
                    title="Voice follow-up",
                    contact_id=call_request.contact_id,
                    contact_name=_contact_name(contact) if contact else None,
                    status=_status_value(call_session.outcome),
                    created_at=timestamp,
                )
            )
        timeline.append(
            Customer360TimelineEventPublic(
                id=f"voice-{call_request.id}",
                source="voice",
                event_type="call_session",
                title="Voice call completed" if call_session else "Voice call queued",
                detail=(call_session.transcript if call_session and call_session.transcript else call_request.trigger_reason),
                contact_id=call_request.contact_id,
                contact_name=_contact_name(contact) if contact else None,
                timestamp=timestamp,
            )
        )

    latest_snapshot = snapshots[0] if snapshots else None
    prospecting_brief = None
    if latest_snapshot:
        prospecting_brief = Customer360ProspectingBriefPublic(
            snapshot_id=latest_snapshot.id,
            contact_id=latest_snapshot.contact_id,
            account_summary=_snapshot_summary(latest_snapshot),
            suggested_next_action=_snapshot_next_action(latest_snapshot),
            email_draft_available=bool(latest_snapshot.email_draft.strip()),
            voice_opener_available=bool(latest_snapshot.voice_opener.strip()),
            created_at=latest_snapshot.created_at,
        )
        contact = contact_map.get(latest_snapshot.contact_id)
        timeline.append(
            Customer360TimelineEventPublic(
                id=f"prospecting-{latest_snapshot.id}",
                source="prospecting",
                event_type="prospecting_research",
                title="Prospecting research created",
                detail=_snapshot_summary(latest_snapshot),
                contact_id=latest_snapshot.contact_id,
                contact_name=_contact_name(contact) if contact else None,
                timestamp=latest_snapshot.created_at,
            )
        )

    next_best_action = None
    if open_work:
        first_work = sorted(open_work, key=lambda item: item.created_at, reverse=True)[0]
        next_best_action = Customer360NextActionPublic(
            title="Reply with pricing clarity, then queue a call" if first_work.source in {"chatbot", "voice"} else first_work.title,
            reason=f"{account.name} has open {first_work.source} work.",
            source=first_work.source,
            priority="high" if first_work.source in {"chatbot", "voice"} else "medium",
        )
    elif prospecting_brief and prospecting_brief.suggested_next_action:
        next_best_action = Customer360NextActionPublic(
            title=prospecting_brief.suggested_next_action,
            reason="Prospecting research is ready.",
            source="prospecting",
            priority="medium",
        )

    timeline = sorted(timeline, key=lambda event: event.timestamp, reverse=True)[:50]
    last_activity_at = timeline[0].timestamp if timeline else None

    return {
        "channel_summaries": channel_summaries,
        "next_best_action": next_best_action,
        "open_work": sorted(open_work, key=lambda item: item.created_at, reverse=True)[:12],
        "prospecting_brief": prospecting_brief,
        "timeline": timeline,
        "last_activity_at": last_activity_at,
    }
```

- [ ] **Step 5: Run Customer 360 service tests**

Run:

```powershell
uv run pytest apps/api/tests/unit/test_customer_360_service.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit Customer 360 service**

Run:

```powershell
git add apps/api/app/domain_models.py apps/api/app/domain/customer_360/__init__.py apps/api/app/domain/customer_360/service.py apps/api/tests/unit/test_customer_360_service.py
git commit -m "Add Customer 360 aggregation service"
```

## Task 5: Customer 360 API Routes

**Files:**
- Create: `apps/api/app/api/routes/customer_360.py`
- Modify: `apps/api/app/api/main.py`
- Test: `apps/api/tests/api/routes/test_customer_360.py`

- [ ] **Step 1: Write failing API route tests**

Create `apps/api/tests/api/routes/test_customer_360.py`:

```python
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
    account = Account(workspace_id=workspace_id, name="Analytical Health", account_key="analytical-health")
    db.add(account)
    db.flush()
    db.add(
        Contact(
            workspace_id=workspace_id,
            account_id=account.id,
            email=f"ada-{uuid.uuid4().hex[:6]}@example.com",
            first_name="Ada",
            last_name="Lovelace",
            company="Analytical Health",
            phone="+15551234567",
        )
    )
    db.commit()

    list_response = client.get(
        f"{settings.API_V1_STR}/customer-360/accounts",
        headers=_headers(superuser_token_headers, workspace_id),
    )
    assert list_response.status_code == 200
    list_payload = list_response.json()
    assert list_payload["count"] == 1
    assert list_payload["data"][0]["name"] == "Analytical Health"
    assert list_payload["data"][0]["contact_count"] == 1

    detail_response = client.get(
        f"{settings.API_V1_STR}/customer-360/accounts/{account.id}",
        headers=_headers(superuser_token_headers, workspace_id),
    )
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["account"]["name"] == "Analytical Health"
    assert detail["contacts"][0]["display_name"] == "Ada Lovelace"
    assert detail["channel_summaries"]["chatbot"]["count"] == 0


def test_customer_360_account_detail_is_workspace_scoped(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    account = Account(workspace_id="ws-owner", name="Owner Account", account_key="owner-account")
    db.add(account)
    db.commit()

    response = client.get(
        f"{settings.API_V1_STR}/customer-360/accounts/{account.id}",
        headers=_headers(superuser_token_headers, "ws-other"),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Account not found"
```

- [ ] **Step 2: Run API route tests to verify they fail**

Run:

```powershell
uv run pytest apps/api/tests/api/routes/test_customer_360.py -q
```

Expected: FAIL because `/customer-360/accounts` is not registered.

- [ ] **Step 3: Add Customer 360 route module**

Create `apps/api/app/api/routes/customer_360.py`:

```python
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import SessionDep, require_admin
from app.api.request_context import WorkspaceIdDep
from app.domain.customer_360.service import get_account_profile, list_customer_360_accounts
from app.domain_models import Customer360AccountProfilePublic, Customer360AccountsPublic

router = APIRouter(
    prefix="/customer-360",
    tags=["customer-360"],
    dependencies=[Depends(require_admin)],
)


@router.get("/accounts", response_model=Customer360AccountsPublic)
def read_customer_360_accounts(
    session: SessionDep,
    workspace_id: WorkspaceIdDep,
    search: Annotated[str | None, Query(max_length=255)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> Customer360AccountsPublic:
    """Return account rows for Customer 360."""
    return list_customer_360_accounts(
        session,
        workspace_id=workspace_id,
        search=search,
        limit=limit,
    )


@router.get("/accounts/{account_id}", response_model=Customer360AccountProfilePublic)
def read_customer_360_account_profile(
    account_id: uuid.UUID,
    session: SessionDep,
    workspace_id: WorkspaceIdDep,
) -> Customer360AccountProfilePublic:
    """Return one Account Command Center payload."""
    profile = get_account_profile(session, workspace_id=workspace_id, account_id=account_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Account not found")
    return profile
```

In `apps/api/app/api/main.py`, add `customer_360` to the routes import block and include it before `contacts`:

```python
    customer_360,
```

```python
api_router.include_router(customer_360.router)
```

- [ ] **Step 4: Run API route tests**

Run:

```powershell
uv run pytest apps/api/tests/api/routes/test_customer_360.py -q
```

Expected: PASS.

- [ ] **Step 5: Run backend targeted tests**

Run:

```powershell
uv run pytest apps/api/tests/domain/test_accounts_service.py apps/api/tests/api/routes/test_contacts.py::test_contact_import_preview_and_commit apps/api/tests/unit/test_customer_360_service.py apps/api/tests/api/routes/test_customer_360.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit Customer 360 API routes**

Run:

```powershell
git add apps/api/app/api/main.py apps/api/app/api/routes/customer_360.py apps/api/tests/api/routes/test_customer_360.py
git commit -m "Add Customer 360 API routes"
```

## Task 6: Customer 360 Frontend Account List

**Files:**
- Create: `apps/web/src/features/customer-360/api.ts`
- Create: `apps/web/src/features/customer-360/Customer360AccountsPage.tsx`
- Create: `apps/web/src/routes/_layout/customer-360.tsx`
- Modify: `apps/web/src/components/Sidebar/AppSidebar.tsx`
- Test: `apps/web/tests/customer-360.spec.ts`

- [ ] **Step 1: Write failing Playwright test for account list**

Create `apps/web/tests/customer-360.spec.ts`:

```typescript
import { expect, test } from "@playwright/test"

const ACCOUNT_ID = "11111111-1111-4111-8111-111111111111"

const ACCOUNTS_RESPONSE = {
  data: [
    {
      id: ACCOUNT_ID,
      workspace_id: "default",
      name: "Analytical Health",
      account_key: "analytical-health",
      website_url: "https://analytical.example",
      industry: "Healthcare",
      status: "active",
      summary: "Multi-location healthcare buyer.",
      tags: ["pricing", "voice-ready"],
      created_at: "2026-06-08T10:00:00Z",
      updated_at: "2026-06-08T10:00:00Z",
      contact_count: 2,
      last_activity_at: "2026-06-08T10:45:00Z",
      channel_counts: { chatbot: 1, email: 1, voice: 1, prospecting: 1 },
      top_next_action: "Reply with pricing clarity, then queue a call.",
    },
  ],
  count: 1,
}

test.use({ storageState: { cookies: [], origins: [] } })

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem("access_token", "e2e-test-token")
    localStorage.setItem("workspace_id", "default")
  })

  await page.route("**/api/v1/users/me", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: "user-1",
        email: "admin@example.com",
        full_name: "Admin User",
        is_superuser: true,
      }),
    })
  })

  await page.route("**/api/v1/customer-360/accounts", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(ACCOUNTS_RESPONSE),
    })
  })
})

test("Customer 360 account list shows account rollups", async ({ page }) => {
  await page.goto("/customer-360")

  await expect(page.getByRole("heading", { name: "Customer 360" })).toBeVisible()
  await expect(page.getByText("Analytical Health")).toBeVisible()
  await expect(page.getByText("2 contacts")).toBeVisible()
  await expect(page.getByText("Chatbot 1")).toBeVisible()
  await expect(page.getByText("Voice 1")).toBeVisible()
  await expect(page.getByRole("link", { name: "Open Analytical Health" })).toHaveAttribute(
    "href",
    `/customer-360/${ACCOUNT_ID}`,
  )
})
```

- [ ] **Step 2: Run Playwright list test to verify it fails**

Run from `apps/web`:

```powershell
npx playwright test tests/customer-360.spec.ts --project=chromium --no-deps --reporter=line
```

Expected: FAIL because `/customer-360` route does not exist.

- [ ] **Step 3: Add frontend API module**

Create `apps/web/src/features/customer-360/api.ts`:

```typescript
import { engagehubRequest } from "@/lib/engagehub-api"

export type Customer360Account = {
  id: string
  workspace_id: string
  name: string
  account_key: string
  website_url?: string | null
  industry?: string | null
  status: string
  summary?: string | null
  tags: string[]
  created_at: string
  updated_at: string
}

export type Customer360AccountRow = Customer360Account & {
  contact_count: number
  last_activity_at?: string | null
  channel_counts: Record<string, number>
  top_next_action?: string | null
}

export type Customer360AccountsResponse = {
  data: Customer360AccountRow[]
  count: number
}

export function listCustomer360Accounts(search = "") {
  const params = new URLSearchParams({ limit: "50" })
  if (search.trim()) params.set("search", search.trim())
  return engagehubRequest<Customer360AccountsResponse>(
    `/api/v1/customer-360/accounts?${params.toString()}`,
  )
}
```

- [ ] **Step 4: Add account list page**

Create `apps/web/src/features/customer-360/Customer360AccountsPage.tsx`:

```tsx
import { Link } from "@tanstack/react-router"
import { Building2, Loader2, RefreshCw, Search } from "lucide-react"
import { useCallback, useEffect, useState } from "react"

import { Alert } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { listCustomer360Accounts, type Customer360AccountRow } from "@/features/customer-360/api"

function channelCount(account: Customer360AccountRow, channel: string) {
  return account.channel_counts[channel] ?? 0
}

export default function Customer360AccountsPage() {
  const [accounts, setAccounts] = useState<Customer360AccountRow[]>([])
  const [search, setSearch] = useState("")
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadAccounts = useCallback(async (nextSearch = search) => {
    setLoading(true)
    setError(null)
    try {
      const response = await listCustomer360Accounts(nextSearch)
      setAccounts(response.data)
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not load accounts")
    } finally {
      setLoading(false)
    }
  }, [search])

  useEffect(() => {
    void loadAccounts("")
  }, [loadAccounts])

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="mb-2 flex items-center gap-2 text-sm text-muted-foreground">
            <Building2 className="size-4" />
            Account workspace
          </div>
          <h1 className="text-3xl font-semibold tracking-tight">Customer 360</h1>
          <p className="text-sm text-muted-foreground">
            Account profiles combining contacts, chatbot, email, voice, prospecting, and timeline activity.
          </p>
        </div>
        <Button variant="outline" onClick={() => void loadAccounts(search)} disabled={loading}>
          {loading ? <Loader2 className="mr-2 size-4 animate-spin" /> : <RefreshCw className="mr-2 size-4" />}
          Refresh
        </Button>
      </div>

      {error && <Alert variant="destructive">{error}</Alert>}

      <div className="flex gap-2">
        <div className="relative min-w-72 flex-1">
          <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") void loadAccounts(search)
            }}
            className="pl-9"
            placeholder="Search accounts"
          />
        </div>
        <Button type="button" variant="outline" onClick={() => void loadAccounts(search)} disabled={loading}>
          Search
        </Button>
      </div>

      {loading && accounts.length === 0 ? (
        <div className="flex items-center gap-2 rounded-lg border border-dashed p-6 text-sm text-muted-foreground">
          <Loader2 className="size-4 animate-spin" />
          Loading accounts...
        </div>
      ) : accounts.length === 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>No accounts yet</CardTitle>
            <CardDescription>Import contacts with company names to create account profiles.</CardDescription>
          </CardHeader>
        </Card>
      ) : (
        <div className="grid gap-4 xl:grid-cols-2">
          {accounts.map((account) => (
            <Card key={account.id}>
              <CardHeader>
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <CardTitle>{account.name}</CardTitle>
                    <CardDescription>
                      {account.industry || "Account"} - {account.contact_count} contacts
                    </CardDescription>
                  </div>
                  <Badge variant="secondary">{account.status}</Badge>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <p className="text-sm leading-6 text-muted-foreground">
                  {account.summary || account.top_next_action || "No account summary yet."}
                </p>
                <div className="flex flex-wrap gap-2">
                  <Badge variant="outline">Chatbot {channelCount(account, "chatbot")}</Badge>
                  <Badge variant="outline">Email {channelCount(account, "email")}</Badge>
                  <Badge variant="outline">Voice {channelCount(account, "voice")}</Badge>
                  <Badge variant="outline">Prospecting {channelCount(account, "prospecting")}</Badge>
                </div>
                <Button asChild>
                  <Link to="/customer-360/$accountId" params={{ accountId: account.id }} aria-label={`Open ${account.name}`}>
                    Open account
                  </Link>
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 5: Add account list route and sidebar item**

Create `apps/web/src/routes/_layout/customer-360.tsx`:

```tsx
import { createFileRoute } from "@tanstack/react-router"

import Customer360AccountsPage from "@/features/customer-360/Customer360AccountsPage"

export const Route = createFileRoute("/_layout/customer-360")({
  head: () => ({
    meta: [{ title: "Customer 360 - EngageHub" }],
  }),
  component: Customer360AccountsPage,
})
```

In `apps/web/src/components/Sidebar/AppSidebar.tsx`, add `Building2` to the `lucide-react` imports and add this item after EngageHub AI:

```tsx
  { icon: Building2, title: "Customer 360", path: "/customer-360" },
```

- [ ] **Step 6: Run Playwright list test**

Run from `apps/web`:

```powershell
npx playwright test tests/customer-360.spec.ts --project=chromium --no-deps --reporter=line
```

Expected: PASS.

- [ ] **Step 7: Commit frontend account list**

Run from repo root:

```powershell
git add apps/web/src/features/customer-360/api.ts apps/web/src/features/customer-360/Customer360AccountsPage.tsx apps/web/src/routes/_layout/customer-360.tsx apps/web/src/components/Sidebar/AppSidebar.tsx apps/web/tests/customer-360.spec.ts apps/web/src/routeTree.gen.ts
git commit -m "Add Customer 360 account list"
```

## Task 7: Customer 360 Frontend Account Profile

**Files:**
- Modify: `apps/web/src/features/customer-360/api.ts`
- Create: `apps/web/src/features/customer-360/Customer360AccountProfilePage.tsx`
- Create: `apps/web/src/routes/_layout/customer-360.$accountId.tsx`
- Modify: `apps/web/tests/customer-360.spec.ts`

- [ ] **Step 1: Extend Playwright test for account profile**

Append to `apps/web/tests/customer-360.spec.ts`:

```typescript
const ACCOUNT_PROFILE_RESPONSE = {
  account: {
    id: ACCOUNT_ID,
    workspace_id: "default",
    name: "Analytical Health",
    account_key: "analytical-health",
    website_url: "https://analytical.example",
    industry: "Healthcare",
    status: "active",
    summary: "Multi-location healthcare buyer.",
    tags: ["pricing", "voice-ready"],
    created_at: "2026-06-08T10:00:00Z",
    updated_at: "2026-06-08T10:00:00Z",
  },
  contacts: [
    {
      id: "contact-1",
      workspace_id: "default",
      account_id: ACCOUNT_ID,
      email: "ada@example.com",
      first_name: "Ada",
      last_name: "Lovelace",
      company: "Analytical Health",
      phone: "+15551234567",
      timezone: "America/New_York",
      created_at: "2026-06-08T09:00:00Z",
      display_name: "Ada Lovelace",
    },
    {
      id: "contact-2",
      workspace_id: "default",
      account_id: ACCOUNT_ID,
      email: "grace@example.com",
      first_name: "Grace",
      last_name: "Hopper",
      company: "Analytical Health",
      phone: null,
      timezone: "UTC",
      created_at: "2026-06-08T09:05:00Z",
      display_name: "Grace Hopper",
    },
  ],
  channel_summaries: {
    chatbot: { channel: "chatbot", label: "Chatbot", count: 1, status: "active", detail: "1 escalated thread(s)" },
    email: { channel: "email", label: "Email", count: 1, status: "active", detail: "1 open or click event(s)" },
    voice: { channel: "voice", label: "Voice", count: 1, status: "active", detail: "1 follow-up call(s)" },
    prospecting: { channel: "prospecting", label: "Prospecting", count: 1, status: "ready", detail: "Latest brief has drafts." },
  },
  next_best_action: {
    title: "Reply with pricing clarity, then queue a call",
    reason: "Analytical Health has open chatbot work.",
    source: "chatbot",
    priority: "high",
  },
  open_work: [
    {
      id: "chatbot-thread-1",
      source: "chatbot",
      title: "Chatbot escalation",
      contact_id: "contact-1",
      contact_name: "Ada Lovelace",
      status: "escalated",
      created_at: "2026-06-08T10:30:00Z",
    },
  ],
  prospecting_brief: {
    snapshot_id: "snapshot-1",
    contact_id: "contact-1",
    account_summary: "Analytical Health is evaluating cross-channel outreach.",
    suggested_next_action: "Reply with pricing clarity, then queue a call.",
    email_draft_available: true,
    voice_opener_available: true,
    created_at: "2026-06-08T09:30:00Z",
  },
  timeline: [
    {
      id: "voice-call-1",
      source: "voice",
      event_type: "call_session",
      title: "Voice call completed",
      detail: "Ada needs implementation pricing clarity before booking.",
      contact_id: "contact-1",
      contact_name: "Ada Lovelace",
      timestamp: "2026-06-08T10:45:00Z",
    },
    {
      id: "chatbot-thread-1",
      source: "chatbot",
      event_type: "chatbot_thread",
      title: "Chatbot escalation",
      detail: "Pricing question needs a human",
      contact_id: "contact-1",
      contact_name: "Ada Lovelace",
      timestamp: "2026-06-08T10:30:00Z",
    },
  ],
}

test("Customer 360 account profile shows command center", async ({ page }) => {
  await page.route(`**/api/v1/customer-360/accounts/${ACCOUNT_ID}`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(ACCOUNT_PROFILE_RESPONSE),
    })
  })

  await page.goto(`/customer-360/${ACCOUNT_ID}`)

  await expect(page.getByRole("heading", { name: "Analytical Health" })).toBeVisible()
  await expect(page.getByText("Multi-location healthcare buyer.")).toBeVisible()
  await expect(page.getByText("Ada Lovelace")).toBeVisible()
  await expect(page.getByText("Grace Hopper")).toBeVisible()
  await expect(page.getByText("Chatbot")).toBeVisible()
  await expect(page.getByText("Email")).toBeVisible()
  await expect(page.getByText("Voice")).toBeVisible()
  await expect(page.getByText("Prospecting")).toBeVisible()
  await expect(page.getByText("Reply with pricing clarity, then queue a call")).toBeVisible()
  await expect(page.getByText("Unified account timeline")).toBeVisible()
  await expect(page.getByText("Voice call completed")).toBeVisible()
  await expect(page.getByText("Pricing question needs a human")).toBeVisible()
})
```

- [ ] **Step 2: Run profile Playwright test to verify it fails**

Run from `apps/web`:

```powershell
npx playwright test tests/customer-360.spec.ts --project=chromium --no-deps --reporter=line
```

Expected: FAIL because `/customer-360/$accountId` route and profile page do not exist.

- [ ] **Step 3: Extend frontend API types**

Append to `apps/web/src/features/customer-360/api.ts`:

```typescript
export type Customer360Contact = {
  id: string
  workspace_id: string
  account_id?: string | null
  email: string
  first_name?: string | null
  last_name?: string | null
  company?: string | null
  phone?: string | null
  timezone: string
  created_at: string
  display_name: string
}

export type Customer360ChannelSummary = {
  channel: string
  label: string
  count: number
  status: string
  detail: string
}

export type Customer360NextAction = {
  title: string
  reason: string
  source: string
  priority: string
}

export type Customer360OpenWork = {
  id: string
  source: string
  title: string
  contact_id?: string | null
  contact_name?: string | null
  status: string
  created_at: string
}

export type Customer360ProspectingBrief = {
  snapshot_id: string
  contact_id: string
  account_summary: string
  suggested_next_action?: string | null
  email_draft_available: boolean
  voice_opener_available: boolean
  created_at: string
}

export type Customer360TimelineEvent = {
  id: string
  source: string
  event_type: string
  title: string
  detail: string
  contact_id?: string | null
  contact_name?: string | null
  timestamp: string
}

export type Customer360AccountProfile = {
  account: Customer360Account
  contacts: Customer360Contact[]
  channel_summaries: Record<string, Customer360ChannelSummary>
  next_best_action?: Customer360NextAction | null
  open_work: Customer360OpenWork[]
  prospecting_brief?: Customer360ProspectingBrief | null
  timeline: Customer360TimelineEvent[]
}

export function getCustomer360AccountProfile(accountId: string) {
  return engagehubRequest<Customer360AccountProfile>(`/api/v1/customer-360/accounts/${accountId}`)
}
```

- [ ] **Step 4: Add account profile page**

Create `apps/web/src/features/customer-360/Customer360AccountProfilePage.tsx`:

```tsx
import { Link } from "@tanstack/react-router"
import { ArrowLeft, BriefcaseBusiness, Loader2, RefreshCw } from "lucide-react"
import { useCallback, useEffect, useState } from "react"

import { Alert } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import {
  getCustomer360AccountProfile,
  type Customer360AccountProfile,
  type Customer360ChannelSummary,
} from "@/features/customer-360/api"

function formatDate(value: string) {
  return new Date(value).toLocaleString()
}

function summaryFor(profile: Customer360AccountProfile, channel: string): Customer360ChannelSummary {
  return profile.channel_summaries[channel] ?? {
    channel,
    label: channel,
    count: 0,
    status: "empty",
    detail: "No activity yet.",
  }
}

export default function Customer360AccountProfilePage({ accountId }: { accountId: string }) {
  const [profile, setProfile] = useState<Customer360AccountProfile | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadProfile = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await getCustomer360AccountProfile(accountId)
      setProfile(response)
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not load account profile")
    } finally {
      setLoading(false)
    }
  }, [accountId])

  useEffect(() => {
    void loadProfile()
  }, [loadProfile])

  if (loading && !profile) {
    return (
      <div className="flex items-center gap-2 rounded-lg border border-dashed p-6 text-sm text-muted-foreground">
        <Loader2 className="size-4 animate-spin" />
        Loading account profile...
      </div>
    )
  }

  if (error && !profile) {
    return (
      <div className="flex flex-col gap-4">
        <Button asChild variant="outline" className="w-fit">
          <Link to="/customer-360">
            <ArrowLeft className="mr-2 size-4" />
            Back to accounts
          </Link>
        </Button>
        <Alert variant="destructive">{error}</Alert>
      </div>
    )
  }

  if (!profile) return null

  const channels = ["chatbot", "email", "voice", "prospecting"].map((channel) => summaryFor(profile, channel))

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Button asChild variant="ghost" size="sm" className="-ml-3 mb-2">
            <Link to="/customer-360">
              <ArrowLeft className="mr-2 size-4" />
              Accounts
            </Link>
          </Button>
          <div className="mb-2 flex items-center gap-2 text-sm text-muted-foreground">
            <BriefcaseBusiness className="size-4" />
            Account command center
          </div>
          <h1 className="text-3xl font-semibold tracking-tight">{profile.account.name}</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {profile.account.industry || "Account"} - {profile.contacts.length} contacts - {profile.account.status}
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            {profile.account.tags.map((tag) => (
              <Badge key={tag} variant="secondary">{tag}</Badge>
            ))}
          </div>
        </div>
        <Button variant="outline" onClick={() => void loadProfile()} disabled={loading}>
          {loading ? <Loader2 className="mr-2 size-4 animate-spin" /> : <RefreshCw className="mr-2 size-4" />}
          Refresh
        </Button>
      </div>

      {error && <Alert variant="destructive">{error}</Alert>}

      <div className="grid gap-6 xl:grid-cols-[300px_minmax(0,1fr)]">
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Account summary</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm leading-6 text-muted-foreground">
                {profile.account.summary || "No account summary yet."}
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Contacts</CardTitle>
              <CardDescription>{profile.contacts.length} people</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {profile.contacts.length ? profile.contacts.map((contact) => (
                <div key={contact.id} className="rounded-md border p-3">
                  <p className="font-medium">{contact.display_name}</p>
                  <p className="mt-1 text-xs text-muted-foreground">{contact.email}</p>
                  {contact.phone && <Badge className="mt-2" variant="outline">Voice ready</Badge>}
                </div>
              )) : (
                <p className="text-sm text-muted-foreground">No contacts attached to this account.</p>
              )}
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6">
          <div className="grid gap-4 md:grid-cols-4">
            {channels.map((channel) => (
              <Card key={channel.channel}>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm">{channel.label}</CardTitle>
                  <CardDescription>{channel.status}</CardDescription>
                </CardHeader>
                <CardContent>
                  <p className="text-2xl font-semibold">{channel.count}</p>
                  <p className="mt-2 text-xs leading-5 text-muted-foreground">{channel.detail}</p>
                </CardContent>
              </Card>
            ))}
          </div>

          <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_320px]">
            <Card>
              <CardHeader>
                <CardTitle>Unified account timeline</CardTitle>
                <CardDescription>Newest activity across contacts and channels.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {profile.timeline.length ? profile.timeline.map((event) => (
                  <div key={event.id} className="rounded-md border p-3">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <p className="font-medium">{event.title}</p>
                        <p className="mt-1 text-sm leading-6 text-muted-foreground">{event.detail}</p>
                        {event.contact_name && <p className="mt-1 text-xs text-muted-foreground">{event.contact_name}</p>}
                      </div>
                      <Badge variant="outline">{event.source}</Badge>
                    </div>
                    <p className="mt-2 text-xs text-muted-foreground">{formatDate(event.timestamp)}</p>
                  </div>
                )) : (
                  <p className="text-sm text-muted-foreground">No account timeline activity yet.</p>
                )}
              </CardContent>
            </Card>

            <div className="space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle>Next best action</CardTitle>
                </CardHeader>
                <CardContent>
                  {profile.next_best_action ? (
                    <div className="space-y-3">
                      <p className="font-medium">{profile.next_best_action.title}</p>
                      <p className="text-sm leading-6 text-muted-foreground">{profile.next_best_action.reason}</p>
                      <Badge>{profile.next_best_action.priority}</Badge>
                    </div>
                  ) : (
                    <p className="text-sm text-muted-foreground">No action recommended right now.</p>
                  )}
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Prospecting brief</CardTitle>
                </CardHeader>
                <CardContent>
                  {profile.prospecting_brief ? (
                    <p className="text-sm leading-6 text-muted-foreground">{profile.prospecting_brief.account_summary}</p>
                  ) : (
                    <p className="text-sm text-muted-foreground">No prospecting brief yet.</p>
                  )}
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Open work</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                  {profile.open_work.length ? profile.open_work.map((item) => (
                    <div key={item.id} className="rounded-md border p-3 text-sm">
                      <p className="font-medium">{item.title}</p>
                      <p className="mt-1 text-xs text-muted-foreground">{item.contact_name || "Account"} - {item.status}</p>
                    </div>
                  )) : (
                    <p className="text-sm text-muted-foreground">No open work.</p>
                  )}
                </CardContent>
              </Card>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 5: Add account profile route**

Create `apps/web/src/routes/_layout/customer-360.$accountId.tsx`:

```tsx
import { createFileRoute } from "@tanstack/react-router"

import Customer360AccountProfilePage from "@/features/customer-360/Customer360AccountProfilePage"

export const Route = createFileRoute("/_layout/customer-360/$accountId")({
  component: Customer360AccountRoute,
})

function Customer360AccountRoute() {
  const { accountId } = Route.useParams()
  return <Customer360AccountProfilePage accountId={accountId} />
}
```

- [ ] **Step 6: Run Customer 360 Playwright tests**

Run from `apps/web`:

```powershell
npx playwright test tests/customer-360.spec.ts --project=chromium --no-deps --reporter=line
```

Expected: PASS.

- [ ] **Step 7: Commit account profile frontend**

Run from repo root:

```powershell
git add apps/web/src/features/customer-360/api.ts apps/web/src/features/customer-360/Customer360AccountProfilePage.tsx apps/web/src/routes/_layout/customer-360.$accountId.tsx apps/web/tests/customer-360.spec.ts apps/web/src/routeTree.gen.ts
git commit -m "Add Customer 360 account profile UI"
```

## Task 8: Final Verification And Documentation Update

**Files:**
- Modify: `docs/user-guide/getting-started.md`

- [ ] **Step 1: Add a short Customer 360 user-guide entry**

In `docs/user-guide/getting-started.md`, add a concise section near the Contacts section:

```markdown
## Customer 360

Customer 360 is the account-level workspace for a company. It shows the account summary, contacts, chatbot activity, email sequence activity, voice call activity, prospecting research, open work, next best action, and unified account timeline.

Use Customer 360 before follow-up when you need to understand what has happened across every channel for one account.
```

- [ ] **Step 2: Run backend targeted tests**

Run:

```powershell
uv run pytest apps/api/tests/domain/test_accounts_service.py apps/api/tests/api/routes/test_contacts.py::test_contact_import_preview_and_commit apps/api/tests/unit/test_customer_360_service.py apps/api/tests/api/routes/test_customer_360.py -q
```

Expected: PASS.

- [ ] **Step 3: Run frontend Customer 360 test**

Run from `apps/web`:

```powershell
npx playwright test tests/customer-360.spec.ts --project=chromium --no-deps --reporter=line
```

Expected: PASS.

- [ ] **Step 4: Run frontend build**

Run from repo root:

```powershell
npm --workspace frontend run build
```

Expected: exit code 0.

- [ ] **Step 5: Run formatter/lint for touched frontend files**

Run from `apps/web`:

```powershell
npx biome check --write --unsafe --no-errors-on-unmatched --files-ignore-unknown=true src/features/customer-360 src/routes/_layout/customer-360.tsx src/routes/_layout/customer-360.`$accountId.tsx tests/customer-360.spec.ts src/components/Sidebar/AppSidebar.tsx
```

Expected: exit code 0.

- [ ] **Step 6: Check git diff**

Run:

```powershell
git status --short
git diff --check
```

Expected: Customer 360 files and docs are modified or staged. `git diff --check` reports no whitespace errors. Unrelated user changes remain unstaged.

- [ ] **Step 7: Commit documentation and final generated changes**

Run:

```powershell
git add docs/user-guide/getting-started.md apps/web/src/routeTree.gen.ts
git commit -m "Document Customer 360 account profiles"
```

If `apps/web/src/routeTree.gen.ts` is unchanged, commit only `docs/user-guide/getting-started.md`.

- [ ] **Step 8: Final status report**

Run:

```powershell
git status --short
```

Expected: no Customer 360 files remain unstaged. Report any unrelated modified files separately.

## Spec Coverage Review

- First-class accounts table: Tasks 1 and 2.
- Backfill existing contacts from company values: Task 2.
- Contact import attaches accounts: Task 3.
- Account list/detail APIs: Tasks 4 and 5.
- Aggregated chatbot/email/voice/prospecting/timeline profile: Task 4.
- Frontend Account Command Center: Tasks 6 and 7.
- Sidebar navigation: Task 6.
- Empty/error states: Tasks 6 and 7.
- Backend, API, Playwright, build, and lint verification: Tasks 1 through 8.
