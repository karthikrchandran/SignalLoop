# Testing Guide

SignalLoop has three test layers. Run the right layer for the change you made.

| Layer | Tool | Where | Use when |
| --- | --- | --- | --- |
| Backend tests | `pytest` (via `uv`) | `apps/api/tests/` | Changing API routes, domain services, models, migrations. |
| Frontend E2E | Playwright | `apps/web/tests/` | Changing UI flows, routes, or shared components. |
| Live smoke | PowerShell driver | `tooling/run-corrective-live-smoke.ps1` | Verifying a running stack end-to-end (manual / pre-release). |

## Backend (`apps/api`)

### Prerequisites

- `uv sync` has been run in `apps/api`.
- Postgres and Redis are running (`.\StartServer.ps1`).
- Migrations are applied (`uv run alembic upgrade head`).

### Run everything

**Never run the mutating API suite against a populated application database.**
The session fixture deletes/recreates users. On a shared native PostgreSQL
installation, use this repository-root command instead:

```powershell
.\.venv\Scripts\python.exe tooling\run-backend-gate.py
```

The runner reads connection credentials privately from `.env`, creates a unique
`signalloop_gate_*` database, sets `POSTGRES_DB` for every fixture, and drops only
that database on exit. Logs are written to `.local-services`. Selectors can be
appended to the command. PostgreSQL must permit the configured role to create
databases. The shared cluster, Redis, and Mailpit are never stopped.

Run the opt-in PostgreSQL migration/locking contracts against Alembic-head
constraints rather than ORM-created tables:

```powershell
.\.venv\Scripts\python.exe tooling\run-backend-gate.py --migrated tests\domain\test_tenant_migration_postgres.py
```

`--migrated` applies Alembic to the disposable database and enables
`RUN_TENANT_PG_TESTS=1`; it does not migrate the original database.

The direct command below is appropriate **only** when the environment already
points to a disposable database (as CI does):

```powershell
cd apps\api
uv run pytest
```

### Run a single file or test

```powershell
uv run pytest tests/api/routes/test_campaigns.py
uv run pytest tests/api/routes/test_campaigns.py::test_create_campaign
```

### Filter by keyword

```powershell
uv run pytest -k "campaign and not delete"
```

### Quiet, fail-fast iteration

```powershell
uv run pytest -q -x --ff
```

### Coverage

The repo has multiple per-group coverage configurations (`.cov_*` files in `apps/api/`). For an ad-hoc whole-suite coverage run:

```powershell
uv run pytest --cov=app --cov-report=term-missing
```

For an HTML report:

```powershell
uv run pytest --cov=app --cov-report=html
start htmlcov\index.html
```

Coverage settings live in `apps/api/pyproject.toml` under `[tool.coverage.*]`.

### Linting & type checks

```powershell
cd apps\api
uv run ruff check .
uv run ruff format --check .
uv run mypy app
```

Apply autofixes with `uv run ruff check --fix .` and `uv run ruff format .`.

The CI workflow currently treats `mypy app` as advisory, but the strict
configuration remains enabled. ORM expressions should use SQLModel's `col()`
helper; explicit SQL type instances belong in `Field(sa_column=Column(...))`,
with nullability, timezone support and defaults preserved. Validate durable
idempotency replay data against the route's declared response type rather than
assuming a stored JSON object is already a response model.

The local `instruction.md` protects `app/main.py` from edits without explicit
approval. Its lifespan function has an explicitly approved `AsyncIterator[None]`
return annotation; strict checking remains enabled without a diagnostic
suppression. The scheduling audit regression tests cover successful writes and
rollback of both creation and update when auditing fails.

## Frontend (`apps/web`)

### Prerequisites

- `npm install` has been run in `apps/web`.
- Playwright browsers are installed (`npx playwright install` once per machine).
- The API and web dev server must be running for E2E specs. Easiest: `.\StartApp.ps1` from the repo root.

### Run everything

```powershell
cd apps\web
npm test
```

### Run a specific spec

```powershell
npm test -- tests/sequences.spec.ts
npm test -- tests/sequences.spec.ts tests/voice-agents.spec.ts
```

### Interactive UI mode (recommended for debugging)

```powershell
npm run test:ui
```

### Lint & build

```powershell
npm run lint     # Read-only Biome checks; no unsafe edits
npm run build    # Type-check + production build
```

### Regenerate the API client after backend route changes

```powershell
# API must be running on :8001
cd apps\web
npm run generate-client
```

Commit the regenerated `src/client/` together with the API change.

### Isolated production-bundle smoke

From the repository root, with local PostgreSQL, Redis and Chromium available:

```powershell
.\.venv\Scripts\python.exe tooling\verify-production-smoke.py
```

This creates and migrates a unique `signalloop_smoke_*` database, builds the
frontend with OIDC mode, and starts owned API/preview processes on loopback
ports 18017/14177. It checks password-login rejection, anonymous denial,
server-session API access, browser routes, discovery request counts, and
logout/session revocation. A short-lived session is issued directly in the
disposable database; this does **not** certify a real identity-provider
redirect/callback. Only the created database and process trees are removed.
No live provider calls are required.

Native PostgreSQL without pgvector can run the standard API/build gate, but
native vector similarity search is **not certified** by this smoke. Deployments
using knowledge retrieval require a compatible installed pgvector extension
and vector-specific verification (CI uses `pgvector/pgvector:pg18`).

Lead-discovery webhooks require authenticated workspace-admin access and a
verified `X-Workspace-Id` header; an arbitrary `workspace_id` query parameter
does not authorize ingestion. Enrichment and promotion audits are scoped to
that verified workspace.

## Live smoke (cross-stack)

```powershell
cd apps\web
npm run test:smoke:live
```

This invokes `tooling/run-corrective-live-smoke.ps1`, which exercises a representative end-to-end path against a fully running stack (API + web + workers). Use it before a release or when validating a recovery procedure. It is slow — don't run it in your tight inner loop.

## Test data

- `seed_db.py` (repo root) populates sample contacts, templates, and a draft campaign. Run with `uv run seed_db.py`.
- `check_user.py` is a small helper for verifying the seeded superuser.
- Playwright specs assume a freshly seeded database. If a spec fails non-deterministically, re-seed before retrying.

## Continuous integration

Pytest, ruff, mypy, and Playwright all run under whichever CI runner the repo is wired to. Always confirm your change passes the equivalent commands above locally before pushing — CI exists to catch what you missed, not to be your first feedback loop.

## Common failure patterns

See [troubleshooting.md](./troubleshooting.md) for things like:

- "tests pass locally but fail in CI" (env var drift, seed-data drift)
- "Playwright spec times out" (API not running, port already taken, slow first-render)
- "Alembic migration mismatch" (forgot to `uv run alembic upgrade head` after pulling)
