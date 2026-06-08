# AI Prospecting Agent Design

## Decision

Build the first AI prospecting/research slice as a local-first EngageHub feature at `/prospecting`.

The v1 will enrich an existing contact/account from EngageHub CRM data, contact timeline history, and an optional company website URL. It will persist a research snapshot and generate deterministic outreach drafts so the workflow works without Docker, paid enrichment APIs, or live news crawling.

## User Workflow

1. A user opens `/prospecting`.
2. The user selects an existing contact from the contact pool.
3. The user optionally enters a company website URL.
4. EngageHub generates:
   - account summary
   - buyer pain points
   - likely objections
   - personalization bullets
   - suggested next action
   - draft email
   - draft voice opener
5. EngageHub stores the result as a snapshot and appends a `prospect.researched` audit event.

## Scope

In scope for this slice:

- Workspace-scoped backend API for running research and listing recent research snapshots.
- Persisted `prospecting_snapshots` table.
- Deterministic enrichment/draft service based on existing contact, company, tags, intent, last seen, timeline events, and optional website snippets.
- Frontend page reachable from the main sidebar.
- Focused backend unit/API tests and frontend Playwright smoke coverage.

Out of scope for this slice:

- Live news search.
- Apollo/HubSpot integration.
- Sending the generated outreach.
- Full LLM-provider drafting. The service should be shaped so an LLM provider can be added later without changing the API contract.

## Product Rationale

This creates a competitive workflow adjacent to Apollo and HubSpot without trying to clone them. The differentiator is using EngageHub's own CRM history, messaging/voice context, and future campaign execution path to create outreach that is immediately actionable inside the same product.

## API Contract

`POST /api/v1/prospecting/research`

Request:

```json
{
  "contact_id": "7c6b5317-a614-4c4c-b1f1-7d0e7bfb1a11",
  "company_url": "https://example.com"
}
```

Response:

```json
{
  "id": "83a172ec-3ae2-40a3-b201-d1c31cfe2e96",
  "contact_id": "7c6b5317-a614-4c4c-b1f1-7d0e7bfb1a11",
  "company_url": "https://example.com",
  "account_summary": "Ada Lovelace is a prospect at Analytical...",
  "pain_points": ["Improve outreach conversion from existing CRM signals"],
  "objections": ["May already have a CRM or enrichment workflow"],
  "personalization_bullets": ["Mention Analytical and the recent engagement signal"],
  "suggested_next_action": "Send a short email, then follow with a voice opener.",
  "email_draft": "Subject: Analytical outreach idea...",
  "voice_opener": "Hi Ada, this is...",
  "sources": [
    {
      "label": "CRM contact",
      "summary": "Ada Lovelace at Analytical"
    }
  ],
  "created_at": "2026-06-08T10:00:00Z"
}
```

`GET /api/v1/prospecting/research?contact_id=<uuid>`

Returns recent snapshots for the active workspace, newest first.

## Data Model

`prospecting_snapshots`

- `id`: UUID primary key
- `workspace_id`: string, indexed
- `contact_id`: UUID foreign key to `contacts.id`, indexed
- `created_by`: UUID nullable, indexed
- `company_url`: text nullable
- `sources_json`: JSON list of source summaries
- `research_json`: JSON structured summary fields
- `email_draft`: text
- `voice_opener`: text
- `created_at`: timezone-aware datetime, indexed

## Implementation Notes

- The service must validate contact ownership by `workspace_id`.
- Website URL failures should degrade gracefully into a CRM-only brief, not fail the whole workflow.
- Generated content should avoid claiming unverified live news.
- The route should require an idempotency key because it creates a snapshot.
- The UI should make the generated drafts copyable in a later slice, but this first slice only needs to display them.
