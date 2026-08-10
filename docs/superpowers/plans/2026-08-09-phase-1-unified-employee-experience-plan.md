# Phase 1 Unified Employee Experience Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give every entitled employee one role-based home with CommitArc access and RevenueOS Essentials, while showing full RevenueOS and SignalLoop only to explicitly assigned users.

**Architecture:** The SignalLoop API exposes a single suite-context document built from local tenant entitlements and role bundles. The web shell derives product switcher and navigation from server-returned capabilities, not hidden UI assumptions. CommitArc receives a tenant-scoped RevenueOS Essentials summary through the native signed API boundary and keeps detailed CRM work inside CommitArc.

**Tech Stack:** FastAPI, SQLModel, React, TanStack Query/Router, Next.js server components, Zod, pytest, Vitest, Playwright.

---

### Task 1: Define the employee suite-context API

**Files:**
- Create: `apps/api/app/domain/suite_context/schemas.py`
- Create: `apps/api/app/domain/suite_context/service.py`
- Create: `apps/api/app/api/routes/suite_context.py`
- Modify: `apps/api/app/api/main.py`
- Test: `apps/api/tests/api/routes/test_suite_context.py`

- [ ] **Step 1: Write failing bundle tests**

```python
def test_employee_gets_commit_arc_and_revenue_essentials_but_not_signalloop(client, employee_headers):
    data = client.get("/api/v1/me/suite-context", headers=employee_headers).json()
    assert data["products"]["commitarc"]["visible"] is True
    assert data["products"]["revenueos"]["mode"] == "ESSENTIALS"
    assert data["products"]["signalloop"]["visible"] is False
```

Add manager, campaign-operator, revenue-operator, tenant-admin, suspended-member, and disabled-product cases.

- [ ] **Step 2: Run RED, implement, and run GREEN**

Return tenant identity/branding summary, active role bundles, capability strings, product visibility/mode, default route, and cross-product URLs. Never return platform roles, provider credentials, or another tenant's identifiers.

```powershell
uv run --project apps/api pytest apps/api/tests/api/routes/test_suite_context.py -q
```

- [ ] **Step 3: Commit**

```powershell
git add apps/api/app/domain/suite_context apps/api/app/api/routes/suite_context.py apps/api/app/api/main.py apps/api/tests/api/routes/test_suite_context.py
git commit -m "feat: expose employee suite context"
```

### Task 2: Build RevenueOS Essentials as a useful employee differentiator

**Files:**
- Create: `apps/api/app/domain/revenue_essentials/service.py`
- Create: `apps/api/app/domain/revenue_essentials/schemas.py`
- Create: `apps/api/app/api/routes/revenue_essentials.py`
- Test: `apps/api/tests/domain/test_revenue_essentials_service.py`
- Test: `apps/api/tests/api/routes/test_revenue_essentials.py`

- [ ] **Step 1: Write failing outcome-oriented tests**

```python
def test_essentials_prioritizes_actionable_work_for_current_employee(service, employee_context):
    result = service.build(employee_context)
    assert [card.kind for card in result.cards] == ["FOLLOW_UP_DUE", "DEAL_RISK", "NEXT_BEST_ACTION"]
    assert all(card.owner_user_id == employee_context.user_id for card in result.cards)
```

Add tests for manager team roll-up, empty state, stale source warning, policy-blocked action, and tenant isolation.

- [ ] **Step 2: Run RED and implement the bounded response**

```python
class RevenueEssentialsResponse(BaseModel):
    generated_at: datetime
    source_freshness: list[SourceFreshness]
    cards: list[EssentialsCard]
    metrics: list[EssentialsMetric]
    blocked_actions: list[BlockedAction]
    permitted_questions: list[PermittedQuestion]
    personal_goals: list[GoalProgress]
    intervention_outcomes: list[InterventionOutcome]
```

Essentials contains prioritized follow-ups, commitment/deadline risks, deal-risk summaries, next-best actions with evidence/explanations, permitted AI questions over records the employee can already access, personal goals, intervention history/outcomes, and transparent source freshness. It does not expose team-wide data, intervention policy editing/approval, knowledge publishing, campaign authoring/execution, provider administration, agent prompts, or cross-tenant aggregates.

- [ ] **Step 3: Run GREEN and commit**

```powershell
uv run --project apps/api pytest apps/api/tests/domain/test_revenue_essentials_service.py apps/api/tests/api/routes/test_revenue_essentials.py -q
git add apps/api/app/domain/revenue_essentials apps/api/app/api/routes/revenue_essentials.py apps/api/tests/domain/test_revenue_essentials_service.py apps/api/tests/api/routes/test_revenue_essentials.py
git commit -m "feat: add revenue os essentials"
```

### Task 3: Build the unified SignalLoop suite home and product switcher

**Files:**
- Create: `apps/web/src/features/suite/SuiteHomePage.tsx`
- Create: `apps/web/src/features/suite/ProductSwitcher.tsx`
- Create: `apps/web/src/features/suite/useSuiteContext.ts`
- Create: `apps/web/src/routes/_layout/home.tsx`
- Delete: `apps/web/src/routes/_layout/index.tsx`
- Modify: `apps/web/src/routes/_layout.tsx`
- Modify: `apps/web/src/features/revenue-os/RevenueOsHomePage.tsx`
- Test: `apps/web/tests/suite-home.spec.ts`

- [ ] **Step 1: Write failing browser matrix**

```typescript
test("employee sees CommitArc and RevenueOS Essentials but no SignalLoop authoring", async ({ page }) => {
  await page.goto("/home")
  await expect(page.getByRole("link", { name: "CommitArc" })).toBeVisible()
  await expect(page.getByText("RevenueOS Essentials")).toBeVisible()
  await expect(page.getByRole("link", { name: "Campaigns" })).toBeHidden()
})
```

Add campaign-operator and tenant-admin variants.

- [ ] **Step 2: Run RED, implement capability-filtered navigation, and run GREEN**

Home sections are `What needs attention`, `My pipeline`, `Recommended next actions`, and `Products`. Disabled products are omitted, not merely CSS-hidden. Deep routes re-check capability and return a neutral unauthorized page.

```powershell
npm --workspace frontend run test -- suite-home.spec.ts
npm --workspace frontend run build
```

- [ ] **Step 3: Commit**

```powershell
git add apps/web/src/features/suite apps/web/src/routes/_layout/home.tsx apps/web/src/routes/_layout.tsx apps/web/src/features/revenue-os/RevenueOsHomePage.tsx apps/web/tests/suite-home.spec.ts
git add -u apps/web/src/routes/_layout/index.tsx
git commit -m "feat: add role based suite home"
```

### Task 4: Surface RevenueOS Essentials in CommitArc

**Files:**
- Create: `C:\My Workspace\eCRM\.worktrees\enterprise-tenancy\src\server\revenue-os\essentials.ts`
- Create: `C:\My Workspace\eCRM\.worktrees\enterprise-tenancy\src\components\revenue-essentials.tsx`
- Modify: `C:\My Workspace\eCRM\.worktrees\enterprise-tenancy\src\app\(app)\dashboard\page.tsx`
- Modify: `C:\My Workspace\eCRM\.worktrees\enterprise-tenancy\src\components\app-shell.tsx`
- Test: `C:\My Workspace\eCRM\.worktrees\enterprise-tenancy\src\server\revenue-os\essentials.test.ts`
- Test: `C:\My Workspace\eCRM\.worktrees\enterprise-tenancy\src\app\(app)\dashboard\page.test.tsx`

- [ ] **Step 1: Write failing tenant, failure, and role tests**

```typescript
it("requests essentials with the server-derived tenant key and immutable identity", async () => {
  await getRevenueEssentials({ organizationKey: "ara-global", issuer: "https://id.example.test", subject: "oidc-user-a" })
  expect(createWorkloadAssertion).toHaveBeenCalledWith(expect.objectContaining({ tenantKey: "ara-global", audience: "revenueos", capability: "revenueos.essentials.read" }))
})
```

Assert a SignalLoop outage renders a non-blocking freshness warning and leaves CommitArc usable.

- [ ] **Step 2: Implement the signed native request and compact dashboard cards**

`essentials.ts` imports `createWorkloadAssertion` from `src/server/integrations/workload-identity.ts`, signs the request body digest for audience `revenueos`, and sends issuer/subject only inside that tenant-bound server request. The browser never receives the integration credential. The server validates the response with Zod, sets bounded connect/read timeouts, and displays last-known freshness rather than inventing values. The app shell product switch opens the suite URL; OIDC supplies seamless re-entry.

```typescript
export async function getRevenueEssentials(input: {
  organizationKey: string
  issuer: string
  subject: string
}): Promise<RevenueEssentials>
```

- [ ] **Step 3: Run GREEN and commit in eCRM**

```powershell
npm test -- src/server/revenue-os/essentials.test.ts 'src/app/(app)/dashboard/page.test.tsx' src/components/app-shell.test.tsx
npm run typecheck
npm run build
git add src/server/revenue-os src/components/revenue-essentials.tsx 'src/app/(app)/dashboard/page.tsx' src/components/app-shell.tsx
git commit -m "feat: add revenue essentials to commit arc"
```

### Task 5: Employee experience acceptance gate

- [ ] Prove every role bundle's navigation and direct-route authorization in API and browser tests.
- [ ] Prove all CommitArc employees see useful Essentials content or an explicit empty/freshness state.
- [ ] Prove unassigned users cannot list, open, or mutate SignalLoop campaigns.
- [ ] Prove removing an entitlement changes API and UI behavior without redeploying either application.
