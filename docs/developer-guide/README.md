---
title: SignalLoop Developer Guide
description: Entry point for engineer handovers — onboarding, codebase tour, local setup, testing, and troubleshooting.
date: 2026-05-28
---

# SignalLoop Developer Guide

This is the starter pack for any engineer joining or taking over the SignalLoop codebase. Read it in order on day one; come back to individual pages later as reference.

## Read in this order

1. [Onboarding & first-day handover](./onboarding.md) — accounts, tools, clone, first successful run.
2. [Codebase tour](./codebase-tour.md) — what lives where in the monorepo.
3. [Local development](../operations/dev-scripts.md) — the start/stop scripts for the full stack.
4. [Environment variables](./environment-variables.md) — what each `.env` value does and which are optional.
5. [Testing guide](./testing.md) — how to run backend pytest, frontend Playwright, and smoke tests.
6. [Troubleshooting](./troubleshooting.md) — known failure modes and fixes.

## Reference docs

- [Architecture overview](../architecture/README.md) — system context, data model, process flows.
- [Operations / provider setup](../operations/provider-setup.md) — local Mailpit/Ollama/faster-whisper first; paid providers after registration.
- [User guide](../user-guide/signalloop%20user%20guide.md) — what the product does, from an operator's perspective.
- [Top-level README](../../README.md) — minimal quick-start.

## Repository at a glance

| Path | Purpose |
| --- | --- |
| `apps/api` | FastAPI backend (SQLModel, Alembic, Casbin RBAC). Primary system core. |
| `apps/web` | React + Vite + TanStack Router operator console. |
| `apps/workers` | Async worker scaffold (sequence, call, post-call). Run as separate processes. |
| `apps/mobile` | Mobile shell scaffold (not yet active). |
| `packages/api-client` | Generated TypeScript client (from FastAPI OpenAPI). |
| `packages/event-contracts` | Shared event payload definitions. |
| `packages/shared-types` | Cross-app TypeScript types. |
| `packages/ui-tokens` | Design tokens shared by the web app. |
| `docs/` | This documentation tree. |
| `_bmad/`, `_bmad-output/` | BMAD planning artifacts (PRD, epics, stories). Read-only for most engineers. |
| `tooling/` | Repo-wide helper scripts (smoke tests, linters, templates). |
| `tests/` | Cross-app integration/e2e scaffolding. |

## Who maintains what

- **Backend / API / workers** — `apps/api`, `apps/workers`. Python 3.10+, `uv`.
- **Frontend / web** — `apps/web`. Node 20+, npm (Bun supported).
- **Shared packages** — `packages/*`. TypeScript only; consumed by `apps/web`.
- **Infrastructure / dev scripts** — root-level `Start*.ps1` / `Stop*.ps1`, `compose*.yml`.

## Day-one success criteria

You're considered "set up" when you can:

1. Run `.\StartServer.ps1` and see Postgres, Redis, Mailpit reporting UP.
2. Run `.\StartApp.ps1` and reach `http://localhost:5173` and `http://localhost:8001/docs` in a browser.
3. Sign in to the web app with the seeded superuser (see [onboarding](./onboarding.md)).
4. For local-provider demos, run `.\tooling\demo-up.ps1` and confirm `Settings -> Providers` shows the local selections.
5. Run the backend smoke pytest group and the frontend Playwright smoke suite — both green.

If any of those fail, jump to [troubleshooting](./troubleshooting.md) before continuing.
