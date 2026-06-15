# Release Gate Validation - 2026-06-05

## Summary

Release-gate validation passed for the SignalLoop corrective/release slice after
repairing one fresh-database migration blocker, stale frontend E2E harness
failures, and the Vite production-build chunk warning.

The key missing scenario was a clean Alembic upgrade path for the provider
selection migration. Existing tests covered provider behavior, but a fresh
Postgres database could not migrate to head because the new migration assumed
the `notificationprovider` enum already existed.

## Fix Applied

- Updated `apps/api/app/alembic/versions/m8b9c0d1e2f3_add_workspace_provider_selection_and_capability_enums.py`
  to create the `notificationprovider` enum when absent, then idempotently add
  all current provider values.
- Added `apps/api/tests/unit/test_provider_selection_migration.py` to keep the
  migration provider/capability constants aligned with `NotificationProvider`
  and `ProviderCapability`.
- Started local Postgres under `.tmp/local-postgres`, created the `signalloop`
  database, and migrated it to head.
- Removed the retired starter-template `/items` Playwright suite.
- Updated auth E2E helpers/tests to match the current SignalLoop dashboard copy,
  wait for sign-up network completion, and cover invalid-token redirect.
- Added local-environment rate-limit disabling while keeping rate limiting on
  by default for staging/production.
- Converted TanStack Router and React Query devtools to development-only lazy
  imports so they are excluded from the production entry bundle.
- Added Vite manual vendor chunking for core React dependencies, TanStack,
  Radix, charts, icons, and shared utility libraries.

## Gates Executed

| Gate | Result | Notes |
| --- | --- | --- |
| Fresh Alembic upgrade | Passed | Local Postgres upgraded to `m8b9c0d1e2f3 (head)`. |
| Backend test suite | Passed | `uv run pytest tests/ -q --no-header`: 503 passed. |
| Provider/config focused tests | Passed | Impacted follow-up tests: 5 passed. |
| Frontend production build | Passed | `npm run build`; no Vite large-chunk or circular chunk warnings. |
| Corrective Playwright slices | Passed | Provider setup, Sequences, Voice Setup: 15 passed. |
| Live corrective smoke | Passed | `tooling/run-corrective-live-smoke.ps1`: 1 passed. |
| Full frontend Chromium suite | Passed | `npx playwright test --project=chromium --workers=1`: 74 passed. |

## Environment Notes

- Docker was not available on PATH in this terminal, so compose-based validation
  could not be used.
- Redis was already reachable on `localhost:6379`.
- Local Postgres is running from `.tmp/local-postgres` on `localhost:5432`.
- The local API is running on `http://localhost:8001`.
- The local web dev server is running on `http://localhost:5173`.
- The local API was started with direct `uvicorn` because the
  FastAPI CLI banner hit a Windows `cp1252` encoding issue in hidden-process
  output.

## Residual Caveats

- No residual caveats from the validated release gates.
