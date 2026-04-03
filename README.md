# EngageHub

EngageHub is a hybrid monorepo for governed campaign orchestration across email and voice channels. The implementation baseline follows the FastAPI full-stack starter structure under `apps/api` and `apps/web`, with additional workspace stubs for workers, mobile, and shared packages.

## Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/)
- Node.js 20+
- Docker Desktop with Docker Compose

## Workspace Layout

- `apps/api`: FastAPI backend, SQLModel domain, auth, governance APIs
- `apps/web`: React/Vite operator console
- `apps/workers`: worker process scaffold for async enforcement and delivery jobs
- `apps/mobile`: mobile shell scaffold
- `packages/*`: shared types, contracts, client, and design token packages

## Local Development Setup

1. Copy `.env.example` to `.env`.
2. Start infrastructure and app services:

	```bash
	docker compose up --build
	```

3. Confirm service health:

	- API health: `http://localhost:8000/api/v1/utils/health-check/`
	- Web app: `http://localhost:5173`

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

- PostgreSQL for transactional campaign and governance records
- MongoDB for audit/event storage
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
