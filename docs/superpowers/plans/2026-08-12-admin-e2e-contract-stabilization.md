# Admin E2E Contract Stabilization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make login and admin E2E coverage assert current Revenue OS behavior and execute stateful admin CRUD against an explicit, serial local API.

**Architecture:** Browser contracts stay at the UI boundary. A test helper asserts the new landing surface. Stateful admin tests wait for their real mutation response and receive a dedicated base URL/serial worker configuration, avoiding the shared 8001 service.

**Tech Stack:** Playwright, TypeScript, Vite, FastAPI.

---

### Task 1: Align stale login and admin assertions

**Files:**

- Modify: `apps/web/tests/utils/user.ts`
- Modify: `apps/web/tests/login.spec.ts`
- Modify: `apps/web/tests/admin.spec.ts`

- [ ] Replace each successful-login `Welcome back` assertion with `getByRole("heading", { name: "Revenue OS" })`.
- [ ] In admin entry and superuser assertions, retain `Users` but also require `Tenant administration`; for ordinary-user denial, assert redirect to `/` and the `Revenue OS` heading.
- [ ] Run focused login and mocked admin route assertions, verifying the old expected string is absent from the changed tests.

### Task 2: Make CRUD mutation failures observable and serial

**Files:**

- Modify: `apps/web/tests/admin.spec.ts`
- Modify: `apps/web/playwright.config.ts`

- [ ] Add an admin mutation helper that registers `page.waitForResponse` before clicking Save/Delete; it matches the expected method and `/api/v1/users` path, then asserts the response is successful.
- [ ] Use the helper for create, update, and delete flows before asserting toast/table state.
- [ ] Create a dedicated `admin-chromium` project with `workers: 1`, dependency on setup, and an explicit `PLAYWRIGHT_API_URL` override passed to the generated client/test config; standard Chromium remains unchanged.
- [ ] Verify focused admin coverage fails before the expectations/configuration change and passes against a temporary worktree API at an explicit port.

### Task 3: Focused verification and integration

**Files:**

- Verify: `apps/web/tests/login.spec.ts`
- Verify: `apps/web/tests/admin.spec.ts`
- Verify: `apps/web/tests/dashboard-shell.spec.ts`
- Verify: `apps/web/tests/contacts-management.spec.ts`

- [ ] Run login and admin project tests against a temporary worktree API on 8002, start it only after local environment variables are loaded ephemerally and confirm `/api/v1/openapi.json` returns 200.
- [ ] Run mocked dashboard/contact coverage with `--no-deps`.
- [ ] Run `npm run build`, focused Biome, `git diff --check`, and ensure status contains no generated test artifacts.
- [ ] Commit implementation with a focused test-stabilization message.

