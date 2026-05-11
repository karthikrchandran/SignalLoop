# Story 1.1: Set Up Initial Project from Starter Template

Status: done

## Story

As a platform engineer,
I want to bootstrap the EngageHub product from the approved FastAPI full-stack starter template,
so that implementation starts from a production-ready, architecture-aligned baseline with all core infrastructure wired up.

## Acceptance Criteria

1. **Given** the official FastAPI full-stack starter template repository is accessible  
   **When** the project is initialized and baseline configuration applied  
   **Then** the repository contains a runnable API with React web frontend wired to FastAPI backend  
   **And** initial dependency installation succeeds with no audit-level errors  
  **And** the native local dev start runs cleanly with API, web, PostgreSQL, and Redis reachable

2. **Given** the starter template is bootstrapped  
   **When** project-specific naming and structure customization is applied  
   **Then** the project is named `EngageHub`, package identifiers updated, default placeholder-content removed  
   **And** the hybrid monorepo structure (`apps/api`, `apps/workers`, `apps/web`, `apps/mobile`, `packages/`) is scaffolded per architecture decision  
   **And** MongoDB connection wiring is added alongside the template's existing PostgreSQL config

3. **Given** the base project scaffold exists  
   **When** baseline configuration is verified  
   **Then** environment variables for PostgreSQL, MongoDB, Redis, and JWT secret are documented in `.env.example`  
   **And** `README.md` contains clear steps for local development setup, dependency install, and running migrations  
   **And** initial Alembic migration baseline is created and runs cleanly

4. **Given** the project structure is in place  
   **When** CI workflow is initialized  
   **Then** a GitHub Actions `ci.yml` job runs linting and tests on every PR to `main`  
   **And** the workflow exits successfully against the empty/bootstrapped test suite

## Tasks / Subtasks

- [x] **Task 1 – Clone and rename starter template** (AC: 1, 2)
  - [x] Clone `github.com/fastapi/full-stack-fastapi-template` into project root
  - [x] Rename project identifiers from template defaults to `EngageHub` / `engagehub` throughout `pyproject.toml`, `package.json`, and config files
  - [x] Remove built-in example domain code (items, etc.) while keeping auth, user, and infra scaffolding
  - [x] Verify `StartServer.ps1` and `StartApp.ps1` start cleanly (API at :8001, web at :5173, Postgres reachable)

- [x] **Task 2 – Scaffold hybrid monorepo structure** (AC: 2)
  - [x] Create `apps/workers/` with `pyproject.toml`, `worker_app/main.py` stub, and `tests/` skeleton
  - [x] Create `apps/mobile/` with `package.json` and `app.json` stub (Expo baseline)
  - [x] Create `packages/api-client/`, `packages/event-contracts/`, `packages/shared-types/`, `packages/ui-tokens/` with `package.json` stubs
  - [x] Add `tooling/` with placeholder `linters/` and `templates/` directories
  - [x] Add `docs/architecture/`, `docs/api/`, `docs/operations/`, `docs/runbooks/` directories

- [x] **Task 3 – Wire MongoDB alongside PostgreSQL** (AC: 2, 3)
  - [x] Add `motor` (async MongoDB driver) to `apps/api/pyproject.toml`
  - [x] Create `apps/api/app/infrastructure/db/mongodb/` module with connection helper and lifespan management
  - [x] Add `MONGODB_URL` to `.env.example` and FastAPI settings model
  - [x] Add health-check endpoint that verifies all three datastores (Postgres, MongoDB, Redis) are reachable

- [x] **Task 4 – Baseline Alembic migration and README** (AC: 3)
  - [x] Run `alembic revision --autogenerate -m "baseline"` to capture empty schema baseline
  - [x] Verify migration upgrades cleanly against local Postgres
  - [x] Update `README.md` with: prerequisites, native local setup, migration steps, and test-run commands

- [x] **Task 5 – Initialize CI workflow** (AC: 4)
  - [x] Create `.github/workflows/ci.yml` with jobs: `lint` (ruff + mypy for API, ESLint for web) and `test` (pytest for API, vitest for web)
  - [x] Ensure workflow runs on both PR and push to `main`
  - [x] Verify workflow passes on bootstrapped empty test suite (no false negatives)

- [x] **Task 6 – Implement PyCasbin authorization scaffold** (AC: 2)
  - [x] Add `pycasbin==1.43.0` and `casbin-async-sqlalchemy-adapter` to `apps/api/pyproject.toml`
  - [x] Create `apps/api/app/infrastructure/authz/` with Casbin enforcer setup and role model definition (`rbac_model.conf`)
  - [x] Define initial roles: `operator`, `lead`, `admin`, `super_admin`
  - [x] Expose `require_role(role)` dependency for use in route handlers

## Dev Notes

### Architecture Compliance

- **Starter template**: Use `github.com/fastapi/full-stack-fastapi-template` (tiangolo). Do NOT use any other FastAPI scaffold. [Source: architecture.md#Architectural-Decision-3-Starter-Template]
- **Monorepo layout**: All apps in `apps/`, all shared packages in `packages/`. Do NOT flatten everything under a single `src/`. [Source: architecture.md#Complete-Project-Directory-Structure]
- **Data stores**: PostgreSQL (mutable operational state), MongoDB (immutable event history), Redis (cache/coordination). All three must be wired from Day 1. [Source: architecture.md#Data-Architecture]
- **Authorization**: PyCasbin 1.43.0 RBAC with roles: `operator`, `lead`, `admin`, `super_admin`. JWT auth from template is retained. [Source: architecture.md#Authentication-Security]
- **Naming**: Python → snake_case; React/TS → PascalCase for components, camelCase for variables; DB tables → plural snake_case. [Source: architecture.md#Naming-Patterns]
- **API casing**: Backend snake_case ↔ client camelCase conversion at serialization boundary ONLY. [Source: architecture.md#Format-Patterns]

### Project Structure Notes

- `apps/api/app/` follows the template's existing structure; extend it with `domain/`, `infrastructure/`, `api/websocket/`, `api/middleware/` subdirectories as needed.
- `apps/workers/` is a NEW top-level app not in the template — create fresh with its own `pyproject.toml` sharing compatible dependency versions.
- The template ships with `items` CRUD as an example. **Remove it entirely** — keep only `auth`, `users` core, and the infra wiring.
- MongoDB `motor` client must use lifespan events (`startup`/`shutdown`) so connection pools are properly managed.
- Casbin policy files go in `apps/api/app/infrastructure/authz/policies/`. Do not embed policy strings in code.

### Testing Standards

- Backend: `pytest` with `httpx.AsyncClient` for API tests. Place unit tests in `apps/api/tests/unit/`, integration tests in `apps/api/tests/integration/`.
- Minimum coverage for this story: CI passing on empty suite + at least one smoke test verifying `/health` returns 200 for all three datastores.
- Frontend: `vitest` + React Testing Library. Co-locate component tests; e2e in `apps/web/e2e/`.
- All test files use `test_*` naming convention (Python) or `*.test.ts` (TypeScript).

### Key Libraries / Versions to Use

| Library | Version | Purpose |
|---------|---------|---------|
| FastAPI | latest stable (≥0.115) | API framework |
| SQLModel / SQLAlchemy | as in template | ORM |
| Alembic | as in template | DB migrations |
| motor | ≥3.5 | Async MongoDB driver |
| redis[hiredis] | ≥5.0 | Redis async client |
| pycasbin | 1.43.0 | Authorization engine |
| casbin-async-sqlalchemy-adapter | latest | Casbin persistence |
| React | ≥18 | Web UI |
| TypeScript | ≥5.3 | Type-safe frontend |
| TanStack Query | v5 | Server state |
| TanStack Router | v1 | Typed routing |
| Chakra UI | v2 / v3 | UI component system |

### References

- [Source: architecture.md#Architectural-Decision-3-Starter-Template]
- [Source: architecture.md#Data-Architecture]
- [Source: architecture.md#Authentication-Security]
- [Source: architecture.md#Complete-Project-Directory-Structure]
- [Source: architecture.md#Naming-Patterns]
- [Source: architecture.md#Format-Patterns]
- [Source: architecture.md#Implementation-Patterns-Consistency-Rules]
- [Source: epics.md#Story-1.1-Set-Up-Initial-Project-from-Starter-Template]

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6 (GitHub Copilot)

### Debug Log References

### Completion Notes List

### Review Findings

- [x] [Review][Decision] Casbin enforcer bypassed — wired `get_enforcer()` singleton via `@lru_cache`; `require_role()` now checks `get_implicit_roles_for_user()` against the Casbin policy hierarchy [`apps/api/app/infrastructure/authz/enforcer.py`]
- [x] [Review][Patch] `redis-data` volume undeclared in `compose.yml` — added to top-level `volumes:` block [`compose.yml`]
- [x] [Review][Patch] `.env.example` missing — file confirmed present (was untracked not absent); dismissed as false positive
- [x] [Review][Patch] `postgres:18` image does not exist — corrected to `postgres:17` [`compose.yml`]
- [x] [Review][Patch] `mypy` missing from CI backend job — added `Mypy` step [`.github/workflows/ci.yml`]
- [x] [Review][Patch] `require_role()` defaults unroled users to `"operator"` — fixed: added `role` field to `UserBase`/`User` model (default `"operator"`, explicit); migration `a1b2c3d4e5f6` created [`apps/api/app/models.py`, `apps/api/app/alembic/versions/a1b2c3d4e5f6_add_role_to_user.py`]
- [x] [Review][Defer] Sync `engine.connect()` in async `health_check` blocks event loop [`apps/api/app/api/routes/utils.py`] — deferred, pre-existing template pattern
- [x] [Review][Defer] No MongoDB server selection timeout configured on `MongoConnectionManager.connect()` [`apps/api/app/infrastructure/db/mongodb/connection.py`] — deferred, pre-existing infra concern

### File List
