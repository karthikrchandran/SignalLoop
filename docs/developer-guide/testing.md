---
title: Testing Guide
description: How to run backend pytest, frontend Playwright, and live smoke tests on EngageHub.
date: 2026-05-28
---

# Testing Guide

EngageHub has three test layers. Run the right layer for the change you made.

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
npm run lint     # Biome lint + autofix
npm run build    # Type-check + production build
```

### Regenerate the API client after backend route changes

```powershell
# API must be running on :8001
cd apps\web
npm run generate-client
```

Commit the regenerated `src/client/` together with the API change.

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
