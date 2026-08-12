# Frontend Test Stabilization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align the browser-test baseline and generated router artifact with the current Revenue OS launcher while preserving the already-green contact and current admin authorization behavior.

**Architecture:** The root route remains the Revenue OS workspace launcher. Browser coverage verifies the launcher’s durable user-facing content and its two internal navigation paths instead of the removed campaign-control dashboard. The generated TanStack route table is synchronized with its checked-in route modules; no route implementation or backend contract changes are introduced.

**Tech Stack:** React 19, TanStack Router, Playwright, Vite, TypeScript, Biome.

---

## File structure

- Modify: `apps/web/tests/dashboard-shell.spec.ts` — browser assertions for the Revenue OS launcher.
- Modify: `apps/web/src/routeTree.gen.ts` — generated route table synchronized with the existing route modules.
- Create: `docs/superpowers/specs/2026-08-12-frontend-test-stabilization-design.md` — approved scope record (already committed).
- Create: `docs/superpowers/plans/2026-08-12-frontend-test-stabilization.md` — this plan.

### Task 1: Replace the stale root-dashboard browser contract

**Files:**

- Modify: `apps/web/tests/dashboard-shell.spec.ts`
- Test: `apps/web/tests/dashboard-shell.spec.ts`

- [ ] **Step 1: Confirm the current assertions fail against the current root route**

Run:

```powershell
& 'C:\Users\K.Ramachandran\eMailVoice\node_modules\.bin\playwright.cmd' test tests/dashboard-shell.spec.ts --project=chromium --no-deps
```

Expected: FAIL because `Campaign control at a glance` and `Open campaigns` are not rendered by `/`.

- [ ] **Step 2: Replace the legacy assertions with the Revenue OS launcher contract**

Replace the two test bodies in `apps/web/tests/dashboard-shell.spec.ts` with the following tests, retaining the existing unauthenticated storage state and `/api/v1/users/me` route stub:

```ts
test("renders the Revenue OS launcher in the application shell", async ({ page }) => {
  await page.goto("/")

  await expect(page.locator("html")).toHaveClass(/light/)
  await expect(page.getByRole("heading", { name: "Revenue OS" })).toBeVisible()
  await expect(page.getByRole("heading", { name: "Your workspaces" })).toBeVisible()
  await expect(page.getByText("One customer record. One operating rhythm.")).toBeVisible()
  await expect(page.getByRole("link", { name: /EngageHub/ })).toBeVisible()
  await expect(page.getByRole("link", { name: /Platform administration/ })).toBeVisible()
  await expect(page.getByRole("heading", { name: "Agent workforce" })).toBeVisible()
})

test("Revenue OS workspace links navigate to internal workspaces", async ({ page }) => {
  await page.route("**/api/v1/campaigns/", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        data: [{ id: "camp-1", name: "Q2 Outreach", status: "draft" }],
        count: 1,
      }),
    })
  })

  await page.goto("/")
  await page.getByRole("link", { name: /Open EngageHub/ }).click()
  await expect(page).toHaveURL(/\/campaigns/)
  await expect(page.getByRole("heading", { name: "Campaigns" })).toBeVisible()

  await page.goto("/")
  await page.getByRole("link", { name: /Open administration/ }).click()
  await expect(page).toHaveURL(/\/admin/)
})
```

- [ ] **Step 3: Run the focused browser test**

Run:

```powershell
& 'C:\Users\K.Ramachandran\eMailVoice\node_modules\.bin\playwright.cmd' test tests/dashboard-shell.spec.ts --project=chromium --no-deps
```

Expected: 2 passed.

- [ ] **Step 4: Commit the test update**

```powershell
git add apps/web/tests/dashboard-shell.spec.ts
git commit -m "test: align root browser coverage with Revenue OS"
```

### Task 2: Synchronize the generated router table

**Files:**

- Modify: `apps/web/src/routeTree.gen.ts`
- Test: `apps/web` Vite router generation

- [ ] **Step 1: Establish the artifact drift**

Before accepting the generated file, start Vite from the clean branch and inspect the tracked route table:

```powershell
npm run dev
git diff -- apps/web/src/routeTree.gen.ts
```

Expected: Vite regenerates entries for already-tracked `/home`, `/platform/*`, and `/admin/*` route modules. Stop the server after observing the diff.

- [ ] **Step 2: Retain only the generated route synchronization**

Keep the generated imports, route definitions, type maps, module declarations, and child-route registrations produced from the existing files. Do not edit any route module or alter paths manually.

- [ ] **Step 3: Verify regeneration is clean**

Run:

```powershell
npm run build
git diff --exit-code -- apps/web/src/routeTree.gen.ts
```

Expected: build succeeds and the second command exits 0, proving a normal build no longer dirties the generated route table.

- [ ] **Step 4: Commit the generated artifact**

```powershell
git add apps/web/src/routeTree.gen.ts
git commit -m "chore: sync generated route tree"
```

### Task 3: Run focused regression and isolated admin verification

**Files:**

- Test: `apps/web/tests/dashboard-shell.spec.ts`
- Test: `apps/web/tests/contacts-management.spec.ts`
- Test: `apps/web/tests/admin.spec.ts`

- [ ] **Step 1: Run browser-mocked regression coverage**

Run:

```powershell
& 'C:\Users\K.Ramachandran\eMailVoice\node_modules\.bin\playwright.cmd' test tests/dashboard-shell.spec.ts tests/contacts-management.spec.ts --project=chromium --no-deps
```

Expected: 4 passed. This confirms the refreshed launcher tests and the previously passing Lead Groups detail test without depending on the shared API listener.

- [ ] **Step 2: Start an API process sourced from this worktree on port 8002**

Run from the repository root:

```powershell
$python = 'C:\Users\K.Ramachandran\eMailVoice\.venv\Scripts\python.exe'
$apiDir = 'C:\Users\K.Ramachandran\eMailVoice\.worktrees\frontend-test-stabilization\apps\api'
$apiProcess = Start-Process -FilePath $python -ArgumentList '-m uvicorn app.main:app --host 127.0.0.1 --port 8002' -WorkingDirectory $apiDir -WindowStyle Hidden -PassThru
Invoke-WebRequest 'http://127.0.0.1:8002/api/v1/openapi.json' -UseBasicParsing
```

Expected: OpenAPI responds 200. Confirm the listener command line references `frontend-test-stabilization` before running tests.

- [ ] **Step 3: Run the existing admin integration coverage against port 8002**

Run from `apps/web`:

```powershell
$env:VITE_API_URL = 'http://127.0.0.1:8002'
& 'C:\Users\K.Ramachandran\eMailVoice\node_modules\.bin\playwright.cmd' test tests/admin.spec.ts --project=chromium
```

Expected: existing admin CRUD plus non-superuser redirect coverage pass without using the service active on port 8001.

- [ ] **Step 4: Stop only the process launched in Step 2 and report the separate result**

```powershell
$listener = Get-NetTCPConnection -State Listen -LocalPort 8002
$process = Get-CimInstance Win32_Process -Filter "ProcessId=$($listener.OwningProcess)"
$process.CommandLine
Stop-Process -Id $listener.OwningProcess
```

Expected: the inspected command line names `frontend-test-stabilization`; no process on port 8001 is stopped.

### Task 4: Final focused quality gate

**Files:**

- Verify: `apps/web/tests/dashboard-shell.spec.ts`
- Verify: `apps/web/src/routeTree.gen.ts`

- [ ] **Step 1: Format-check changed frontend sources**

Run:

```powershell
npx @biomejs/biome check apps/web/tests/dashboard-shell.spec.ts apps/web/src/routeTree.gen.ts
```

Expected: exit 0 with no formatting or lint diagnostics.

- [ ] **Step 2: Confirm only intended tracked files are present**

Run:

```powershell
git status --short
git log --oneline -3
```

Expected: no Playwright report, `test-results`, or `node_modules` changes are staged; the stabilization commits and documentation are visible.

