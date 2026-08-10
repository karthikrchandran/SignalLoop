# Phase 1 Client Suite Program Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver one enterprise-grade, tenant-aware suite in which ARA Global and AI Consulting can use CommitArc, RevenueOS, and SignalLoop through centralized OIDC, distinct authorization, role-specific experiences, tenant administration, branding, and repeatable onboarding.

**Architecture:** SignalLoop remains the suite control plane and RevenueOS host; CommitArc remains an independently deployable CRM with its own database and authorization projection. One external OIDC issuer authenticates users, while each application derives permissions from local tenant memberships and entitlements. Cross-product integration is API/event based; neither application reads the other's database.

**Tech Stack:** FastAPI, SQLModel, Alembic, PostgreSQL, PyJWT, httpx, React, Vite, TanStack Router/Query, Playwright, Next.js 16, Prisma 6, jose, Vitest.

---

## Governing documents

- Design: `docs/superpowers/specs/2026-08-09-phase-1-client-suite-admin-and-experience-design.md`
- Revenue intervention engine: `docs/superpowers/plans/2026-08-09-revenueos-enterprise-implementation-plan.md`, Tasks 8-10
- Tenant/product packaging: `docs/enterprise/2026-08-09-tenant-onboarding-and-product-packaging.md`
- This plan package:
  - `docs/superpowers/plans/2026-08-09-phase-1-oidc-identity-plan.md`
  - `docs/superpowers/plans/2026-08-09-phase-1-platform-control-plane-plan.md`
  - `docs/superpowers/plans/2026-08-09-phase-1-native-product-integration-plan.md`
  - `docs/superpowers/plans/2026-08-09-phase-1-unified-employee-experience-plan.md`
  - `docs/superpowers/plans/2026-08-09-phase-1-tenant-branding-admin-plan.md`
  - `docs/superpowers/plans/2026-08-09-phase-1-onboarding-acceptance-plan.md`

## Non-negotiable boundaries

- CommitArc, RevenueOS, and SignalLoop remain separately entitled and separately sellable.
- RevenueOS is a distinct module inside the SignalLoop repository, not a third repository.
- Every CommitArc employee gets RevenueOS Essentials; full RevenueOS and SignalLoop access require explicit entitlements and role bundles.
- A platform administrator may manage tenants but may not read tenant business data without a time-bounded, audited support grant.
- OIDC proves identity only. Tenant, role, product, and data permissions are always loaded from local application data.
- No external CRM connector or external campaign-management connector is delivered in Phase 1.
- HaloEHS is not provisioned in Phase 1.
- Existing dirty files in either worktree are never staged by unrelated work packages.

The entitlement model must support the complete suite (recommended), RevenueOS + CommitArc, RevenueOS + SignalLoop, CommitArc standalone, and SignalLoop standalone. RevenueOS-only may be represented for future compatibility but is marked `NOT_RECOMMENDED` in Phase 1 because external CRM and campaign-management connectors are absent.

## Design coverage index

| Approved design area | Owning implementation plan |
|---|---|
| OIDC, immutable subject, invitations, MFA/recovery handoff, secure sessions | OIDC Identity Tasks 1-7 |
| Suite membership, composable bundles, product entitlements, platform/tenant admin | Platform Control Plane Tasks 1-7 |
| Time-bounded support and audit propagation | Platform Control Plane Task 4 |
| Native CommitArc signals/writeback, SignalLoop dispatch, RevenueOS outcomes | Native Product Integration Tasks 1-6 plus enterprise Tasks 8-10 |
| Unified home, RevenueOS Essentials, hidden-and-denied SignalLoop | Unified Employee Experience Tasks 1-5 |
| Verified tenant entry, immutable branding, ARA/AI landing, generic CommitArc regression | Tenant Branding and Administration Tasks 1-6 |
| Knowledge-grounded autonomy, consent, budgets, kill switches | Enterprise plan Tasks 8-10 |
| Idempotent onboarding, exact lifecycle, evidence, recovery, ARA/AI fixtures | Onboarding and Acceptance Tasks 1-6 |
| HaloEHS deferral and connector deferral | Program boundaries and acceptance assertions |

## Program sequence and gates

### Task 0: Close both product-isolation baselines

**Files:**
- Continue only the existing files named by Task 4 in `docs/superpowers/plans/2026-08-09-revenueos-enterprise-implementation-plan.md`.
- Preserve: `apps/web/src/routeTree.gen.ts` in SignalLoop and `.tmp-pg-quality/` in eCRM.

- [ ] **Step 1: Resume the paused WP4 review-fix package**

Close the executable A/B matrix, same-transaction foreign-ID checks, `IncentiveSplit.userId`, and workflow-system-owner findings already recorded by the review.

- [ ] **Step 2: Run the eCRM isolation gate**

Run from `C:\My Workspace\eCRM\.worktrees\enterprise-tenancy`:

```powershell
npm run typecheck
npm run lint
npm test -- src/server/organizations/tenant-adversarial-matrix.integration.test.ts src/server/organizations/tenant-rls.integration.test.ts
npx playwright test tests/e2e/tenant-isolation.spec.ts
npm run build
```

Expected: every command exits `0`; the known date-sensitive report test is not part of this focused gate.

- [ ] **Step 3: Obtain two-stage review approval and commit only WP4 files**

```powershell
git diff --check
git status --short
git add src/server/organizations/tenant-adversarial-matrix.ts src/server/organizations/tenant-adversarial-matrix.test.ts src/server/organizations/tenant-adversarial-database.ts src/server/organizations/tenant-adversarial-matrix.integration.test.ts src/server/finance/mutations.ts src/server/workflow-events/service.ts src/server/crm/mutations.ts src/server/crm/lead-import.ts src/server/opportunities/mutations.ts src/server/production/mutations.ts
git commit -m "fix: complete commit arc tenant isolation"
```

Expected: the commit excludes `.tmp-pg-quality/` and all SignalLoop files.

- [ ] **Step 4: Execute SignalLoop isolation before adding new Alembic revisions**

Execute Task 6 of `2026-08-09-revenueos-enterprise-implementation-plan.md`, including its API, queue, worker, consent, and migration tests. Its migration must declare `revision = "tenant_20260809"` and `down_revision = "psid_20260726"`. Require `uv run alembic heads` to report only `tenant_20260809` before OIDC work begins.

### Task 1: Establish OIDC primitives, then create the control-plane invitation authority

- [ ] Execute OIDC Tasks 1-3 in `2026-08-09-phase-1-oidc-identity-plan.md` to establish identity persistence, protocol validation, and secure application sessions. The OIDC migration chains from `tenant_20260809`.
- [ ] Execute Control Plane Tasks 1-3 in `2026-08-09-phase-1-platform-control-plane-plan.md` to establish tenants, entitlements, role bundles, and invitations.
- [ ] Execute OIDC Tasks 4-7 only after `TenantInvitation` exists; callback activation must not invent or email-match a user.
- [ ] Require security review approval before changing either application from password login to OIDC-first login.
- [ ] Record SignalLoop and CommitArc commit hashes in the onboarding evidence manifest.

### Task 2: Deliver the platform control plane and entitlements

- [ ] Execute Control Plane Tasks 4-7 after OIDC callback/session activation is green.
- [ ] Prove a platform administrator cannot query tenant business records without an active support grant.
- [ ] Prove tenant administrators cannot administer any other tenant.

### Task 3: Complete native integration and the RevenueOS engine foundation

- [ ] Treat this plan package as the replacement for the older plan's Tasks 5, 7, and 11 where their branding, tenant-control, entitlement, or onboarding contracts overlap.
- [ ] Execute Native Integration Tasks 1-3 in `2026-08-09-phase-1-native-product-integration-plan.md`.
- [ ] Execute Tasks 8-10 and Task 12 of `2026-08-09-revenueos-enterprise-implementation-plan.md` after entitlement resolution exists. At execution, set the old-plan migration chain exactly: `compliance_20260811.down_revision = "p1_install_20260809"`, `revenueos_20260812.down_revision = "compliance_20260811"`, and `acquisition_20260814.down_revision = "revenueos_20260812"`.
- [ ] Execute Native Integration Tasks 4-6 after the intervention/dispatch modules from old Task 10 exist.
- [ ] Apply Task 13's enterprise hardening gates, but replace its three-customer acceptance list with ARA Global and AI Consulting only; HaloEHS remains unprovisioned.
- [ ] Keep knowledge-grounded product capability, price, tax, contract, and payment-cycle answers authoritative; do not add free-form agent invention paths.
- [ ] Gate every intervention through consent, policy, evidence, idempotency, and auditable outcome recording.

### Task 4: Deliver role-based employee and administrator experiences

- [ ] Execute `2026-08-09-phase-1-unified-employee-experience-plan.md`.
- [ ] Execute `2026-08-09-phase-1-tenant-branding-admin-plan.md` after the engine/acquisition migration chain is stable; its first revision chains from `acquisition_20260814`.
- [ ] Run both product browser suites against the same OIDC issuer and the same ARA/AI tenant fixtures.

### Task 5: Automate onboarding and approve both launch tenants

- [ ] Execute every task in `2026-08-09-phase-1-onboarding-acceptance-plan.md`.
- [ ] Provision ARA Global and AI Consulting with all three products; do not provision HaloEHS.
- [ ] Produce evidence bundles that contain no passwords, client secrets, access tokens, or raw customer data.

## Review rhythm

Each implementation task uses this sequence:

1. Fresh implementation worker writes the failing test, records RED, writes the smallest implementation, records GREEN, and commits only that task.
2. A specification reviewer checks the commit against the named requirements and returns `APPROVED` or exact blockers.
3. After spec approval, a quality reviewer checks maintainability, security, and test strength.
4. Review fixes return to the same implementation worker and repeat both reviews.
5. The primary agent audits status, diff, and verification output before starting the next task.

## Program completion gate

Run from the SignalLoop worktree:

```powershell
uv run --project apps/api pytest apps/api/tests -q
uv run --project apps/api ruff check apps/api/app apps/api/tests
uv run --project apps/api mypy --config-file apps/api/pyproject.toml apps/api/app
npm run build
npm test
```

Run from the CommitArc worktree:

```powershell
npm run gate
npx playwright test tests/e2e/oidc-suite.spec.ts tests/e2e/tenant-admin.spec.ts tests/e2e/tenant-isolation.spec.ts
```

Then run:

```powershell
powershell -ExecutionPolicy Bypass -File tooling/run-phase1-suite-acceptance.ps1
```

The SignalLoop baseline captured on 2026-08-09 at commit `0e7b300` is 390 API tests passing/23 failing, 68 Ruff findings, and 559 mypy findings. Before the first implementation task, rerun the full commands above and record commit, counts, and failing identifiers in `docs/operations/enterprise-migration-baseline.md`; that refreshed record becomes the comparison baseline. Each work package must make its changed-file checks green and must not add or alter a baseline failure. Task 13 of the governing enterprise plan owns baseline debt burn-down; the suite is not called generally available until full API tests, Ruff, and mypy are green. ARA and AI Consulting acceptance additionally must pass identity, navigation, entitlement, branding, isolation, support-access, and onboarding scenarios; HaloEHS is absent; no browser console error or API `5xx` appears.
