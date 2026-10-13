# Codebase Tour

SignalLoop is a hybrid monorepo: Python backend + workers in `apps/api` and `apps/workers`, a React/Vite frontend in `apps/web`, and a few shared TypeScript packages. There is no Lerna/Nx orchestration — each app is independently runnable, with PowerShell scripts at the repo root tying them together for local dev.

## Top-level layout

```
eMailVoice/
├── apps/
│   ├── api/         FastAPI backend, SQLModel, Alembic, Casbin RBAC
│   ├── web/         React + Vite + TanStack Router operator console
│   ├── workers/     Long-running async workers (sequence, call, postcall)
│   └── mobile/      Mobile shell scaffold (not active)
├── packages/
│   ├── api-client/      Generated TS client (from FastAPI OpenAPI)
│   ├── event-contracts/ Shared event payload definitions
│   ├── shared-types/    Cross-app TypeScript types
│   └── ui-tokens/       Design tokens
├── docs/            This documentation tree
├── tests/           Cross-app integration/e2e scaffolding
├── tooling/         Helper scripts (smoke tests, linters, templates)
├── _bmad/           BMAD framework files (skills, agents, workflows)
├── _bmad-output/    BMAD planning artifacts (PRD, epics, stories, sprints)
├── StartServer.ps1  Start Postgres + Redis + Mailpit
├── StopServer.ps1   Stop Postgres + Redis + Mailpit
├── StartApp.ps1     Start API + Web (+ optional Workers)
├── StopApp.ps1      Stop API + Web + Workers
├── compose.yml      Docker Compose (optional)
├── seed_db.py       Dev seed script for sample contacts/templates/campaign
└── pyproject.toml   Repo-root Python config (lint targets)
```

## `apps/api` — FastAPI backend

```
apps/api/
├── app/
│   ├── main.py               FastAPI app factory + middleware wiring
│   ├── core/                 Settings, security, db engine, casbin policy
│   ├── api/
│   │   ├── deps.py           Dependency-injection helpers
│   │   ├── request_context.py Workspace + idempotency + correlation middleware
│   │   └── routes/           One module per resource (see table below)
│   ├── domain/               Business logic, policy engine, services
│   ├── domain_models.py      SQLModel domain entities
│   ├── models.py             Auth/user models
│   ├── infrastructure/       Provider adapters (SendGrid, SMTP, Twilio, Deepgram, Groq, Ollama, faster-whisper)
│   ├── workers/              Worker entry points (called by scripts/processes)
│   ├── alembic/              Database migrations
│   ├── email-templates/      MJML/HTML templates for transactional email
│   ├── initial_data.py       Seeds the FIRST_SUPERUSER on first boot
│   └── tests_pre_start.py    Connectivity wait for pytest in containers
├── tests/                    Pytest suite (api/, domain/, infrastructure/)
├── scripts/                  Backend-only helper scripts
├── alembic.ini               Alembic config
├── pyproject.toml            Backend deps + pytest + coverage config
└── Dockerfile                Backend container image
```

### Route modules (`apps/api/app/api/routes/`)

| Module | Purpose |
| --- | --- |
| `login.py`, `users.py` | Auth, password reset, user CRUD. |
| `campaigns.py`, `campaign_health.py` | Campaign intake, audience selection, health metrics. |
| `templates.py`, `offer_packs.py` | Template/offer-pack governance and publishing. |
| `sequences.py` | Sequence definition and enrolment. |
| `contacts.py`, `accounts.py` | Lead pool, CSV import, timeline, customer accounts. |
| `lead_discovery.py` | AI Lead Discovery, waterfall enrichment gateway, 4-pillar scoring, CRM promotion, external webhooks. |
| `lead_preparation.py` | Autonomous lead preparation agent, versioned scoring policies, worker leases, evidence briefs. |
| `commercial_agents.py` | Commercial agent registry, slot allocation, and capacity metering. |
| `proposal_agent.py` | Governed generative proposal drafting, review workflows, grounding, and eCRM handoffs. |
| `scheduling.py` | Autonomous Calendar Scheduler Agent, meeting slot discovery, booking links, and durable confirmations. |
| `customer_360.py` | Unified customer 360 profile, cross-channel engagement timelines, and next best action. |
| `controls.py` | Daily caps, quiet hours, emergency pause/resume. |
| `voice.py`, `calls.py`, `scripts.py` | Voice agents, call sessions, scripts, voice profile management. |
| `provider_credentials.py` | Per-workspace provider credential management. |
| `webhooks.py`, `triggers.py`, `signals.py` | Inbound provider webhooks, trigger evaluation, behavioural signals. |
| `audit_log.py` | Append-only audit trail readback. |
| `dashboard.py`, `kpis.py` | Aggregate dashboards and KPI surfaces. |
| `revenue_essentials.py`, `revenue_interventions.py` | Revenue OS core intelligence, risk detection, and corrective actions. |
| `ecrm_installations.py` | eCRM installation bindings and revenue projections. |
| `tenant_admin.py`, `platform_admin.py` | Tenant administration, platform control plane, and product entitlements. |
| `oidc.py`, `public_branding.py`, `suite_context.py` | SSO/OIDC identity, custom branding assets, and suite context. |
| `workspace_runtime_config.py` | Per-workspace runtime configuration. |
| `utils.py` | Health-check + utility endpoints. |
| `private.py` | Internal-only endpoints (not exposed publicly). |

### Important conventions

- Every mutating request must carry `X-Workspace-Id` and `Idempotency-Key` headers. `request_context.py` enforces this.
- Casbin policy lives in `core/` and is loaded at startup; authorisation decisions go through helpers, not raw `if user.role == ...` checks.
- Append-only audit goes into the `audit_events` table with a JSONB payload column — read `apps/api/app/domain/audit.py` (or equivalent service) before adding new event types.
- Background work is enqueued, not executed inline. The actual delivery and agent loops are implemented in `apps/workers/worker_app/`.

## `apps/workers` — Async workers

Nine worker processes, run via `apps/workers/worker_app/main.py` or launched individually:

| Worker | Entry point (`apps/workers/worker_app/`) | Job |
| --- | --- | --- |
| Lead discovery worker | `lead_discovery_worker.py` | Polls discovered lead batches, executes waterfall enrichment, and calculates 4-pillar AI scores. |
| Lead preparation worker | `lead_preparation_worker.py` | Evaluates contact pools against versioned scoring policies with atomic lease locks. |
| Proposal agent worker | `proposal_agent_worker.py` | Generates governed proposal drafts grounded in customer requirements and pricing policies. |
| Calendar scheduler worker | `calendar_scheduler_worker.py` | Evaluates meeting windows, issues booking links, and durably reconciles calendar invites. |
| Sequence worker | `sequence_worker.py` | Sends queued email steps via SendGrid/SMTP with daily caps and quiet hours. |
| Call worker | `call_worker.py` | Places Twilio/Vapi outbound voice calls respecting daily caps and quiet hours. |
| Postcall worker | `postcall_worker.py` | Transcribes audio (Deepgram/faster-whisper) and summarizes calls (Groq/Ollama). |
| Projection worker | `projection_worker.py` | Projects multi-tenant events and synchronizes cross-product state. |
| Revenue intervention worker | `revenue_intervention_worker.py` | Evaluates revenue risk and executes governed corrective interventions. |

The `StartApp.ps1 -Workers` flag launches the worker suite. Workers share the API's `app/` domain packages and the same `.env`.

## `apps/web` — React operator console

```
apps/web/
├── src/
│   ├── main.tsx              App entrypoint
│   ├── routes/               TanStack Router file-based routes
│   ├── routeTree.gen.ts      Auto-generated route tree (do not edit by hand)
│   ├── features/             Per-feature UI (campaigns, sequences, contacts, ...)
│   ├── components/           Shared UI primitives (shadcn-style)
│   ├── hooks/                Cross-cutting React hooks
│   ├── lib/, utils.ts        Helpers
│   ├── client/               Generated API client (regenerated from OpenAPI)
│   └── index.css             Tailwind entry
├── tests/                    Playwright end-to-end specs
├── playwright/               Playwright fixtures and helpers
├── playwright.config.ts      Playwright configuration
├── openapi-ts.config.ts      Config for regenerating `src/client/`
├── vite.config.ts            Vite + Tailwind v4 + TanStack plugins
└── package.json              Frontend deps + npm scripts
```

### Key npm scripts (`apps/web/package.json`)

| Script | Purpose |
| --- | --- |
| `npm run dev` | Vite dev server on :5173. |
| `npm run build` | Type-check then build for production. |
| `npm run lint` | Biome lint + autofix. |
| `npm run generate-client` | Regenerate `src/client/` from the running API's OpenAPI. |
| `npm test` | Playwright end-to-end tests. |
| `npm run test:ui` | Playwright UI mode for debugging specs. |
| `npm run test:smoke:live` | Cross-stack corrective live-smoke (PowerShell driver). |

### Regenerating the API client

When you add or change a FastAPI route, the TS client under `apps/web/src/client/` will be stale.

```powershell
# API must be running on :8001
cd apps\web
npm run generate-client
```

Commit the regenerated client alongside the API change.

## `packages/` — Shared packages

| Package | Purpose | Consumed by |
| --- | --- | --- |
| `api-client` | Hand-curated client surface on top of the generated client. | `apps/web` |
| `event-contracts` | Event payload type definitions shared between API and consumers. | `apps/web`, future workers |
| `shared-types` | Domain types shared across TS apps. | `apps/web`, `apps/mobile` |
| `ui-tokens` | Tailwind/CSS design tokens. | `apps/web`, `apps/mobile` |

These packages are referenced directly via relative paths from the consumer's `tsconfig.json`; there is no separate publish step.

## `docs/` — Documentation

| Folder | Audience |
| --- | --- |
| `docs/user-guide/` | End users (campaign operators, admins). |
| `docs/developer-guide/` | Engineers — this folder. |
| `docs/architecture/` | Architecture stories, data model, diagrams. |
| `docs/operations/` | Dev scripts, provider setup. |
| `docs/runbooks/` | Operational procedures (currently being filled in). |
| `docs/api/` | API-specific reference (currently a stub — the live OpenAPI at `/docs` is the source of truth). |

## `_bmad/` and `_bmad-output/`

`_bmad/` holds the BMAD methodology files (agents, skills, workflows). `_bmad-output/` holds the *output* of running those workflows on this project:

- `_bmad-output/planning-artifacts/` — PRD, epics, architecture decisions, sprint status.
- `_bmad-output/implementation-artifacts/` — per-story implementation notes.
- `_bmad-output/brainstorming/` — discovery sessions.
- `_bmad-output/project-context.md` — the canonical AI-context summary.

Treat these as read-only unless you are explicitly running a BMAD workflow.

## `tooling/`

Repo-wide helpers that don't belong to a single app:

- `tooling/run-corrective-live-smoke.ps1` — cross-stack live smoke driver.
- `tooling/linters/` — shared lint configuration.
- `tooling/templates/` — file templates used by scaffolding scripts.

## Where business logic lives

A new engineer's first instinct is usually to grep for `POST /campaigns`. The actual logic flow is:

1. Route module in `apps/api/app/api/routes/` — parses request, calls into domain service.
2. Domain service in `apps/api/app/domain/` — encodes business rules, writes audit events, enqueues async work.
3. SQLModel entities in `apps/api/app/domain_models.py` — persistence.
4. Provider adapter in `apps/api/app/infrastructure/` — only when external IO is needed; always called from a worker, never inline from a request handler.

Stick to that order when adding new behaviour.
