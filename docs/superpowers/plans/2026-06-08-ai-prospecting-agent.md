# AI Prospecting Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a first usable EngageHub AI prospecting/research slice that enriches an existing contact/account from CRM history and an optional website URL, persists a research snapshot, and drafts personalized email plus voice outreach.

**Architecture:** Add a new `prospecting` backend domain with SQLModel persistence, deterministic research service, workspace-scoped API route, and audit event. Add a new React/TanStack route at `/prospecting` using existing `engagehubRequest`, contact list API, and sidebar navigation. Keep v1 local-first and provider-independent; shape the service so LLM/live-news enrichment can be added later.

**Tech Stack:** FastAPI, SQLModel, Alembic, pytest, React, TypeScript, TanStack Router, Vite, Playwright, existing shadcn-style UI components, lucide-react.

---

## Tasks

- [ ] Verify current migration state before adding a new revision.
  - Run `uv run alembic heads` from `apps/api`.
  - If multiple heads still exist, do not create a new branch from a non-head revision. Merge heads first with `uv run alembic merge -m "merge heads before prospecting" <head1> <head2>`, then create the prospecting migration from the merged head.

- [ ] Add backend unit tests first for deterministic research generation.
  - Create `apps/api/tests/domain/test_prospecting_service.py`.
  - Test `build_prospecting_brief` with a contact that has `company`, `tags_json`, `intent_json`, and a website snippet.
  - Assert the result contains:
    - `account_summary` mentioning contact/company
    - at least two `pain_points`
    - at least one `objections`
    - at least two `personalization_bullets`
    - `email_draft` with a subject and contact first name
    - `voice_opener` with contact first name

- [ ] Add backend API tests first for the research endpoint.
  - Create `apps/api/tests/api/routes/test_prospecting.py`.
  - Insert a `Contact` in the test workspace.
  - POST to `${settings.API_V1_STR}/prospecting/research` with `Idempotency-Key`.
  - Assert HTTP 200, returned `contact_id`, non-empty drafts, and a persisted `ProspectingSnapshot`.
  - Assert an `AuditEvent` exists with `event_name == "prospect.researched"`.
  - Add a workspace isolation test that posting a contact from a different workspace returns 404.

- [ ] Add backend models and schemas.
  - Add `ProspectingSnapshot` to `apps/api/app/domain_models.py` near contact/campaign-adjacent models:

    ```python
    class ProspectingSnapshot(SQLModel, table=True):
        __tablename__ = "prospecting_snapshots"

        id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
        workspace_id: str = Field(sa_type=String(64), index=True)
        contact_id: uuid.UUID = Field(foreign_key="contacts.id", index=True)
        created_by: uuid.UUID | None = Field(default=None, index=True)
        company_url: str | None = Field(default=None, sa_type=Text)
        sources_json: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
        research_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
        email_draft: str = Field(sa_type=Text)
        voice_opener: str = Field(sa_type=Text)
        created_at: datetime = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True), index=True)
    ```

  - Add response/request schemas in `apps/api/app/domain/prospecting/schemas.py`.

- [ ] Add deterministic prospecting service.
  - Create `apps/api/app/domain/prospecting/service.py`.
  - Implement:
    - `build_prospecting_brief(contact: Contact, sources: list[ProspectingSource]) -> ProspectingBrief`
    - `create_prospecting_snapshot(session, workspace_id, contact_id, company_url, actor_id, actor_role) -> ProspectingSnapshot`
    - `list_prospecting_snapshots(session, workspace_id, contact_id=None, limit=20) -> list[ProspectingSnapshot]`
  - Query timeline context from `ContactEvent` and `ContactStateHistory` for the active contact.
  - If `company_url` is present, call `crawl_website(company_url, depth=1, max_pages=3)` from `app.infrastructure.rag.crawler`, catch exceptions, and continue with a `"Website unavailable"` source.
  - Append audit event through `append_audit_event_to_session(... event_name="prospect.researched" ...)`.

- [ ] Add FastAPI route.
  - Create `apps/api/app/api/routes/prospecting.py`.
  - Prefix: `APIRouter(prefix="/prospecting", tags=["prospecting"])`.
  - Endpoints:
    - `POST /research` with `SessionDep`, `CurrentUser`, `WorkspaceIdDep`, and `IdempotencyKeyDep`
    - `GET /research` with optional `contact_id` and `limit`
  - Include the router in `apps/api/app/api/main.py`.

- [ ] Add Alembic migration.
  - Create a new migration under `apps/api/app/alembic/versions`.
  - Upgrade creates `prospecting_snapshots`, indexes on `workspace_id`, `contact_id`, `created_by`, `created_at`.
  - Downgrade drops `prospecting_snapshots`.

- [ ] Add frontend API/types.
  - Create `apps/web/src/features/prospecting/api.ts`.
  - Types:
    - `ContactListResponse`
    - `ProspectingResearchRequest`
    - `ProspectingResearchResult`
  - Functions:
    - `listContacts(search?: string)`
    - `runProspectingResearch(input: ProspectingResearchRequest)`
    - `listProspectingResearch(contactId?: string)`

- [ ] Add frontend page.
  - Create `apps/web/src/features/prospecting/ProspectingPage.tsx`.
  - Page layout:
    - left/control area for contact search, contact select, company URL, run button
    - right/results area for account summary, pain points, objections, personalization, next action
    - draft area for email and voice opener
  - Use existing UI components from `apps/web/src/components/ui`.
  - Keep the UI dense and operational, not a marketing hero.

- [ ] Add route and sidebar navigation.
  - Create `apps/web/src/routes/_layout/prospecting.tsx` with `createFileRoute("/_layout/prospecting")`.
  - Add `{ icon: SearchCheck, title: "Prospecting", path: "/prospecting" }` to `baseItems` in `apps/web/src/components/Sidebar/AppSidebar.tsx`.
  - Regenerate TanStack route tree by running the existing web build or route generator script used by the repo.

- [ ] Add frontend Playwright smoke test.
  - Create `apps/web/tests/prospecting.spec.ts`.
  - Mock:
    - `GET **/api/v1/contacts/**` with two contacts
    - `POST **/api/v1/prospecting/research` with a deterministic prospecting result
  - Visit `/prospecting`.
  - Select a contact, enter URL, run research.
  - Assert the account summary, email draft, and voice opener are visible.

- [ ] Run focused verification.
  - Backend:

    ```powershell
    cd apps/api
    uv run pytest tests/domain/test_prospecting_service.py tests/api/routes/test_prospecting.py
    ```

  - Frontend:

    ```powershell
    cd apps/web
    npm run build
    npx playwright test tests/prospecting.spec.ts --project=chromium --workers=1
    ```

  - Migration:

    ```powershell
    cd apps/api
    uv run alembic heads
    ```

- [ ] Commit the slice when verification is complete.
  - Stage only intentional files plus any route-tree generated output.
  - Leave unrelated `apps/web/.tanstack/tmp/*` changes unstaged unless they are generated by the final build and needed.
  - Commit message: `Add AI prospecting research slice`.

## Acceptance Criteria

- `/prospecting` is reachable from the sidebar.
- A user can select a contact, optionally enter a URL, and generate a research result.
- Results persist in `prospecting_snapshots`.
- `prospect.researched` audit event is written.
- Backend tests cover service generation, endpoint persistence, audit, and workspace isolation.
- Frontend smoke test covers the main workflow.
- The implementation does not require Docker, Apollo, HubSpot, or live news access.
