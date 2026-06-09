# Account Management Design

Date: 2026-06-09
Status: approved for implementation planning

## Purpose

Account Management turns the Customer 360 read model into an operational account workspace. Operators need to create and maintain company accounts, clean up account metadata, and move contacts into the right account without losing the channel history already shown in Customer 360.

## Approved Direction

Build Account Management as the next bounded Customer 360 slice:

- Keep `accounts` as the account identity source of truth.
- Keep Customer 360 as the primary account list/profile surface.
- Add account create and edit actions to the Customer 360 accounts page and account profile.
- Add contact assignment controls so existing contacts can be linked to, moved between, or unlinked from accounts.
- Do not introduce a separate full CRM module in this slice.

## Goals

- Add workspace-scoped account write APIs.
- Validate account names and prevent duplicate normalized account keys in a workspace.
- Allow account metadata updates for name, website, industry, status, summary, and tags.
- Allow contact account reassignment from an account profile.
- Keep `contacts.company` synchronized with the linked account name when a contact is assigned.
- Keep existing contact import behavior intact.
- Refresh Customer 360 list/detail views after account or contact assignment changes.

## Non-Goals

- Do not build account owner assignment, territories, lifecycle automation, merge tooling, or duplicate resolution.
- Do not delete accounts in V1. Empty accounts can remain visible and editable.
- Do not change campaign audience semantics.
- Do not rewrite the existing Contacts page beyond what is needed for account assignment visibility.

## Backend API

Add an account command route module under `/api/v1/accounts`.

`POST /accounts`

Creates an account in the active workspace. Request fields:

- `name`: required, trimmed, 1-255 characters.
- `website_url`: optional URL/text.
- `industry`: optional, max 255 characters.
- `status`: optional, default `active`.
- `summary`: optional text.
- `tags`: optional string array.

Response: `AccountPublic`.

Duplicate normalized names in the same workspace return HTTP 409 with detail `Account already exists`.

`PATCH /accounts/{account_id}`

Updates account metadata in the active workspace. Renaming an account regenerates `account_key`. If the new key collides with another account in the same workspace, return HTTP 409. Existing linked contacts keep their `account_id`; contacts whose `company` matched the old account name should be updated to the new account name.

Response: `AccountPublic`.

`POST /accounts/{account_id}/contacts`

Assigns contacts to the account. Request fields:

- `contact_ids`: required list of UUIDs, 1-100.

Every contact must belong to the active workspace. A cross-workspace or unknown id returns HTTP 404. On success, set `contacts.account_id` to the target account and `contacts.company` to the account name.

Response includes `account_id`, `assigned_count`, and `contact_ids`.

`DELETE /accounts/{account_id}/contacts/{contact_id}`

Unlinks one contact from the account. The contact must currently belong to the target account and active workspace. On success, set `contacts.account_id` to null and leave `contacts.company` unchanged for display continuity.

Response includes `account_id`, `unassigned_count`, and `contact_ids`.

## Frontend

Extend `apps/web/src/features/customer-360/` rather than creating a new top-level module.

Accounts list:

- Add `New account` button.
- Use a dialog form for account create.
- Refresh the list after create.
- Open the new account profile after successful create.

Account profile:

- Add `Edit account` dialog for account metadata.
- Add an `Assign contacts` dialog with searchable unassigned/all contacts.
- Add contact row action to unlink a contact from the account.
- Refresh the profile after edit, assign, or unlink.

Contacts display:

- Keep the existing Contacts page intact.
- Ensure contact list types include `account_id`, because assignment dialogs need to distinguish unassigned and already linked contacts.

## Error And Empty States

- Create duplicate: show inline feedback `Account already exists`.
- Edit conflict: keep the dialog open and show the conflict message.
- Assign no contacts selected: disable the assign button.
- Account with no contacts: keep the profile visible and show the existing empty contacts state plus an assign action.
- Unlink failure: show section-level feedback and keep the last loaded profile.

## Testing

Backend tests:

- Account create succeeds and returns workspace-scoped account fields.
- Account create rejects duplicate normalized names with 409.
- Account patch updates metadata and rejects cross-workspace ids.
- Account rename updates linked contacts that still mirror the old account name.
- Contact assignment moves contacts into an account and syncs company.
- Contact unlink clears `account_id`.
- Cross-workspace contact assignment is rejected.

Frontend tests:

- Customer 360 account list can create an account.
- Account profile can edit account metadata.
- Account profile can assign an existing contact.
- Account profile can unlink a contact.
- Duplicate create/edit errors are visible.

Verification gates:

- `uv run pytest tests/api/routes/test_accounts.py tests/api/routes/test_customer_360.py tests/domain/test_accounts_service.py`
- `npx playwright test tests/customer-360.spec.ts --project=chromium --reporter=line`
- `npm run build` from `apps/web`.

