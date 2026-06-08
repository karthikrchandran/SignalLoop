# Customer 360 Account Profile Design

Date: 2026-06-08
Status: approved for implementation planning

## Purpose

Customer 360 gives operators one account-first profile for a company and all of
the people, channel activity, and follow-up work attached to that company.

The view combines chatbot, email, voice, prospecting, and timeline context so a
rep can answer a simple question before acting: what has happened with this
account, who is involved, and what should happen next?

## Approved Direction

Customer 360 is an account profile, not a single-contact profile. The first
screen is an Account Command Center:

- The company/account is the primary record.
- Contacts are shown as people inside the account.
- Chatbot, email, voice, and prospecting summaries are visible near the top.
- A next-best-action panel highlights the most important follow-up.
- A unified timeline merges account activity across contacts and channels.

Customer 360 V1 must include a real `accounts` table. It should not rely on
grouping contacts by `company` text as the long-term identity model.

## Goals

- Add first-class account identity to the backend data model.
- Backfill existing contacts into accounts using current company values.
- Attach future imports and lead capture flows to accounts.
- Provide account list and account detail APIs for Customer 360.
- Render an account profile page that combines account identity, contacts,
  chatbot, email, voice, prospecting, next actions, open work, and timeline.
- Keep existing contact and campaign workflows working while the account model
  is introduced.

## Non-Goals

- Do not replace the existing Contacts lead pool in this work package.
- Do not remove `contacts.company`; keep it for compatibility and display.
- Do not build full CRM account ownership, territory assignment, or duplicate
  merge tooling in V1.
- Do not make Customer 360 the write surface for every channel workflow. V1 can
  link or route users to existing channel pages for deeper actions.

## Data Model

Add an `Account` SQLModel table:

- `id`: UUID primary key.
- `workspace_id`: tenant/workspace boundary, indexed.
- `name`: display account name.
- `account_key`: normalized stable key generated from the account name.
- `website_url`: optional account website.
- `industry`: optional industry label.
- `status`: optional lifecycle status, defaulting to an active/open value.
- `summary`: optional account summary text.
- `tags_json`: JSON array for account-level labels.
- `created_at`: creation timestamp.
- `updated_at`: update timestamp.

Add `contacts.account_id` as a nullable foreign key to `accounts.id`.

Use a unique constraint on `(workspace_id, account_key)`. Account keys should be
deterministic from name, lowercase, trimmed, and slug-like. If two different
account names normalize to the same key in one workspace, the create path should
resolve the collision deterministically rather than violating the constraint.

`contacts.company` remains available. For Customer 360, `account_id` is the
source of truth. `company` is a compatibility/display field and can mirror the
account name when created from imports.

## Migration

Create an Alembic migration that:

1. Creates the `accounts` table.
2. Adds nullable `account_id` to `contacts`.
3. Backfills one account per distinct non-empty `(workspace_id, company)` value.
4. Assigns matching contacts to the created account.
5. Adds indexes and constraints needed by the read path.

Contacts with blank or null company remain unassigned. That is intentional for
V1 because inventing placeholder accounts would pollute Customer 360.

## Backend API

Add a `customer_360` API route module under `/api/v1/customer-360`.

`GET /accounts`

Returns searchable account rows:

- account id, name, status, summary, tags, website, industry.
- contact count.
- last activity timestamp.
- high-level chatbot, email, voice, and prospecting counts.
- top next action label or null.

`GET /accounts/{account_id}`

Returns the Account Command Center payload:

- account identity and summary.
- contacts attached to the account.
- channel summary cards for chatbot, email, voice, and prospecting.
- latest prospecting brief when available.
- open work items.
- next-best action.
- unified account timeline.

All queries must enforce workspace isolation. An account id from another
workspace returns 404.

## Aggregation Rules

The profile service loads contacts by `account_id` and aggregates activity for
those contact ids.

Chatbot:

- Use conversations linked through `ChatbotConversation.contact_id`.
- Count open, escalated, agent-active, and resolved states.
- Pull latest message previews for open work and timeline highlights.

Email:

- Use existing sequence and email event state where contact ids are available.
- Count sequence enrollment and recent email delivery/open/click activity.
- If no email events exist, show an empty summary rather than failing the page.

Voice:

- Use `CallRequest.contact_id` and `CallSession` joins.
- Count queued, completed, answered, failed, and follow-up-needed outcomes.
- Include transcript excerpts or unanswered questions only where already
  available and safe to display.

Prospecting:

- Use `ProspectingSnapshot.contact_id`.
- Show the latest account-relevant research summary, suggested next action,
  email draft availability, and voice opener availability.

Timeline:

- Merge channel highlights across all contacts attached to the account.
- Preserve contact names on each timeline event.
- Sort newest first.
- Bound V1 payloads to a practical limit, such as the latest 50 events.

## Frontend

Add `apps/web/src/features/customer-360/` with:

- `api.ts` for account list/detail client calls.
- `Customer360AccountsPage.tsx` for searchable account list.
- `Customer360AccountProfilePage.tsx` for the Account Command Center.
- Small presentational components only when they reduce real duplication.

Add routes:

- `/customer-360`
- `/customer-360/$accountId`

Add a sidebar item named `Customer 360`.

The account profile layout should match the approved mockup:

- Account header with name, metadata, status tags, and key actions.
- Left account summary and contact roster.
- Top channel summary strip for chatbot, email, voice, and prospecting.
- Main unified timeline.
- Right rail for next-best action, prospecting brief, and open work.

## Error And Empty States

- No accounts: show a clear empty state with a path back to contact import.
- Account not found: show a not-found state rather than a blank profile.
- No contacts on an account: keep account identity visible and show an empty
  contact roster.
- No channel activity: keep channel cards visible with zero/empty states.
- Partial aggregation failure: prefer section-level fallback text when feasible.
  Do not hide the account identity or contacts because one channel has no data.

## Testing

Backend tests:

- Account key generation and collision handling.
- Migration/backfill behavior for contacts with matching company values.
- Contact import creating or reusing accounts and assigning `account_id`.
- Account list route returns only accounts in the active workspace.
- Account detail route rejects cross-workspace ids.
- Account detail aggregation includes contacts, chatbot, email, voice,
  prospecting, next action, and timeline data.

Frontend tests:

- Playwright test for `/customer-360` showing accounts.
- Playwright test for `/customer-360/:accountId` showing the account name,
  contacts, channel summaries, next-best action, and timeline.
- Empty-state test for no accounts or no channel activity.

Verification gates:

- Backend targeted tests for Customer 360 and contact import.
- Frontend targeted Playwright spec.
- `npm --workspace frontend run build`.
- Existing repo lint/format checks for touched files.

## Implementation Notes

Keep the first implementation cohesive but bounded. The durable boundary is the
account model and account profile read service. Deep editing workflows can stay
on existing pages until Customer 360 has proven its read model.

The current uncommitted EngageHub AI work already uses useful vocabulary such as
next-best actions, unified work, and journey signals. Customer 360 should reuse
that vocabulary at account scope, not duplicate a second workspace-level
dashboard.
