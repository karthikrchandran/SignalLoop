# Frontend Test Stabilization Design

**Date:** 2026-08-12  
**Branch:** `codex/frontend-test-stabilization`  
**Status:** approved for planning

## Purpose

Stabilize the browser-test baseline against the current Revenue OS landing experience without reverting the product to the retired campaign-control dashboard. Keep the change isolated from the parallel Sales Agent work and from provider or tenant-control-plane contracts.

## Evidence and decisions

- The current `/` route renders `RevenueOsHomePage`; it no longer renders the legacy `Dashboard` component.
- `dashboard-shell.spec.ts` fails on the retired `Campaign control at a glance` and `Open campaigns` contracts. Its two tests are therefore stale, not evidence of a UI regression.
- `contacts-management.spec.ts`, including the Lead Groups detail path, passes independently against the current branch. No contact change is warranted.
- The current admin components already emit success feedback, and `/admin` redirects a non-authorized user instead of exposing the legacy page. Do not reimplement that behavior. Verify it only through the existing integration coverage using a worktree-local API process; do not point that test at another active worktree's service.
- Starting the web server regenerated `routeTree.gen.ts` to include already-tracked platform and tenant-admin routes. The generated route table must be committed in sync with its source files so a normal dev/build run does not leave a tracked modification.

## Design

### 1. Revenue OS home browser contract

Replace the legacy dashboard assertions with the stable launcher contract:

- an authorized admin sees `Revenue OS`, `Your workspaces`, and the agent-workforce section;
- the visible workspace cards include the internally routed EngageHub and Platform administration actions;
- the EngageHub action reaches `/campaigns` and the Platform administration action reaches `/admin`.

The test will assert user-visible labels and destination URLs only. It will not assert card counts, legacy dashboard copy, external Sales Ops links, or implementation-specific CSS beyond the existing light-theme shell check.

### 2. Generated router artifact

Keep the generated `apps/web/src/routeTree.gen.ts` aligned with the tracked route modules already present in the branch. This is a generated-artifact synchronization only: it neither changes route implementation nor adds a new product surface.

### 3. Verification boundary

Run the focused dashboard and contacts browser specs. Run the existing admin authorization and CRUD coverage only after starting an API process from this worktree on a non-conflicting port and directing the test setup to it. Treat failures outside these contracts as separate issues; do not modify the Sales Agent branch, providers, data schema, or control-plane behavior in this slice.

## Error handling and risk controls

- Keep request interception in the browse-only dashboard/contacts tests so they do not depend on a shared active service.
- Use a distinct local API port for admin integration verification, then stop only the process launched for this worktree.
- Preserve unrelated worktrees and do not add generated Playwright output or dependency links to Git.

## Acceptance criteria

1. The updated dashboard browser spec passes against the Revenue OS launcher and verifies both internal workspace destinations.
2. The Contact Lead Groups spec remains green without source changes.
3. `routeTree.gen.ts` is synchronized and no longer changes merely from starting the local web server.
4. The focused admin access and user-management coverage is run against a worktree-local API instance; its result is reported separately from browser-mocked coverage.
5. The focused build/lint checks appropriate to changed frontend files pass.

## Out of scope

- Sales Agent UI/API changes and any merge of that branch.
- CRM/provider connections, external Sales Ops links, or live production smoke tests.
- New authorization semantics, tenant schema changes, and repair of unrelated full-suite failures.
