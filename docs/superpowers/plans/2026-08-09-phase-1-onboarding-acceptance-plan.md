# Phase 1 Onboarding and Acceptance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Provision, reconcile, verify, and recover ARA Global and AI Consulting across CommitArc, RevenueOS, SignalLoop, and OIDC with repeatable evidence and no manual database edits.

**Architecture:** SignalLoop runs an idempotent onboarding state machine and calls signed application-specific provisioners. Each stage records request digest, version, status, attempts, evidence, and compensating action; reruns reconcile desired and observed state. A PowerShell acceptance orchestrator starts disposable dependencies, executes both product gates, and writes a secret-free signed manifest.

**Tech Stack:** FastAPI, SQLModel, Alembic, PostgreSQL, cryptography/Ed25519, Prisma, PowerShell, pytest, Vitest, Playwright.

---

### Task 1: Persist the onboarding state machine

**Files:**
- Create: `apps/api/app/domain/onboarding/models.py`
- Create: `apps/api/app/domain/onboarding/schemas.py`
- Create: `apps/api/app/alembic/versions/p1_onboard_20260809_add_onboarding_runs.py`
- Modify: `apps/api/app/models.py`
- Test: `apps/api/tests/unit/test_onboarding_models.py`

- [ ] **Step 1: Write failing transition tests**

```python
@pytest.mark.parametrize(
    ("current", "next_status", "allowed"),
    [("PENDING", "RUNNING", True), ("RUNNING", "SUCCEEDED", True),
     ("RUNNING", "FAILED", True), ("SUCCEEDED", "RUNNING", False)],
)
def test_stage_transition_table(current, next_status, allowed):
    assert can_transition(current, next_status) is allowed
```

- [ ] **Step 2: Run RED and create exact stages**

Stages are exactly `TENANT_DRAFTED`, `PRODUCTS_ASSIGNED`, `ENTRY_CONFIGURED`, `OWNER_INVITED`, `ROLES_ASSIGNED`, `POLICIES_PUBLISHED`, `NATIVE_INTEGRATION_VERIFIED`, `READY_FOR_ACCEPTANCE`, and `ACTIVE`. `ACTIVE` requires accepted OIDC invitation, issuer-confirmed MFA status, and all acceptance evidence. Persist run/stage IDs, tenant key, input hash, idempotency key, desired version, status, attempt count, start/end timestamps, actor/approver, safe result code, redacted evidence references, and rollback/compensation status.

The migration declares `revision = "p1_onboard_20260809"` and `down_revision = "p1_branding_20260809"`; require one Alembic head before and after rehearsal.

- [ ] **Step 3: Run GREEN and commit**

```powershell
uv run --project apps/api pytest apps/api/tests/unit/test_onboarding_models.py -q
git add apps/api/app/domain/onboarding apps/api/app/models.py apps/api/app/alembic/versions/p1_onboard_20260809_add_onboarding_runs.py apps/api/tests/unit/test_onboarding_models.py
git commit -m "feat: add tenant onboarding state machine"
```

### Task 2: Implement idempotent provisioning and reconciliation

**Files:**
- Create: `apps/api/app/domain/onboarding/service.py`
- Create: `apps/api/app/domain/onboarding/provisioners.py`
- Create: `apps/api/app/api/routes/onboarding.py`
- Modify: `apps/api/app/api/main.py`
- Test: `apps/api/tests/domain/test_onboarding_service.py`
- Test: `apps/api/tests/api/routes/test_onboarding.py`

- [ ] **Step 1: Write failing resume/reconcile tests**

```python
def test_retry_resumes_failed_stage_without_duplicating_prior_resources(service, request):
    first = service.run(request, fail_at="NATIVE_INTEGRATION_VERIFIED:signalloop")
    second = service.retry(first.id)
    assert second.status == "SUCCEEDED"
    assert service.count_tenants(request.tenant_key) == 1
    assert service.count_active_entitlements(request.tenant_key) == 3
```

- [ ] **Step 2: Run RED and implement stage executors**

Every executor compares desired and observed state before mutation and returns `CREATED`, `UPDATED`, or `UNCHANGED`. `NATIVE_INTEGRATION_VERIFIED` calls `NativeCanaryService`; any failed CommitArc, RevenueOS, SignalLoop, drift, or synthetic-provider canary blocks `READY_FOR_ACCEPTANCE`. Failures retain prior successful stages, expose a stable error code, and allow retry from the failed stage. Destructive rollback is limited to resources created by the same uncommitted onboarding run; active tenant data is never deleted automatically.

- [ ] **Step 3: Run GREEN and commit**

```powershell
uv run --project apps/api pytest apps/api/tests/domain/test_onboarding_service.py apps/api/tests/api/routes/test_onboarding.py -q
git add apps/api/app/domain/onboarding/service.py apps/api/app/domain/onboarding/provisioners.py apps/api/app/api/routes/onboarding.py apps/api/app/api/main.py apps/api/tests/domain/test_onboarding_service.py apps/api/tests/api/routes/test_onboarding.py
git commit -m "feat: automate tenant onboarding reconciliation"
```

### Task 3: Define the Phase 1 tenant manifests

**Files:**
- Create: `config/tenants/ara-global.phase1.json`
- Create: `config/tenants/ai-consulting.phase1.json`
- Create: `apps/api/app/domain/onboarding/manifest.py`
- Test: `apps/api/tests/unit/test_phase1_tenant_manifests.py`

- [ ] **Step 1: Write failing manifest assertions**

```python
def test_phase1_manifests_enable_all_products_and_exclude_halo():
    manifests = load_phase1_manifests()
    assert set(manifests) == {"ara-global", "ai-consulting"}
    assert all(set(m.products) == {"commitarc", "revenueos", "signalloop"} for m in manifests.values())
```

- [ ] **Step 2: Add validated secret-free manifests**

Each manifest contains tenant key/legal/display name, region, locale, time zone, currency, allowed email domains, product entitlements/editions, first named Tenant Owner email, all four approved admin role bundles, branding text/colors/pinned local asset path and SHA-256, messaging overrides, knowledge-release IDs, consent/jurisdiction/quiet-hours policy, autonomy thresholds, budgets/frequency caps, kill-switch defaults, and secret reference names. ARA additionally carries tenant-data references for tax, payment-cycle, and contract-term knowledge. AI Consulting additionally carries United States consent/channel policy and neutral abstract-branding configuration. OIDC groups are not accepted as authorization; suite roles come only from these authoritative assignments. The manifest contains no password, client secret, signing key, bearer token, provider credential, or customer lead data. Secrets are supplied through the runtime secret provider by reference name.

- [ ] **Step 3: Run GREEN and commit**

```powershell
uv run --project apps/api pytest apps/api/tests/unit/test_phase1_tenant_manifests.py -q
git add config/tenants apps/api/app/domain/onboarding/manifest.py apps/api/tests/unit/test_phase1_tenant_manifests.py
git commit -m "config: define phase one launch tenants"
```

### Task 4: Build signed evidence bundles

**Files:**
- Create: `apps/api/app/domain/onboarding/evidence.py`
- Create: `apps/api/tests/unit/test_onboarding_evidence.py`
- Create: `tooling/verify-onboarding-evidence.ps1`

- [ ] **Step 1: Write failing redaction and signature tests**

```python
def test_evidence_is_signed_and_contains_no_secrets(evidence_builder, completed_run):
    bundle = evidence_builder.build(completed_run)
    assert verify_ed25519(bundle.manifest, bundle.signature)
    serialized = bundle.manifest.model_dump_json().lower()
    assert all(word not in serialized for word in ["password", "client_secret", "access_token", "bearer "])
```

- [ ] **Step 2: Implement canonical evidence**

The manifest records tenant key, desired version/digest, application commit hashes, migration heads, stage outcomes, test command names/results/timestamps, branding version, entitlements, role-count summaries, and SHA-256 hashes of artifacts. Sign canonical JSON with an Ed25519 private key from the runtime secret provider; include only the public key ID.

- [ ] **Step 3: Run GREEN, verify with PowerShell, and commit**

```powershell
uv run --project apps/api pytest apps/api/tests/unit/test_onboarding_evidence.py -q
powershell -ExecutionPolicy Bypass -File tooling/verify-onboarding-evidence.ps1 -Fixture
git add apps/api/app/domain/onboarding/evidence.py apps/api/tests/unit/test_onboarding_evidence.py tooling/verify-onboarding-evidence.ps1
git commit -m "feat: sign onboarding evidence bundles"
```

### Task 5: Add cross-repository disposable acceptance orchestration

**Files:**
- Create: `tooling/run-phase1-suite-acceptance.ps1`
- Create: `apps/web/tests/phase1-suite-acceptance.spec.ts`
- Create: `C:\My Workspace\eCRM\.worktrees\enterprise-tenancy\tests\e2e\phase1-suite-acceptance.spec.ts`
- Create: `docs/operations/phase1-suite-acceptance.md`

- [ ] **Step 1: Write a failing dry-run contract test**

The script's `-WhatIf` output must list fresh PostgreSQL databases, fake OIDC provider, SignalLoop API/web, CommitArc, ARA and AI manifests, both Playwright suites, evidence verification, and shutdown; it must not mutate the developer databases.

- [ ] **Step 2: Implement safe orchestration**

The script resolves both worktrees, rejects production-like database hosts, allocates unused localhost ports, creates uniquely named disposable databases, runs all migrations, starts deterministic fake OIDC, email, SMS, chat, voice, scheduling, and payment/provider endpoints, provisions both tenants twice, runs both browser suites, verifies evidence, captures logs, stops child processes in `finally`, and retains failed-run artifacts under a uniquely named temp directory. Fixtures use reserved `.test` email domains, non-routable phone numbers, and synthetic business records. A network-egress spy fails the run if any provider request leaves loopback. The script never invokes either repository's general seed against a non-disposable database.

- [ ] **Step 3: Run the full acceptance command**

```powershell
powershell -ExecutionPolicy Bypass -File tooling/run-phase1-suite-acceptance.ps1
```

Expected scenarios:

- ARA: tenant-branded suite entry, one OIDC login, all three product cards, tenant admin, employee Essentials, campaign operator SignalLoop, cross-tenant denial.
- AI Consulting: neutral configured suite entry, one OIDC login, all three products, independent admin/users/data, knowledge-grounded RevenueOS behavior.
- Platform admin: tenant/product/invitation controls but no tenant data without support grant.
- Support grant: explicit reason/approval, audit on use, expiry denial.
- Rerun: no duplicate tenants, memberships, entitlements, identities, or projections.
- HaloEHS: absent from provisioned tenants and cannot resolve a tenant entry.

- [ ] **Step 4: Commit in each repository**

SignalLoop commit:

```powershell
git add tooling/run-phase1-suite-acceptance.ps1 apps/web/tests/phase1-suite-acceptance.spec.ts docs/operations/phase1-suite-acceptance.md
git commit -m "test: automate phase one suite acceptance"
```

CommitArc commit:

```powershell
git add tests/e2e/phase1-suite-acceptance.spec.ts
git commit -m "test: add commit arc suite acceptance"
```

### Task 6: Launch-readiness review

- [ ] Run security review for OIDC, invitations, projections, support access, uploads, and audit redaction.
- [ ] Run specification review against every acceptance criterion in the design spec and map each to a test/evidence item.
- [ ] Run quality review for maintainability and failure recovery.
- [ ] Verify both worktrees are clean except explicitly preserved pre-existing paths.
- [ ] Record final commit hashes and signed evidence locations; do not call the tenants launch-ready until every required gate is green.
