# Platform Shared Data Foundation Validation

Validated on 2026-07-26 after completing the platform-owned account, contact,
lead-identity, and order-identity implementation.

## Passed checks

- `cd apps/api; uv run pytest tests/unit/test_platform_shared_repository.py tests/unit/test_platform_shared_import.py tests/unit/test_platform_shared_reconciliation.py tests/api/routes/test_platform_shared.py -q`
  - Passed: `29 passed in 2.59s`.
  - Covers local-first reads, deterministic public IDs, paged eCRM imports,
    account/contact/lead/order identity persistence, reconciliation, and the
    admin import/reconciliation routes.

- `cd apps/api; uv run alembic heads`
  - Passed with one head: `psid_20260726`.

- `cd apps/api; $env:POSTGRES_DB='emv_platform_shared_foundation_verify_20260726'; uv run alembic upgrade head`
  - Passed against a disposable local PostgreSQL database.
  - Resulting schema includes `platform_shared_accounts`,
    `platform_shared_contacts`, and `platform_shared_identities`; the database
    is recorded at `psid_20260726`.
  - The migration chain expands Alembic's historical 32-character version
    column before applying descriptive shared-record revisions.

- `cd "C:\My Workspace\eCRM"; npm test -- src/server/shared-records/export.test.ts`
  - Passed: 7 tests.

- `cd "C:\My Workspace\eCRM"; npm run typecheck`
  - Passed.

## Configuration-gated checks

- `uv run python -m app.scripts.import_ecrm_shared_records --workspace-id default --dry-run`
  - Correctly stops before any write because `ECRM_SHARED_API_TOKEN` is not
    configured in this local environment. This is an intentional deployment
    configuration prerequisite, not an implementation failure.

- The existing local eMailVoice database contains application tables but has
  no Alembic history, so applying the complete chain to it starts at the
  initial migration and encounters a pre-existing `user` table. It was left
  unchanged. Use the approved baseline/backup procedure in the cutover runbook
  before applying the migration to that legacy database.

## Cutover decision

The code and schema are ready for a configured pilot. Complete the dry-run
import and reconciliation with the eCRM endpoint/token, then set
`USE_LOCAL_SHARED_RECORDS=true` per the documented runbook.
