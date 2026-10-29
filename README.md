# SignalLoop

SignalLoop is the governed operating platform for multichannel campaign orchestration (voice, email, messaging), autonomous commercial agents, AI lead discovery and waterfall enrichment, and lead-to-cash execution integrated with Revenue OS and eCRM.

The system is architected as a high-performance hybrid monorepo: FastAPI + SQLModel + Casbin RBAC backend (`apps/api`), TanStack Router + Vite + Tailwind operator console (`apps/web`), and an asynchronous multi-worker engine (`apps/workers`) executing background enrichment, scoring, delivery, and agent operations.

## Key Capabilities

- **AI Lead Discovery & Multi-Provider Waterfall Enrichment:** Search prospects across firmographic matrices (industry, revenue, headcount, tech stack, geography), query external providers sequentially (Apollo.io, Clay.com, Burkettopti / leadspti, and deterministic sandbox fallback), canonicalize entities, calculate 4-pillar AI fit scores (0–100), synthesize opportunity briefs with personalized conversation angles, and promote 1-click into CRM contacts.
- **Unified Commercial Agent Suite:** Governed agent registry with capacity metering and slot enforcement across autonomous agents: `LEAD_DISCOVERY`, `LEAD_PREPARATION`, `EMAIL_OUTREACH`, `VOICE_CONVERSATION`, `PROPOSAL_DRAFTING`, `CALENDAR_SCHEDULER`, and `REVENUE_INTERVENTION`.
- **Governed Generative Proposals:** Synthesize commercial proposal drafts grounded in customer requirements, line items, and pricing policies with human review gates and signed event handoffs to eCRM.
- **Autonomous Calendar Scheduling:** Calculate available meeting windows, issue booking links, reconcile timezones, and durably confirm bookings with immutable receipt records.
- **Multichannel Campaigns & Voice Outreach:** Governed email sequences, AI voice calls with custom voice profiles, script versioning, postcall audio transcription, and call summarization.
- **Messaging Hub & Customer 360:** Website chatbot with live knowledge base indexing, operator inbox, conversation containment analytics, and unified customer timeline intelligence.
- **Enterprise Multi-Tenancy & Revenue OS:** Strict workspace/tenant isolation, OIDC/SSO authentication, custom tenant branding, audit logging, and signed event streaming to eCRM.

## Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/)
- Node.js 20+
- npm for the web frontend
- PostgreSQL 18 as the repository baseline (Compose and CI use 18); see the version-safety note below for existing native installations
- Redis for local coordination
- Mailpit for local email capture (`scoop install mailpit`)
- Ollama for local LLM demos (`llama3.2:1b` is the default model)
- Docker Compose is optional for containerized runs, including Docker running in WSL

## Workspace Layout

- `apps/api`: FastAPI backend, SQLModel domain models, auth, commercial agent registry, lead discovery, governance APIs
- `apps/web`: React/Vite/TanStack Router operator console (Outreach, Messaging Hub, Tenant Admin, Platform Control Plane)
- `apps/workers`: Production async worker suite executing lead discovery, lead preparation, proposals, calendar scheduling, email sequences, voice calls, postcall processing, projections, and revenue interventions
- `packages/*`: Shared TypeScript packages (`api-client`, `event-contracts`, `shared-types`, `ui-tokens`)
- `docs/`: Comprehensive documentation tree (User Guide, Developer Guide, Architecture, Sales Materials, Operations)

## Local Development Setup

### Option A — Native local services with uv (recommended)

Postgres and Redis must be reachable on `localhost`. Your existing native startup workflow remains supported; Docker and Supabase are not required.

For a new database installation, use PostgreSQL 18 to match Compose and CI. Check `pg_ctl --version` and the data directory's `PG_VERSION` before changing binaries. Scoop's current `postgresql` package may install a newer major version, so it is not a version-18 pin. Do not downgrade an existing newer native database or point different-major binaries at its data directory. Back up existing databases and plan a supported migration separately if a version change is necessary.

On Windows, with the existing Scoop-managed PostgreSQL installation:

```powershell
# Verify PostgreSQL 18 and reuse the existing cluster without replacing data.
.\StartDatabase.ps1
createdb -U postgres signalloop

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

# 2. In separate terminals — worker suite or individual background workers
cd ..\workers
uv sync
uv run python -m worker_app.main           # runs the full unified background worker suite
# or run individually:
# uv run python -m worker_app.lead_discovery_worker
# uv run python -m worker_app.lead_preparation_worker
# uv run python -m worker_app.proposal_agent_worker
# uv run python -m worker_app.calendar_scheduler_worker
# uv run python -m worker_app.sequence_worker
# uv run python -m worker_app.call_worker
# uv run python -m worker_app.postcall_worker

# 3. Frontend
cd ..\web
npm install
npm run dev     # http://localhost:5173
```

Copy `.env.example` to `.env` only if you do not already have a local environment file, and set your database credentials. The example targets `localhost` for both Postgres and Redis. Leave `POSTGRES_SSLMODE` empty to preserve the existing local connection behavior. Provider credentials (`SENDGRID_*`, `TWILIO_*`, `DEEPGRAM_API_KEY`, `GROQ_API_KEY`) are optional — the adapters fail closed when keys are absent, so the API and UI still boot for development.

Confirm service health:

- API health: `http://localhost:8001/api/v1/utils/health-check/`
- Web app: `http://localhost:5173`
- Mailpit inbox: `http://localhost:8025`

### Near-zero local demo stack

The local demo path uses only local tools: Mailpit for email capture, Ollama for LLM calls, and a `uv`-started faster-whisper service for batch STT.

```powershell
# install once if needed
scoop install mailpit
ollama pull llama3.2:1b

# start local services, API, web, STT, and seed provider selections
.\tooling\demo-up.ps1
```

Provider selections can be reviewed by a superuser in the web app at `Settings -> Providers`. Paid provider keys should stay blank until you register for those services.

### Option B — Docker Compose (optional)

Use Compose only when you specifically want a containerized run:

```bash
docker compose up --build
```

Compose and CI use `pgvector/pgvector:pg18`. The Compose database uses a new `postgres18-data` volume at `/var/lib/postgresql`, with `PGDATA=/var/lib/postgresql/18/docker`. Old volumes are neither reused nor deleted, and their data is not automatically migrated. Check that native or hosted PostgreSQL has the `vector` extension available before using knowledge-base vector search.

## Hosted Database

SignalLoop connects to standard PostgreSQL through SQLModel/SQLAlchemy and Psycopg; it does not require Supabase or Neon. Use the same `POSTGRES_SERVER`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, and `POSTGRES_PASSWORD` configuration for any compatible provider, with `POSTGRES_SSLMODE=require` or the provider's certificate-verifying settings. API, workers, and Alembic share this configuration.

Keep development, launch/customer environments, and eCRM databases separate, with separate credentials. Select a service tier with suitable availability, backups, restore procedures, and monitoring. Do not depend on auto-pausing free tiers for continuous availability. The [launch runbook](docs/operations/scheduled-launch-desktop.md) describes the provider-neutral hosted setup; it does not change the native local startup path.

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

## Documentation

Full handover documentation lives under [`docs/`](docs/):

- [Developer guide](docs/developer-guide/README.md) — onboarding, codebase tour, env vars, testing, troubleshooting.
- [User guide](docs/user-guide/signalloop%20user%20guide.md) — operator-facing product walkthrough.
- [Architecture overview](docs/architecture/README.md) — system context, data model, process flows.
- [Operations / dev scripts](docs/operations/dev-scripts.md) — start/stop scripts and ports.
- [Provider setup](docs/operations/provider-setup.md) — local Mailpit/Ollama/faster-whisper first, paid providers only when registered.

## Running Tests

Backend tests:

```bash
cd apps/api
uv run pytest
```

Frontend checks:

```bash
cd apps/web
npm install
npm run lint
npm run build
```

## Services

- PostgreSQL for transactional campaign and governance records (audit events also live here in the `audit_events` table)
- Redis for async coordination and short-lived state
- Mailpit, Ollama, and faster-whisper for the local no-spend demo path

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

- The frontend starter is present in `apps/web`, but the SignalLoop-specific screens still need to be layered on top of the starter routes.
- The backend domain models have been added alongside the starter auth/user flows; Alembic migrations and runtime validation are still required before calling the stack production-ready.
