# Phase 1 Platform Control Plane Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give platform administrators a safe, auditable control plane for tenants, products, invitations, role bundles, messaging defaults, and support access while giving tenant administrators control of only their own tenant.

**Architecture:** SignalLoop stores suite-level tenant and entitlement state. It projects only the CommitArc membership fields CommitArc needs through a signed, idempotent API. Platform administration and tenant administration use separate routes and authorization guards; platform status never implies tenant data access.

**Tech Stack:** FastAPI, SQLModel, Alembic, PostgreSQL, React, TanStack Router/Query, Zod, pytest, Playwright, Next.js/Prisma projection endpoint.

---

## File map

Create a focused `app/domain/tenants` package for tenant lifecycle, entitlements, role bundles, invitations, and support grants; expose it through `app/api/routes/platform_admin.py` and `tenant_admin.py`. Create corresponding React routes under `_layout/platform` and `_layout/admin`. CommitArc receives membership projections through one authenticated route and never reads the SignalLoop database.

### Task 1: Persist tenants, entitlements, role bundles, and invitations

**Files:**
- Create: `apps/api/app/domain/tenants/models.py`
- Create: `apps/api/app/domain/tenants/schemas.py`
- Create: `apps/api/app/alembic/versions/p1_control_20260809_add_suite_control_plane.py`
- Modify: `apps/api/app/models.py`
- Test: `apps/api/tests/unit/test_tenant_control_models.py`

- [ ] **Step 1: Write failing invariant tests**

```python
def test_entitlement_unique_per_tenant_product(session, tenant):
    session.add(TenantEntitlement(tenant_id=tenant.id, product_code="commitarc", status="ACTIVE"))
    session.commit()
    session.add(TenantEntitlement(tenant_id=tenant.id, product_code="commitarc", status="ACTIVE"))
    with pytest.raises(IntegrityError):
        session.commit()

def test_invitation_stores_digest_not_raw_token(invitation):
    assert invitation.token_digest
    assert not hasattr(invitation, "token")
```

- [ ] **Step 2: Run RED**

```powershell
uv run --project apps/api pytest apps/api/tests/unit/test_tenant_control_models.py -q
```

- [ ] **Step 3: Add the exact model set**

```python
class ProductCode(StrEnum):
    COMMIT_ARC = "commitarc"
    REVENUE_OS = "revenueos"
    SIGNAL_LOOP = "signalloop"

class RoleBundle(StrEnum):
    EMPLOYEE = "EMPLOYEE"
    MANAGER = "MANAGER"
    ENGAGEMENT_OPERATOR = "ENGAGEMENT_OPERATOR"
    TENANT_OWNER = "TENANT_OWNER"
    REVENUE_OS_ADMIN = "REVENUE_OS_ADMIN"
    COMMIT_ARC_ADMIN = "COMMIT_ARC_ADMIN"
    ENGAGEMENT_ADMIN = "ENGAGEMENT_ADMIN"

class PlatformRole(StrEnum):
    PLATFORM_ADMIN = "PLATFORM_ADMIN"
    PLATFORM_SUPPORT = "PLATFORM_SUPPORT"
```

Persist `Tenant`, `TenantEntitlement`, `ProductInstallation`, `SuiteMembership`, `SuiteRoleAssignment`, `TenantInvitation`, `TenantDomain`, `SupportAccessGrant`, and `SuiteProjectionOutbox`. `Tenant` includes stable key, legal/display name, lifecycle, region, locale, time zone, currency, compliance-pack selection, and version. `ProductInstallation` maps each suite entitlement to its product-local organization/workspace identifier without exposing that identifier publicly. `SuiteProjectionOutbox` stores event ID, tenant, product installation, projection kind/version, payload digest/ciphertext-safe payload, status, attempt count, next attempt, acknowledgement receipt, and dead-letter reason with unique `(installation_id, projection_kind, projection_version)`. Add tenant-scoped unique constraints and `created_by`, `updated_by`, timestamps, version, and status fields. A support grant requires tenant, operator, requested capabilities, reason, ticket/reference, approved_by, emergency-policy reference when used, starts_at, expires_at, and revoked_at.

The migration declares `revision = "p1_control_20260809"` and `down_revision = "p1_session_20260809"`. Run `uv run alembic heads` from `apps/api` before and after migration rehearsal and require exactly one head.

- [ ] **Step 4: Run GREEN**

```powershell
uv run --project apps/api pytest apps/api/tests/unit/test_tenant_control_models.py -q
```

- [ ] **Step 5: Commit**

```powershell
git add apps/api/app/domain/tenants apps/api/app/models.py apps/api/app/alembic/versions/p1_control_20260809_add_suite_control_plane.py apps/api/tests/unit/test_tenant_control_models.py
git commit -m "feat: add suite tenant control models"
```

### Task 2: Implement capability resolution and remove global data bypass

**Files:**
- Create: `apps/api/app/domain/tenants/capabilities.py`
- Modify: `apps/api/app/domain/workspaces/service.py`
- Modify: `apps/api/app/api/deps.py`
- Test: `apps/api/tests/unit/test_suite_capabilities.py`

- [ ] **Step 1: Write failing permission-table tests**

```python
@pytest.mark.parametrize(
    ("bundle", "capability", "allowed"),
    [("EMPLOYEE", "revenueos.essentials.read", True),
     ("EMPLOYEE", "signalloop.campaign.manage", False),
     ("ENGAGEMENT_OPERATOR", "signalloop.campaign.manage", True),
     ("TENANT_OWNER", "tenant.members.manage", True)],
)
def test_role_bundle_capabilities(bundle, capability, allowed):
    assert has_capability(bundle, capability) is allowed
```

Add a separate test proving `PLATFORM_ADMIN` cannot call a tenant business-data dependency without an unexpired support grant.

- [ ] **Step 2: Run RED**

```powershell
uv run --project apps/api pytest apps/api/tests/unit/test_suite_capabilities.py apps/api/tests/unit/test_workspace_memberships.py -q
```

- [ ] **Step 3: Add the immutable capability registry**

`resolve_suite_context(user_id, tenant_id)` must require an active tenant, active membership, active product entitlement, and matching role capability. Remove `is_superuser` as a tenant-data shortcut; retain it only as a migration input mapped to `PLATFORM_ADMIN`.

```python
def resolve_suite_context(user_id: UUID, tenant_id: UUID) -> SuiteContext:
    return capability_registry.resolve_live(user_id=user_id, tenant_id=tenant_id)
```

- [ ] **Step 4: Run GREEN**

Run the same focused command and expect every case to pass.

- [ ] **Step 5: Commit**

```powershell
git add apps/api/app/domain/tenants/capabilities.py apps/api/app/domain/workspaces/service.py apps/api/app/api/deps.py apps/api/tests/unit/test_suite_capabilities.py apps/api/tests/unit/test_workspace_memberships.py
git commit -m "fix: separate platform and tenant authorization"
```

### Task 3: Add idempotent tenant, entitlement, invitation, and support APIs

**Files:**
- Create: `apps/api/app/domain/tenants/service.py`
- Create: `apps/api/app/api/routes/platform_admin.py`
- Create: `apps/api/app/api/routes/tenant_admin.py`
- Modify: `apps/api/app/api/main.py`
- Test: `apps/api/tests/api/routes/test_platform_admin.py`
- Test: `apps/api/tests/api/routes/test_tenant_admin.py`

- [ ] **Step 1: Write failing API tests**

```python
def test_platform_admin_creates_tenant_idempotently(client, platform_headers):
    payload = {"key": "ara-global", "display_name": "ARA Global", "idempotency_key": "ara-v1"}
    first = client.post("/api/v1/platform/tenants", json=payload, headers=platform_headers)
    second = client.post("/api/v1/platform/tenants", json=payload, headers=platform_headers)
    assert first.json()["id"] == second.json()["id"]

def test_tenant_admin_cannot_update_other_tenant(client, ara_admin_headers, ai_tenant):
    assert client.patch(f"/api/v1/admin/tenants/{ai_tenant.id}", json={"display_name": "x"}, headers=ara_admin_headers).status_code == 404
```

- [ ] **Step 2: Run RED**

```powershell
uv run --project apps/api pytest apps/api/tests/api/routes/test_platform_admin.py apps/api/tests/api/routes/test_tenant_admin.py -q
```

- [ ] **Step 3: Implement the administration routes**

The platform API manages tenant lifecycle, domains, all three product entitlements/editions, OIDC configuration references, region/locale/currency/compliance pack, provider/model allowlists, global safety ceilings, messaging defaults, invitations, usage/health summaries, suspension/offboarding, and support grants. The tenant API manages its own members, role bundles, invitations/reinvitations, account suspension/reactivation, application-session revocation, branding references, messaging overrides, and product settings. Password/MFA recovery produces an issuer recovery redirect and never reads or sets a credential. Every mutation accepts an idempotency key, optimistic `expected_version`, and records actor subject/local ID, tenant, product, capability, target, before/after versions, correlation/idempotency IDs, support context, outcome, and denial reason.

```python
@router.post("/tenants", response_model=TenantPublic)
def create_tenant(request: TenantCreate, actor: PlatformAdmin) -> TenantPublic:
    return tenant_service.create_idempotent(request=request, actor=actor)
```

- [ ] **Step 4: Run GREEN**

Run the same focused command and expect every case to pass.

- [ ] **Step 5: Commit**

```powershell
git add apps/api/app/domain/tenants/service.py apps/api/app/api/routes/platform_admin.py apps/api/app/api/routes/tenant_admin.py apps/api/app/api/main.py apps/api/tests/api/routes/test_platform_admin.py apps/api/tests/api/routes/test_tenant_admin.py
git commit -m "feat: add suite administration apis"
```

### Task 4: Propagate time-bounded support context through the data plane

**Files:**
- Create: `apps/api/app/domain/support_access/context.py`
- Create: `apps/api/app/domain/support_access/service.py`
- Modify: `apps/api/app/api/request_context.py`
- Modify: `apps/api/app/domain/audit/audit_events.py`
- Modify: `apps/api/app/domain/outreach/action_queue_service.py`
- Modify: `apps/api/app/domain/outreach/outbox_service.py`
- Modify: `apps/api/app/domain/shared_records/service.py`
- Modify: `apps/api/app/domain/chatbot/engine.py`
- Modify: `apps/workers/worker_app/policies/enforcement_gate.py`
- Modify: `apps/workers/worker_app/sequence_worker.py`
- Modify: `apps/workers/worker_app/call_worker.py`
- Test: `apps/api/tests/unit/test_support_access.py`
- Test: `apps/api/tests/api/routes/test_support_access.py`
- Test: `apps/workers/tests/unit/test_enforcement_gate.py`

- [ ] **Step 1: Write failing denial, expiry, and audit tests**

```python
def test_platform_admin_has_no_tenant_context_without_grant(client, platform_headers):
    assert client.get("/api/v1/contacts", headers=platform_headers).status_code == 404

def test_expired_support_grant_is_denied_and_audited(client, expired_support_headers):
    response = client.get("/api/v1/contacts", headers=expired_support_headers)
    assert response.status_code == 404
    assert latest_audit().denial_reason == "SUPPORT_GRANT_EXPIRED"
```

- [ ] **Step 2: Implement one support-context dependency**

Resolve the authenticated operator, signed grant identifier, tenant, requested capability, approval/emergency policy, and expiry before constructing tenant request context. Propagate `support_grant_id` through page, query, mutation, export, AI-tool, queue, and audit contexts. A revoked, expired, or mismatched grant returns uniform not-found behavior and cannot be refreshed from request data.

- [ ] **Step 3: Run GREEN**

```powershell
uv run --project apps/api pytest apps/api/tests/unit/test_support_access.py apps/api/tests/api/routes/test_support_access.py apps/api/tests/api/routes/test_audit_log.py -q
uv run --project apps/workers pytest apps/workers/tests/unit/test_enforcement_gate.py -q
```

- [ ] **Step 4: Commit**

```powershell
git add apps/api/app/domain/support_access apps/api/app/api/request_context.py apps/api/app/domain/audit/audit_events.py apps/api/app/domain/outreach/action_queue_service.py apps/api/app/domain/outreach/outbox_service.py apps/api/app/domain/shared_records/service.py apps/api/app/domain/chatbot/engine.py apps/workers/worker_app/policies/enforcement_gate.py apps/workers/worker_app/sequence_worker.py apps/workers/worker_app/call_worker.py apps/api/tests/unit/test_support_access.py apps/api/tests/api/routes/test_support_access.py apps/api/tests/api/routes/test_audit_log.py apps/workers/tests/unit/test_enforcement_gate.py
git commit -m "feat: enforce audited tenant support access"
```

### Task 5: Project CommitArc memberships safely

**Files:**
- Create: `apps/api/app/domain/tenants/commit_arc_projection.py`
- Create: `apps/api/app/domain/projections/dispatcher.py`
- Create: `apps/api/app/domain/projections/reconciliation.py`
- Create: `apps/workers/worker_app/projection_worker.py`
- Test: `apps/api/tests/unit/test_commit_arc_projection.py`
- Test: `apps/api/tests/unit/test_projection_dispatcher.py`
- Test: `apps/workers/tests/unit/test_projection_worker.py`
- Create: `C:\My Workspace\eCRM\.worktrees\enterprise-tenancy\src\app\api\platform\projections\memberships\route.ts`
- Create: `C:\My Workspace\eCRM\.worktrees\enterprise-tenancy\src\app\api\platform\projections\status\route.ts`
- Create: `C:\My Workspace\eCRM\.worktrees\enterprise-tenancy\src\server\organizations\membership-projection.ts`
- Test: `C:\My Workspace\eCRM\.worktrees\enterprise-tenancy\src\server\organizations\membership-projection.test.ts`
- Modify: `C:\My Workspace\eCRM\.worktrees\enterprise-tenancy\prisma\schema.prisma`
- Create: `C:\My Workspace\eCRM\.worktrees\enterprise-tenancy\prisma\migrations\20260809130500_add_suite_authorization_projection\migration.sql`
- Create: `C:\My Workspace\eCRM\.worktrees\enterprise-tenancy\src\server\auth\capabilities.ts`
- Modify: `C:\My Workspace\eCRM\.worktrees\enterprise-tenancy\src\server\organizations\context.ts`

- [ ] **Step 1: Write failing replay, stale-version, and cross-tenant tests**

```typescript
it("applies the same projection once and rejects an older version", async () => {
  expect(await applyMembershipProjection(projection(7))).toEqual({ applied: true, version: 7 })
  expect(await applyMembershipProjection(projection(7))).toEqual({ applied: false, version: 7 })
  await expect(applyMembershipProjection(projection(6))).rejects.toThrow("stale projection")
})
```

- [ ] **Step 2: Implement signed delivery**

SignalLoop signs a canonical JSON envelope containing event ID, tenant key, issuer, subject, email snapshot, CommitArc compatibility role, suite role bundles, three product entitlements, membership status, projection version, and issued-at. CommitArc validates signature, five-minute age, event uniqueness, tenant mapping, and monotonic version in one control-plane transaction. Add `OrganizationProductEntitlement`, `OrganizationRoleBundleAssignment`, and `SuiteProjectionReceipt` models; retain `OrganizationMembership.role` only as a compatibility field. `resolveOrganizationContext` derives live capabilities from these projected rows and rejects projection drift. It does not accept organization ID, product, role, or capability from browser headers.

`ProjectionDispatcher` claims persisted outbox rows, signs them, delivers membership/entitlement, installation/key, and branding projections, verifies the product receipt, and marks `ACKNOWLEDGED` in one state transition. It applies bounded exponential retry, moves exhausted deliveries to `DEAD_LETTER`, and never drops or mutates the projection payload. `ProjectionReconciler` compares central versions with CommitArc's signed status response and enqueues only missing/newer projections. The worker uses the same dispatcher; restart resumes persisted rows. Branding and installation services write their projection plus outbox event in the same database transaction.

- [ ] **Step 3: Run both focused suites**

```powershell
uv run --project apps/api pytest apps/api/tests/unit/test_commit_arc_projection.py apps/api/tests/unit/test_projection_dispatcher.py -q
uv run --project apps/workers pytest apps/workers/tests/unit/test_projection_worker.py -q
```

```powershell
npm test -- src/server/organizations/membership-projection.test.ts
```

- [ ] **Step 4: Commit separately**

SignalLoop:

```powershell
git add apps/api/app/domain/tenants/commit_arc_projection.py apps/api/app/domain/projections apps/workers/worker_app/projection_worker.py apps/api/tests/unit/test_commit_arc_projection.py apps/api/tests/unit/test_projection_dispatcher.py apps/workers/tests/unit/test_projection_worker.py
git commit -m "feat: deliver suite projections reliably"
```

CommitArc:

```powershell
git add prisma/schema.prisma prisma/migrations/20260809130500_add_suite_authorization_projection src/app/api/platform/projections/memberships/route.ts src/app/api/platform/projections/status/route.ts src/server/organizations/membership-projection.ts src/server/organizations/membership-projection.test.ts src/server/auth/capabilities.ts src/server/organizations/context.ts
git commit -m "feat: consume suite authorization projections"
```

### Task 6: Build separate Platform Admin and Tenant Admin shells

**Files:**
- Create: `apps/web/src/routes/_layout/platform.tsx`
- Create: `apps/web/src/routes/_layout/platform.tenants.tsx`
- Create: `apps/web/src/routes/_layout/platform.products.tsx`
- Create: `apps/web/src/routes/_layout/platform.identity.tsx`
- Create: `apps/web/src/routes/_layout/platform.messaging.tsx`
- Create: `apps/web/src/routes/_layout/platform.provider-policies.tsx`
- Create: `apps/web/src/routes/_layout/platform.usage-health.tsx`
- Create: `apps/web/src/routes/_layout/platform.support-access.tsx`
- Create: `apps/web/src/routes/_layout/platform.audit.tsx`
- Create: `apps/web/src/routes/_layout/admin.members.tsx`
- Create: `apps/web/src/routes/_layout/admin.products.tsx`
- Create: `apps/web/src/routes/_layout/admin.messaging.tsx`
- Create: `apps/web/src/routes/_layout/admin.security.tsx`
- Create: `apps/web/src/routes/_layout/admin.audit.tsx`
- Create: `apps/web/src/routes/_layout/admin.commit-arc.tsx`
- Create: `apps/web/src/routes/_layout/admin.revenue-os.tsx`
- Create: `apps/web/src/routes/_layout/admin.signal-loop.tsx`
- Create: `apps/web/src/features/admin/PlatformAdminLayout.tsx`
- Create: `apps/web/src/features/admin/TenantAdminLayout.tsx`
- Test: `apps/web/tests/platform-admin.spec.ts`
- Test: `apps/web/tests/tenant-admin.spec.ts`

- [ ] **Step 1: Write RED Playwright scenarios**

Assert separate navigation, ARA/AI tenant creation, all-three-product entitlement assignment, invitation and role assignment, support-grant expiry, and tenant-admin cross-tenant denial.

- [ ] **Step 2: Implement route guards and layouts**

Platform navigation is `Tenants`, `Products`, `Identity`, `Messaging defaults`, `Provider policies`, `Usage and health`, `Support access`, `Audit`. Tenant navigation is `Overview`, `People and Roles`, `Products`, `Branding`, `Security`, `Messaging`, `Tenant Audit`. The RevenueOS page contains AI Control Center, Knowledge Releases, Policies and Autonomy, Intervention Queue, Budgets and Limits, Outcomes, and RevenueOS Audit. The CommitArc page links to business settings, pipeline/catalog, proposals/numbering, delivery/production, finance/incentives, and CommitArc Audit. The SignalLoop page contains engagement overview, campaigns/sequences, channels/providers, consent/suppression, templates, messaging/voice agents, and SignalLoop Audit. Product-admin pages render only when the user has the corresponding product-admin capability.

- [ ] **Step 3: Generate routes and run GREEN**

```powershell
npm --workspace frontend run build
npm --workspace frontend run test -- platform-admin.spec.ts tenant-admin.spec.ts
```

- [ ] **Step 4: Commit**

```powershell
git add apps/web/src/routes apps/web/src/features/admin apps/web/tests/platform-admin.spec.ts apps/web/tests/tenant-admin.spec.ts apps/web/src/routeTree.gen.ts
git commit -m "feat: add suite administration workspaces"
```

Before staging `routeTree.gen.ts`, confirm its diff contains only routes created in this task; preserve any pre-existing unrelated generated diff.

### Task 7: Control-plane security gate

- [ ] Prove invitation tokens are one-time, hashed, expiring, revocable, and tenant-bound.
- [ ] Prove support grants are approved, reasoned, time-bounded, revocable, and audited on every use.
- [ ] Prove `PLATFORM_ADMIN`, `PLATFORM_SUPPORT`, `TENANT_OWNER`, and employee bundles cannot acquire each other's capabilities through request data.
- [ ] Run all SignalLoop API and web gates plus CommitArc projection tests.
