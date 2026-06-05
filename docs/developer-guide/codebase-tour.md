---
title: Codebase Tour
description: A guided walk through the EngageHub monorepo so a new engineer knows where things live before they start changing code.
date: 2026-05-28
---

# Codebase Tour

EngageHub is a hybrid monorepo: Python backend + workers in `apps/api` and `apps/workers`, a React/Vite frontend in `apps/web`, and a few shared TypeScript packages. There is no Lerna/Nx orchestration — each app is independently runnable, with PowerShell scripts at the repo root tying them together for local dev.

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
| `contacts.py` | Lead pool, CSV import, timeline. |
| `controls.py` | Daily caps, quiet hours, emergency pause/resume. |
| `voice.py`, `calls.py`, `scripts.py` | Voice agents, call sessions, scripts. |
| `provider_credentials.py` | Per-workspace provider credential management. |
| `webhooks.py`, `triggers.py`, `signals.py` | Inbound provider webhooks, trigger evaluation, behavioural signals. |
| `audit_log.py` | Append-only audit trail readback. |
| `dashboard.py`, `kpis.py` | Aggregate dashboards and KPI surfaces. |
| `workspace_runtime_config.py` | Per-workspace runtime configuration. |
| `utils.py` | Health-check + utility endpoints. |
| `private.py` | Internal-only endpoints (not exposed publicly). |

### Important conventions

- Every mutating request must carry `X-Workspace-Id` and `Idempotency-Key` headers. `request_context.py` enforces this.
- Casbin policy lives in `core/` and is loaded at startup; authorisation decisions go through helpers, not raw `if user.role == ...` checks.
- Append-only audit goes into the `audit_events` table with a JSONB payload column — read `apps/api/app/domain/audit.py` (or equivalent service) before adding new event types.
- Background work is enqueued, not executed inline. The actual delivery loop is implemented in `apps/api/app/workers/`.

## `apps/workers` — Async workers

Three worker processes, each launched independently:

| Worker | Entry point | Job |
| --- | --- | --- |
| Sequence worker | `python -m app.workers.sequence_worker` | Sends queued email steps via SendGrid. |
| Call worker | `python -m app.workers.call_worker` | Places Twilio outbound calls; respects daily cap and quiet hours. |
| Postcall worker | `python -m app.workers.postcall_worker` | Transcribes recordings (Deepgram) and summarises (Groq). |

The `StartApp.ps1 -Workers` flag launches all three in separate named PowerShell windows. They share the API's `app/` package and the same `.env`.

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
