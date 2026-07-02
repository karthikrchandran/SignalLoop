# eMailVoice Shared Layer Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make eMailVoice read business entities from the eCRM shared-record layer and stop treating local `accounts` and `contacts` as the business source of truth.

**Architecture:** eCRM remains the owner of shared business records through `/api/shared-records`. eMailVoice reads `CUSTOMER` and `CONTACT` records through `app.integrations.ecrm_shared_records`, maps them into existing API response shapes for the web app, and stores only eMailVoice operational state locally. Existing local `contacts.id` foreign keys must be migrated to shared-record identifiers before the local contact table can be retired.

**Tech Stack:** FastAPI, SQLModel, Alembic, pytest, React/Vite, TanStack Router.

---

## File Structure

- `apps/api/app/domain/shared_records/entities.py`: typed shared `CUSTOMER` and `CONTACT` DTO helpers.
- `apps/api/app/domain/shared_records/service.py`: list, filter, and map shared records for eMailVoice pages.
- `apps/api/app/api/routes/contacts.py`: route `/contacts` through shared service; keep timeline routes local until operational tables are migrated.
- `apps/api/app/domain/customer_360/service.py`: read customer/account rows and child contacts from shared service.
- `apps/api/app/domain/prospecting/service.py`: read prospecting candidate contacts from shared service.
- `apps/api/app/api/routes/campaigns.py`: assign campaign audience from shared contacts, then write local campaign state against shared identifiers after schema migration.
- `apps/api/app/domain_models.py`: replace operational `contact_id` foreign-key dependencies with shared-contact reference fields in a later schema task.
- `apps/api/alembic/versions/*_shared_contact_refs.py`: migrate operational tables from local `contact_id` FK ownership to shared contact reference columns.
- `apps/api/tests/unit/test_shared_records_cutover.py`: unit coverage for shared contacts/accounts/customer 360/prospecting.
- `apps/api/tests/api/routes/test_campaigns.py`: route-level coverage for shared audience assignment.

## Task 1: Shared-Record Read Service

**Files:**
- Create: `apps/api/app/domain/shared_records/entities.py`
- Create: `apps/api/app/domain/shared_records/service.py`
- Test: `apps/api/tests/unit/test_shared_records_cutover.py`

- [ ] **Step 1: Write failing tests**

Add tests that monkeypatch `ecrm_shared_records.list_shared_records` and assert:

```python
def test_shared_contact_service_maps_records_to_contact_public():
    records = {
        "records": [
            {
                "id": "shared-contact-1",
                "entityType": "CONTACT",
                "displayName": "Ada Lovelace",
                "status": "active",
                "email": "ada@example.com",
                "phone": "+15551234567",
                "companyName": "Analytical",
                "data": {"workspaceId": "ws-a", "firstName": "Ada", "lastName": "Lovelace", "timezone": "UTC"},
                "createdAt": "2026-06-30T12:00:00Z",
            }
        ]
    }
```

Expected behavior: mapped contact contains no local database lookup and has stable deterministic ID derived from the shared record.

- [ ] **Step 2: Run test and confirm RED**

Run:

```powershell
cd apps\api
uv run pytest tests/unit/test_shared_records_cutover.py -q
```

Expected: fails because `app.domain.shared_records.service` does not exist.

- [ ] **Step 3: Implement minimal service**

Create shared-record mapping helpers and call `ecrm_shared_records.list_shared_records(entity_type="CONTACT", ...)`.

- [ ] **Step 4: Run test and confirm GREEN**

Run the same pytest command. Expected: test passes.

## Task 2: Page Read Cutover

**Files:**
- Modify: `apps/api/app/api/routes/contacts.py`
- Modify: `apps/api/app/domain/customer_360/service.py`
- Modify: `apps/api/app/domain/prospecting/service.py`
- Test: `apps/api/tests/unit/test_shared_records_cutover.py`

- [ ] **Step 1: Write failing route/service tests**

Tests must assert:
- `read_contacts` does not query `Contact` when `USE_ECRM_SHARED_RECORDS=True`.
- `list_customer_360_accounts` returns shared `CUSTOMER` rows.
- `get_account_profile` resolves shared child `CONTACT` rows by parent/shared relationship.
- `list_ready_contacts` scores shared contacts instead of local `Contact` rows.

- [ ] **Step 2: Run tests and confirm RED**

Run:

```powershell
cd apps\api
uv run pytest tests/unit/test_shared_records_cutover.py -q
```

- [ ] **Step 3: Implement page read cutovers**

Replace local `select(Account)` and `select(Contact)` paths in page services with shared service calls when the flag is enabled. Keep local fallback only for `USE_ECRM_SHARED_RECORDS=False`.

- [ ] **Step 4: Run tests and confirm GREEN**

Run the same pytest command.

## Task 3: Operational Schema Migration

**Files:**
- Modify: `apps/api/app/domain_models.py`
- Modify: `apps/api/app/domain/voice/models.py`
- Modify: `apps/api/app/domain/chatbot/models.py`
- Modify: `apps/api/app/domain/sequences/models.py`
- Modify: `apps/api/app/domain/signals/models.py`
- Create: `apps/api/alembic/versions/*_shared_contact_refs.py`
- Test: impacted backend route/domain tests

- [ ] **Step 1: Write migration tests**

Add tests that create campaign progressions, call requests, chatbot conversations, sequence states, signal events, and prospecting snapshots using shared contact IDs without requiring a local `contacts` row.

- [ ] **Step 2: Run tests and confirm RED**

Expected: FK or type validation failures on local `contacts.id`.

- [ ] **Step 3: Add shared contact reference fields**

Add string shared reference fields such as `shared_contact_id` and `shared_account_id` to operational rows. Preserve existing local `contact_id` as nullable only during migration.

- [ ] **Step 4: Update operational queries**

Change campaign, voice, chatbot, sequence, signal, prospecting, and timeline queries to filter and render by shared contact reference.

- [ ] **Step 5: Run impacted backend tests**

Run:

```powershell
cd apps\api
uv run pytest tests/api/routes/test_campaigns.py tests/api/routes/test_contact_timeline.py tests/unit/test_shared_records_cutover.py -q
```

## Task 4: Remove Local Business Ownership

**Files:**
- Modify: `apps/api/app/api/routes/accounts.py`
- Modify: `apps/api/app/api/routes/contacts.py`
- Modify: `apps/api/app/domain/accounts/service.py`
- Modify: `apps/api/app/domain_models.py`

- [ ] **Step 1: Write tests proving local source routes are disabled**

Tests must assert account/contact create/update routes call shared API and no longer create local business-owned `Account` or `Contact` rows.

- [ ] **Step 2: Run tests and confirm RED**

- [ ] **Step 3: Remove local ownership writes**

Delete or deprecate local account/contact ownership code after operational rows no longer depend on local FKs.

- [ ] **Step 4: Run full backend verification**

Run:

```powershell
cd apps\api
uv run pytest -q
uv run ruff check app tests
uv run ruff format --check app tests
```

## Acceptance Criteria

- Contacts page reads from eCRM shared records.
- Customer 360 reads customers and contacts from eCRM shared records.
- Campaign audience selection reads from eCRM shared contacts.
- Prospecting reads from eCRM shared contacts.
- Operational tables no longer require a local `contacts` row for new activity.
- A source scan shows no page/service read path still uses local `Account` or `Contact` as the business entity source when `USE_ECRM_SHARED_RECORDS=True`.
- Backend tests, lint, and format checks pass.
