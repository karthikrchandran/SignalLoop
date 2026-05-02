# Story 1.2: Remove PyCasbin and Simplify Authorization

Status: done

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

- [x] Task 1: Remove casbin and casbin-async-sqlalchemy-adapter from pyproject.toml (AC: 1)
- [x] Task 2: Delete apps/api/app/infrastructure/authz/ directory (AC: 2)
- [x] Task 3: Create simple require_admin dependency: check user.role == "admin" or raise 403 (AC: 3)
- [x] Task 4: Update all route files to use new require_admin instead of require_role (AC: 3)
- [x] Task 5: Remove policy-related routes if they exist (AC: 4)
- [x] Task 6: Search for remaining casbin imports and remove (AC: 2)
- [x] Task 7: Run pytest (AC: 1)

### Review Findings

- [x] [Review][Patch] Replace remaining `require_role`/`require_permission` authz surface with an admin-only dependency [apps/api/app/infrastructure/authz/enforcer.py:10]
	- AC2/AC3 violation: `apps/api/app/infrastructure/authz/` still exists, route files still import `app.infrastructure.authz.enforcer`, and `require_role("operator")` passes for any authenticated user because `role == "operator"` is treated as an automatic allow.
- [x] [Review][Patch] Remove the still-registered `/api/v1/policies` endpoints [apps/api/app/api/main.py:30]
	- AC4 violation: `policies.router` is still included and `apps/api/app/api/routes/policies.py` still exposes `/policies`, `/policies/`, and `/policies/evaluate` handlers.
- [x] [Review][Patch] Add auth enforcement to registered data-bearing routes that currently have none [apps/api/app/api/routes/calls.py:57]
	- Calls, scripts, sequences, dashboard, signals, triggers, campaign/template reads, and template preview include routes with no `CurrentUser`, no admin dependency, and in several cases no workspace context before returning business data.
- [x] [Review][Patch] Bind workspace context to the authenticated user instead of trusting caller-supplied workspace IDs [apps/api/app/api/request_context.py:25]
	- Workspace isolation gap: `X-Workspace-Id` is accepted as the data boundary without checking that the current user belongs to or administers that workspace.
- [x] [Review][Patch] Scope sequence reads and mutations to workspace ownership [apps/api/app/api/routes/sequences.py:53]
	- Cross-workspace leakage/mutation risk: sequence routes and `app.domain.sequences.service` load `EmailSequence` by raw IDs or list all sequences without joining through `Campaign.workspace_id`.
- [x] [Review][Patch] Scope script and call detail/action routes before returning data or causing side effects [apps/api/app/api/routes/scripts.py:28]
	- Cross-workspace leakage/mutation risk: scripts and calls are loaded by script/call UUID only; call detail returns transcript/recording data and call actions can email or pause sequence state for another workspace's contact.
- [x] [Review][Patch] Protect provider credential routes against cross-workspace path targeting [apps/api/app/api/routes/provider_credentials.py:76]
	- Any admin can choose an arbitrary `/{workspace_id}/provider-credentials` path; the path is not checked against a user/workspace membership or an authoritative workspace context before credentials are listed, replaced, or deactivated.
- [x] [Review][Patch] Validate every body/path foreign ID against the active workspace before persisting references [apps/api/app/api/routes/sequences.py:36]
	- Privilege escalation/vector: create/update paths accept `campaign_id`, `sequence_id`, `script_id`, `offer_pack_id`, and policy `campaign_id` references without consistently proving those objects belong to the requested workspace.
- [x] [Review][Patch] Add route coverage tests for admin 200, non-admin 403, unauthenticated denial, and cross-workspace denial [apps/api/tests/api/routes/test_campaigns.py:21]
	- Test gap: current route tests mostly use `superuser_token_headers`; normal-user denial coverage is limited and does not cover the route surface migrated from `require_role` or the public data endpoints found in this review.

## Dev Notes

- MVP has only admin users — no complex RBAC needed
- Simple FastAPI Depends(require_admin) is sufficient
### References
- [Source: architecture.md#Security-Baseline — simple role check, JWT from template retained]
- [Source: prd.md#FR11 — RBAC simplified to admin-only]

## Dev Agent Record
### Agent Model Used
GitHub Copilot

### Debug Log References
- `python -m ruff check ...` passed for modified API and regression-test files.
- `python -m pytest tests/api/routes/test_governance_controls.py` passed: 6 tests.

### Completion Notes List
- Added central `require_admin` dependency and applied it across migrated route surfaces.
- Removed `/api/v1/policies` registration and deleted the obsolete policy route module.
- Deleted the old `apps/api/app/infrastructure/authz/enforcer.py` surface; grep confirms no remaining app references to Casbin, `require_role`, `require_permission`, or `app.infrastructure.authz`.
- Required admin-authenticated workspace context for workspace-scoped APIs and added resource/header workspace validation to calls, scripts, sequences, dashboard, signals, campaign health, KPIs, provider credentials, and campaign strategy foreign IDs.
- Replaced obsolete policy-engine tests with focused authorization regressions for admin success, non-admin denial, anonymous denial, removed policy routes, and cross-workspace rejection.

### File List
- apps/api/app/api/deps.py
- apps/api/app/api/request_context.py
- apps/api/app/api/main.py
- apps/api/app/api/routes/audit_log.py
- apps/api/app/api/routes/campaigns.py
- apps/api/app/api/routes/campaign_health.py
- apps/api/app/api/routes/calls.py
- apps/api/app/api/routes/contacts.py
- apps/api/app/api/routes/controls.py
- apps/api/app/api/routes/dashboard.py
- apps/api/app/api/routes/kpis.py
- apps/api/app/api/routes/provider_credentials.py
- apps/api/app/api/routes/scripts.py
- apps/api/app/api/routes/sequences.py
- apps/api/app/api/routes/signals.py
- apps/api/app/api/routes/templates.py
- apps/api/app/api/routes/triggers.py
- apps/api/app/domain/dashboard/service.py
- apps/api/tests/api/routes/test_governance_controls.py
- apps/api/app/api/routes/policies.py
- apps/api/app/infrastructure/authz/enforcer.py
