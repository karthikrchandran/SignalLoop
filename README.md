# EngageHub

EngageHub is a hybrid monorepo for governed campaign orchestration across email and voice channels. The implementation baseline follows the FastAPI full-stack starter structure under `apps/api` and `apps/web`, with additional workspace stubs for workers, mobile, and shared packages.

## Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/)
- Node.js 20+
- [Bun](https://bun.sh/) for the web frontend
- Docker Desktop with Docker Compose is optional for containerized runs

## Workspace Layout

- `apps/api`: FastAPI backend, SQLModel domain, auth, governance APIs
- `apps/web`: React/Vite operator console
- `apps/workers`: worker process scaffold for async enforcement and delivery jobs
- `apps/mobile`: mobile shell scaffold
- `packages/*`: shared types, contracts, client, and design token packages

## Local Development Setup

### Option A — Native local services with uv (recommended)

Postgres and Redis must be reachable on `localhost`. On Windows with scoop:

```powershell
# Postgres (already installed in this workspace via scoop)
scoop install postgresql           # if not yet installed
pg_ctl -D "$env:USERPROFILE\scoop\apps\postgresql\current\data" -l postgres.log start
createdb -U postgres engagehub

# Redis — scoop ships a Windows port; or use Memurai
scoop install redis
redis-server --service-install
redis-server --service-start
```

Then from the repo root:

```powershell
# 1. Backend deps + migrations + API, using uv
cd apps\api
uv sync
uv run alembic upgrade head
uv run python -m app.initial_data         # seed superuser
uv run fastapi dev app/main.py --port 8001 # http://localhost:8001

# 2. In separate terminals — workers (each is a long-running process)
uv run python -m app.workers.sequence_worker
uv run python -m app.workers.call_worker
uv run python -m app.workers.postcall_worker

# 3. Frontend
cd ..\web
bun install
bun run dev     # http://localhost:5173
```

`.env` already targets `localhost` for both Postgres and Redis, so no further config edits are needed for local-only runs. Provider credentials (`SENDGRID_*`, `TWILIO_*`, `DEEPGRAM_API_KEY`, `GROQ_API_KEY`) are optional — the adapters fail closed when keys are absent, so the API and UI still boot for development.

Confirm service health:

- API health: `http://localhost:8001/api/v1/utils/health-check/`
- Web app: `http://localhost:5173`

### Option B — Docker Compose (optional)

Use Compose only when you specifically want a containerized run:

```bash
docker compose up --build
```

## Backend Dependency Install

Install backend dependencies from repo root:

```bash
cd apps/api
uv sync
```

## Database Migrations

Run Alembic migrations after the stack is up:

```bash
cd apps/api
uv run alembic upgrade head
```

Create a new migration when models change:

```bash
cd apps/api
uv run alembic revision --autogenerate -m "describe change"
```

## Running Tests

Backend tests:

```bash
cd apps/api
uv run pytest
```

Frontend checks:

```bash
cd apps/web
bun install
bun run lint
bun run build
```

## Services

- PostgreSQL for transactional campaign and governance records (audit events also live here in the `audit_events` table)
- Redis for async coordination and short-lived state

## Current Story Coverage

- Story 1.1: monorepo bootstrap, compose stack, worker/mobile/package scaffolds
- Story 1.2: campaign intake, import preview, mapping, segmentation, strategy assignment APIs
- Story 1.3: template library, preview, publish, and offer pack APIs
- Story 1.4: governance policy, approval, and pause/resume control APIs

## Architecture Docs

Architecture documentation lives under `docs/architecture`:

- `docs/architecture/README.md`
- `docs/architecture/architecture-stories.md`
- `docs/architecture/data-model.md`
- `docs/architecture/process-flows.md`

## Notes

- The frontend starter is present in `apps/web`, but the EngageHub-specific screens still need to be layered on top of the starter routes.
- The backend domain models have been added alongside the starter auth/user flows; Alembic migrations and runtime validation are still required before calling the stack production-ready.
