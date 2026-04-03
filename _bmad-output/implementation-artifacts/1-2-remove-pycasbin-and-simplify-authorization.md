# Story 1.2: Remove PyCasbin and Simplify Authorization

Status: ready-for-dev

## Story

As a platform engineer,
I want to replace PyCasbin with a simple role-check middleware,
so that authorization is straightforward and doesn't require a policy engine for 2-3 admin users.

## Acceptance Criteria

1. **Given** casbin is in pyproject.toml **When** it is removed **Then** pip install completes without casbin packages
2. **Given** apps/api/app/infrastructure/authz/ directory exists with enforcer, rbac_model.conf, bootstrap.csv **When** the directory is deleted **Then** no imports reference casbin/authz modules
3. **Given** routes use require_role() dependency **When** a simple role check middleware replaces it **Then** admin users get 200 and non-admin users get 403
4. **Given** policy management routes exist **When** they are removed **Then** no /api/v1/policies endpoints exist

## Tasks / Subtasks

- [ ] Task 1: Remove casbin and casbin-async-sqlalchemy-adapter from pyproject.toml (AC: 1)
- [ ] Task 2: Delete apps/api/app/infrastructure/authz/ directory (AC: 2)
- [ ] Task 3: Create simple require_admin dependency: check user.role == "admin" or raise 403 (AC: 3)
- [ ] Task 4: Update all route files to use new require_admin instead of require_role (AC: 3)
- [ ] Task 5: Remove policy-related routes if they exist (AC: 4)
- [ ] Task 6: Search for remaining casbin imports and remove (AC: 2)
- [ ] Task 7: Run pytest (AC: 1)

## Dev Notes

- MVP has only admin users — no complex RBAC needed
- Simple FastAPI Depends(require_admin) is sufficient
### References
- [Source: architecture.md#Security-Baseline — simple role check, JWT from template retained]
- [Source: prd.md#FR11 — RBAC simplified to admin-only]

## Dev Agent Record
### Agent Model Used
### Debug Log References
### Completion Notes List
### File List
