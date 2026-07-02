# Campaigns Lifecycle Workspace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the synthetic campaigns workspace with real lifecycle routes for draft, ready, running, paused, and completed campaigns.

**Architecture:** Keep the existing campaigns API as the source of truth, but present the workspace as a status-driven route set. The top-level `/campaigns` route will summarize lifecycle counts and route users into the most relevant operational state, while each lifecycle page filters the same campaign list into a single status-focused view. The existing intake wizard becomes the draft builder so creation still exists, but no longer dominates the page.

**Tech Stack:** TanStack Router, React, TypeScript, shadcn/ui, existing `signalloopRequest` API helper, Playwright.

---

### Task 1: Add lifecycle route structure and shared campaign utilities

**Files:**
- Create: `apps/web/src/features/campaigns/campaign-types.ts`
- Create: `apps/web/src/features/campaigns/CampaignLifecycleWorkspacePage.tsx`
- Modify: `apps/web/src/routes/_layout/campaigns.tsx`
- Create: `apps/web/src/routes/_layout/campaigns.draft.tsx`
- Create: `apps/web/src/routes/_layout/campaigns.ready.tsx`
- Create: `apps/web/src/routes/_layout/campaigns.running.tsx`
- Create: `apps/web/src/routes/_layout/campaigns.paused.tsx`
- Create: `apps/web/src/routes/_layout/campaigns.completed.tsx`

- [ ] **Step 1: Write the failing route test**

```ts
test("campaign lifecycle routes render and link from the workspace", async ({ page }) => {
  await page.goto("/campaigns")
  await expect(page.getByRole("heading", { name: "Campaign lifecycle" })).toBeVisible()
  await page.getByRole("link", { name: "Draft" }).click()
  await expect(page).toHaveURL("/campaigns/draft")
})
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm test -- campaigns.spec.ts -g "campaign lifecycle routes"` from `apps/web`
Expected: fail because the route does not exist yet.

- [ ] **Step 3: Implement the route scaffold and lifecycle filters**

```tsx
type CampaignStatusFilter = "draft" | "ready" | "active" | "paused" | "completed"

const routeLabels: Record<CampaignStatusFilter, string> = {
  draft: "Draft",
  ready: "Ready",
  active: "Running",
  paused: "Paused",
  completed: "Completed",
}
```

- [ ] **Step 4: Run the route test again**

Run: `npm test -- campaigns.spec.ts -g "campaign lifecycle routes"` from `apps/web`
Expected: pass.

### Task 2: Reframe the campaigns pages around operational lifecycle content

**Files:**
- Modify: `apps/web/src/features/campaigns/CampaignsWorkspacePage.tsx`
- Modify: `apps/web/src/features/campaigns/CampaignIntakeWizardPage.tsx`

- [ ] **Step 1: Write the failing content test**

```ts
test("draft campaigns page keeps the builder secondary to the lifecycle list", async ({ page }) => {
  await page.goto("/campaigns/draft")
  await expect(page.getByRole("heading", { name: "Draft campaigns" })).toBeVisible()
  await expect(page.getByRole("heading", { name: "Campaign draft builder" })).toBeVisible()
})
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm test -- campaigns.spec.ts -g "builder secondary"` from `apps/web`
Expected: fail because the page still uses the old list-plus-wizard layout.

- [ ] **Step 3: Replace the synthetic dashboard with a lifecycle workspace**

```tsx
const statusCopy = {
  draft: "Assembly in progress",
  ready: "Prepared for launch",
  active: "Currently running",
  paused: "Temporarily paused",
  completed: "Finished and available for review",
}
```

- [ ] **Step 4: Run the content test again**

Run: `npm test -- campaigns.spec.ts -g "builder secondary"` from `apps/web`
Expected: pass.

### Task 3: Update Playwright coverage and verify the frontend build

**Files:**
- Modify: `apps/web/tests/campaigns.spec.ts`

- [ ] **Step 1: Add route- and lifecycle-specific coverage**

```ts
test("campaign lifecycle routes are status-focused", async ({ page }) => {
  await page.goto("/campaigns/running")
  await expect(page.getByRole("heading", { name: "Running campaigns" })).toBeVisible()
  await expect(page.getByRole("link", { name: "Paused" })).toBeVisible()
})
```

- [ ] **Step 2: Run the targeted Playwright file**

Run: `npm test -- campaigns.spec.ts` from `apps/web`
Expected: all campaign tests pass.

- [ ] **Step 3: Run the frontend build**

Run: `npm run build` from `apps/web`
Expected: successful build with no TypeScript or route errors.

- [ ] **Step 4: Commit the campaigns lifecycle slice**

```bash
git add apps/web/src/features/campaigns apps/web/src/routes/_layout/campaigns*.tsx apps/web/tests/campaigns.spec.ts docs/superpowers/plans/2026-06-23-campaigns-lifecycle-workspace.md
git commit -m "feat: restructure campaigns around lifecycle routes"
```
