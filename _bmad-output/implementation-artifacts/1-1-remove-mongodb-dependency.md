# Story 1.1: Remove MongoDB Dependency

Status: ready-for-dev

## Story

As a platform engineer,
I want to remove all MongoDB (motor) dependencies from the codebase,
so that the application uses only PostgreSQL for all persistent storage, reducing complexity and hosting costs.

## Acceptance Criteria

1. **Given** motor is in pyproject.toml **When** the dependency is removed **Then** pip install completes without motor and the application starts without MongoDB
2. **Given** MongoDB infrastructure code exists in apps/api/app/infrastructure/db/mongodb/ **When** the directory and all files are deleted **Then** no imports reference mongodb modules
3. **Given** mongo_schema.py and mongo_audit.py exist **When** they are removed/rewritten **Then** audit events write to a new PostgreSQL audit_events table (JSONB payload column) via Alembic migration
4. **Given** compose.yml references a MongoDB service **When** it is removed **Then** docker compose up starts only PostgreSQL, Redis, API, and web
5. **Given** the MONGODB_URL environment variable exists in settings **When** it is removed **Then** the FastAPI settings model and .env.example no longer reference MongoDB

## Tasks / Subtasks

- [ ] Task 1: Remove motor from apps/api/pyproject.toml (AC: 1)
- [ ] Task 2: Delete apps/api/app/infrastructure/db/mongodb/ directory (AC: 2)
- [ ] Task 3: Delete apps/api/app/domain/events/mongo_schema.py (AC: 2,3)
- [ ] Task 4: Rewrite apps/api/app/domain/audit/mongo_audit.py to use PostgreSQL — create SQLModel AuditEvent with JSONB payload (AC: 3)
- [ ] Task 5: Create Alembic migration for audit_events table (AC: 3)
- [ ] Task 6: Remove MongoDB service from compose.yml and compose.override.yml (AC: 4)
- [ ] Task 7: Remove MONGODB_URL from settings and .env.example (AC: 5)
- [ ] Task 8: Search entire codebase for remaining MongoDB/motor imports and remove them (AC: 2)
- [ ] Task 9: Run pytest to verify nothing is broken (AC: 1)

## Dev Notes

- The audit_events table should have: id (UUID), event_type (str), actor_id (UUID nullable), resource_type (str), resource_id (str), payload (JSONB), created_at (datetime)
- Keep the audit logging interface (function signature) compatible so other code doesn't need changes
### References
- [Source: architecture.md#Data-Architecture — PostgreSQL is the only required datastore]
- [Source: prd.md#FR9-FR13 — simplified governance needs only PostgreSQL]

## Dev Agent Record
### Agent Model Used
### Debug Log References
### Completion Notes List
### File List
