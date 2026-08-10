# Phase 1 Tenant Branding and Administration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Provide configurable tenant branding and tenant-specific suite entry pages, including an ARA Global experience based on the old ARA visual and a neutral AI Consulting experience, without changing the generic CommitArc landing.

**Architecture:** SignalLoop owns public suite branding and entry resolution because it is the suite control plane. Branding records are versioned and assets are stored in PostgreSQL behind a storage interface for Phase 1, with strict size/MIME validation and content hashes. CommitArc consumes a minimal signed branding projection for in-app chrome while retaining its generic public login page.

**Tech Stack:** FastAPI, SQLModel, PostgreSQL byte storage, React, TanStack Router, Next.js, Prisma, Tailwind, pytest, Vitest, Playwright.

---

### Task 1: Persist versioned branding and safe assets

**Files:**
- Modify: `apps/api/pyproject.toml`
- Create: `apps/api/app/domain/branding/models.py`
- Create: `apps/api/app/domain/branding/service.py`
- Create: `apps/api/app/domain/branding/schemas.py`
- Create: `apps/api/app/domain/branding/storage.py`
- Create: `apps/api/app/alembic/versions/p1_branding_20260809_add_tenant_branding.py`
- Modify: `apps/api/app/models.py`
- Test: `apps/api/tests/domain/test_branding_service.py`

- [ ] **Step 1: Write failing validation tests**

```python
@pytest.mark.parametrize("mime", ["image/svg+xml", "text/html", "application/javascript"])
def test_rejects_active_content_assets(service, mime):
    with pytest.raises(BrandAssetValidationError):
        service.store_asset(tenant_id=TENANT_A, mime_type=mime, content=b"payload")

def test_rejects_asset_over_five_megabytes(service):
    with pytest.raises(BrandAssetValidationError):
        service.store_asset(TENANT_A, "image/png", b"x" * (5 * 1024 * 1024 + 1))

def test_rejects_fake_png_and_excessive_dimensions(service):
    with pytest.raises(BrandAssetValidationError):
        service.store_asset(TENANT_A, "image/png", b"not-a-png")
    with pytest.raises(BrandAssetValidationError):
        service.store_asset(TENANT_A, "image/png", decoded_png(width=5000, height=5000))
```

- [ ] **Step 2: Run RED and add models**

Persist immutable `TenantBrandingVersion` rows with tenant ID, version, lifecycle (`DRAFT`, `PREVIEWED`, `VALIDATED`, `PUBLISHED`, `SUPERSEDED`), display/product names, headline, supporting copy, enabled product-card copy, primary/secondary colors, support/privacy/legal links, email/document identity, logo/hero asset IDs, creator/validator/publisher, and timestamps. Persist `TenantBrandAsset` with tenant ID, kind (`LOGO` or `HERO`), `image/png|image/jpeg|image/webp`, bytes, byte count, SHA-256, creator, and timestamps. `BrandAssetStore` defines put/get; `PostgresBrandAssetStore` is the Phase 1 adapter. Add Pillow to decode, verify actual format, strip metadata by re-encoding, and reject images wider/taller than 4096 pixels or over 20 megapixels. Never allow SVG or arbitrary URLs. Superseded assets remain immutable; an audited cleanup job may remove only unreferenced abandoned-draft assets older than 30 days and never runs during rollback.

The migration declares `revision = "p1_branding_20260809"` and `down_revision = "acquisition_20260814"`; require one Alembic head before and after rehearsal.

- [ ] **Step 3: Run GREEN and commit**

```powershell
uv run --project apps/api pytest apps/api/tests/domain/test_branding_service.py -q
git add apps/api/pyproject.toml apps/api/app/domain/branding apps/api/app/models.py apps/api/app/alembic/versions/p1_branding_20260809_add_tenant_branding.py apps/api/tests/domain/test_branding_service.py
git commit -m "feat: add tenant branding storage"
```

### Task 2: Resolve public suite entry without leaking tenant configuration

**Files:**
- Create: `apps/api/app/api/routes/public_branding.py`
- Create: `apps/api/app/domain/branding/host_resolver.py`
- Modify: `apps/api/app/core/config.py`
- Create: `apps/api/tests/api/routes/test_public_branding.py`
- Create: `apps/api/tests/unit/test_tenant_host_resolver.py`
- Modify: `apps/api/app/api/main.py`

- [ ] **Step 1: Write failing host/slug resolution tests**

```python
def test_known_domain_returns_public_branding(client):
    client.app.dependency_overrides[verified_tenant_host] = lambda: "ara.example.test"
    response = client.get("/api/v1/public/entry")
    assert response.json()["tenant_key"] == "ara-global"
    assert "support_email" not in response.json()

def test_unknown_domain_discloses_nothing(client):
    client.app.dependency_overrides[verified_tenant_host] = lambda: "unknown.test"
    response = client.get("/api/v1/public/entry")
    assert response.status_code == 404
    assert response.json() == {"detail": "Workspace is not available"}
```

- [ ] **Step 2: Implement the allowlisted response**

`TrustedTenantHostResolver` accepts a canonical host only from `X-Verified-Tenant-Host` when the immediate peer belongs to configured `TRUSTED_PROXY_CIDRS`; production startup requires nonempty trusted proxies and `TRUSTED_ENTRY_ORIGINS`, and the deployment contract requires that the TLS terminator strip any client-supplied verified-host header before injecting its own SNI/allowlist-validated value. Direct production access to the API listener is blocked and an untrusted peer/header fails closed. It never accepts tenant identity from raw `Host`, query, form, cookie, or ordinary client header. A nonproduction-only dependency resolves `ara.localhost` and `ai-consulting.localhost` through the same `TenantDomain` rows. Return only display name, approved text, colors, asset URLs, legal links, and OIDC start URL. Do not return internal tenant IDs, entitlements, member counts, status history, messaging settings, or storage metadata. Asset routes verify tenant/asset association and emit `nosniff`, immutable ETag, and explicit image content type.

- [ ] **Step 3: Run GREEN and commit**

```powershell
uv run --project apps/api pytest apps/api/tests/api/routes/test_public_branding.py apps/api/tests/unit/test_tenant_host_resolver.py -q
git add apps/api/app/api/routes/public_branding.py apps/api/app/domain/branding/host_resolver.py apps/api/app/core/config.py apps/api/tests/api/routes/test_public_branding.py apps/api/tests/unit/test_tenant_host_resolver.py apps/api/app/api/main.py
git commit -m "feat: expose safe tenant entry branding"
```

### Task 3: Build tenant branding and messaging administration

**Files:**
- Create: `apps/api/app/api/routes/branding_admin.py`
- Modify: `apps/api/app/api/main.py`
- Create: `apps/api/tests/api/routes/test_branding_admin.py`
- Create: `apps/api/app/domain/branding/projection.py`
- Test: `apps/api/tests/unit/test_branding_projection.py`
- Create: `apps/web/src/features/admin/branding/BrandingEditor.tsx`
- Create: `apps/web/src/features/admin/branding/BrandingPreview.tsx`
- Create: `apps/web/src/routes/_layout/admin.branding.tsx`
- Modify: `apps/web/src/routes/_layout/admin.messaging.tsx`
- Test: `apps/web/tests/branding-admin.spec.ts`

- [ ] **Step 1: Write failing admin scenarios**

Assert authenticated logo/hero upload validation, headline/copy/colors preview, draft lifecycle transitions, rollback-as-new-version, optimistic-version conflict, save/publish separation, audit actor, and ARA-admin inability to edit AI Consulting. API tests prove a tenant owner can mutate only its own draft, product admins without branding capability are denied, and platform support requires an active branding support grant.

- [ ] **Step 2: Implement the form with exact constraints**

`branding_admin.py` exposes tenant-scoped create-draft, upload-asset, preview, validate, publish, rollback, and history endpoints using the same capability dependency as Tenant Admin. Use Zod to require 3-80 character product name, 3-120 character headline, 3-300 character supporting copy, six-digit hex colors, HTTPS support/privacy/legal links, and PNG/JPEG/WebP assets no larger than 5 MB. Validation rejects prohibited markup/tracking, insufficient contrast, missing required links, and product-card copy for an unentitled product. Only a `VALIDATED` draft may publish; publishing creates a new immutable `PUBLISHED` version, marks the former version `SUPERSEDED`, records audit, invalidates the public cache, and emits a signed branding-projection outbox event. Rollback creates and publishes a new version copied from a prior version; it never edits history. Messaging settings expose approved tenant-level copy and escalation/contact details; system safety notices remain platform-owned and immutable to tenants.

- [ ] **Step 3: Run GREEN and commit**

```powershell
uv run --project apps/api pytest apps/api/tests/api/routes/test_branding_admin.py apps/api/tests/unit/test_branding_projection.py -q
npm --workspace frontend run test -- branding-admin.spec.ts
npm --workspace frontend run build
git add apps/api/app/api/routes/branding_admin.py apps/api/app/api/main.py apps/api/app/domain/branding/projection.py apps/api/tests/api/routes/test_branding_admin.py apps/api/tests/unit/test_branding_projection.py apps/web/src/features/admin/branding apps/web/src/routes/_layout/admin.branding.tsx apps/web/src/routes/_layout/admin.messaging.tsx apps/web/tests/branding-admin.spec.ts
git commit -m "feat: add tenant branding administration"
```

### Task 4: Build ARA and AI Consulting suite entry variants

**Files:**
- Create: `apps/web/src/features/entry/SuiteEntryPage.tsx`
- Create: `apps/web/src/features/entry/TenantSuiteEntry.tsx`
- Create: `apps/web/src/features/entry/UnavailableSuiteEntry.tsx`
- Create: `apps/web/src/routes/index.tsx`
- Create: `config/tenants/assets/ara-global-hero.png`
- Create: `config/tenants/assets/ara-global-hero.provenance.json`
- Create: `tooling/import-approved-brand-asset.ps1`
- Test: `apps/web/tests/suite-entry.spec.ts`

- [ ] **Step 1: Write failing visual-content assertions**

```typescript
test("ARA presents one suite login and all three products", async ({ page }) => {
  await page.goto("http://ara.localhost:5173/")
  await expect(page.getByRole("heading", { name: "ARA Global Revenue Workspace" })).toBeVisible()
  await expect(page.getByText("Turn every customer commitment into coordinated action.")).toBeVisible()
  await expect(page.getByText("CommitArc")).toBeVisible()
  await expect(page.getByText("RevenueOS")).toBeVisible()
  await expect(page.getByText("SignalLoop")).toBeVisible()
  await expect(page.getByRole("button", { name: "Continue with your work account" })).toHaveCount(1)
})
```

Also assert AI Consulting displays `AI Consulting Revenue Workspace`, uses neutral configured copy and abstract graphics with no customer photograph, unknown/inactive tenant returns the same neutral not-available entry without disclosure, and HaloEHS returns that not-provisioned behavior.

- [ ] **Step 2: Implement the resolver-driven page**

Before acceptance-harness execution, run `tooling/import-approved-brand-asset.ps1` once against the former approved source `https://araglobalinc.com/wp-content/uploads/2025/10/ARA-Global-banner-4-scaled.png`. The script decodes/re-encodes it, writes the normalized PNG to `config/tenants/assets/ara-global-hero.png`, and writes source, acquisition time, dimensions, byte count, and computed SHA-256 to the provenance JSON. Both files are reviewed and committed; onboarding and acceptance read only this pinned local artifact and never fetch the remote source. `PostgresBrandAssetStore` revalidates it on upload and records the same digest in evidence. ARA presents one suite login plus three product capability cards. AI Consulting uses configured neutral abstract graphics. No variant hardcodes credentials, product entitlements, internal IDs, or pricing.

- [ ] **Step 3: Run desktop/narrow GREEN and commit**

```powershell
npm --workspace frontend run test -- suite-entry.spec.ts
npm --workspace frontend run build
git add apps/web/src/features/entry apps/web/src/routes/index.tsx apps/web/tests/suite-entry.spec.ts config/tenants/assets/ara-global-hero.png config/tenants/assets/ara-global-hero.provenance.json tooling/import-approved-brand-asset.ps1
git commit -m "feat: add tenant suite entry pages"
```

### Task 5: Project in-app branding to CommitArc without changing its generic landing

**Files:**
- Modify: `C:\My Workspace\eCRM\.worktrees\enterprise-tenancy\prisma\schema.prisma`
- Create: `C:\My Workspace\eCRM\.worktrees\enterprise-tenancy\prisma\migrations\20260809131000_version_organization_branding\migration.sql`
- Create: `C:\My Workspace\eCRM\.worktrees\enterprise-tenancy\src\server\organizations\branding-projection.ts`
- Create: `C:\My Workspace\eCRM\.worktrees\enterprise-tenancy\src\app\api\platform\projections\branding\route.ts`
- Modify: `C:\My Workspace\eCRM\.worktrees\enterprise-tenancy\src\components\app-shell.tsx`
- Test: `C:\My Workspace\eCRM\.worktrees\enterprise-tenancy\src\server\organizations\branding-projection.test.ts`
- Test: `C:\My Workspace\eCRM\.worktrees\enterprise-tenancy\src\app\(auth)\login\login-landing.test.tsx`

- [ ] **Step 1: Write failing version and generic-landing regression tests**

Assert signed projection monotonicity and tenant match. Assert the public CommitArc login still displays `CommitArc` generic content and no `ARA Global` copy.

- [ ] **Step 2: Implement in-app projection**

Add `sourceVersion` and `publishedAt` to `OrganizationBranding`; the authenticated platform projection route reuses the membership projection's signature verifier, replay store, five-minute age limit, tenant mapping, and monotonic-version transaction. Apply product name/logo/colors only after authenticated organization resolution. Do not branch public login content on user-supplied query parameters.

- [ ] **Step 3: Run GREEN and commit**

```powershell
npm test -- src/server/organizations/branding-projection.test.ts 'src/app/(auth)/login/login-landing.test.tsx' src/components/app-shell.test.tsx
npm run gate
git add prisma/schema.prisma prisma/migrations/20260809131000_version_organization_branding src/server/organizations/branding-projection.ts src/app/api/platform/projections/branding/route.ts src/components/app-shell.tsx
git commit -m "feat: apply tenant branding inside commit arc"
```

### Task 6: Branding acceptance gate

- [ ] Capture desktop and narrow screenshots for generic, ARA, and AI Consulting entry pages.
- [ ] Verify keyboard navigation, contrast, alt text, heading hierarchy, and reduced-motion behavior.
- [ ] Verify malicious assets, stale versions, unknown hosts/slugs, disabled tenants, and cross-tenant edits fail safely.
- [ ] Verify the generic CommitArc landing remains byte-for-byte free of ARA-specific text and remote image dependencies.
