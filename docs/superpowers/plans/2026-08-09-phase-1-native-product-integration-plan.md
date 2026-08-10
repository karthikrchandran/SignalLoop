# Phase 1 Native Product Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect CommitArc, RevenueOS, and SignalLoop through tenant-scoped workload identity, idempotent projections, policy-gated commands, outcome evidence, and activation canaries without direct cross-database access.

**Architecture:** Each `ProductInstallation` receives an asymmetric workload key reference and product-local tenant mapping from the control plane. Short-lived signed request assertions bind issuer, audience, installation, tenant, capability, body digest, idempotency key, and replay ID. CommitArc publishes business/workflow projections; RevenueOS decides interventions; SignalLoop executes engagement; both products return evidence and outcomes to RevenueOS.

**Tech Stack:** FastAPI, SQLModel, httpx, cryptography/Ed25519, Next.js route handlers, Prisma, jose, PostgreSQL, pytest, Vitest, Playwright.

---

### Task 1: Define workload identity and installation credentials

**Files:**
- Create: `apps/api/app/domain/installations/workload_identity.py`
- Create: `apps/api/app/domain/installations/service.py`
- Modify: `apps/api/app/domain/tenants/models.py`
- Modify: `apps/api/app/models.py`
- Create: `apps/api/app/alembic/versions/p1_install_20260809_add_installation_security.py`
- Test: `apps/api/tests/unit/test_workload_identity.py`
- Create: `apps/api/tests/fixtures/workload-identity-vector.json`

- [ ] **Step 1: Write the failing assertion tests**

```python
@pytest.mark.parametrize("fault", ["expired", "wrong_audience", "wrong_tenant", "wrong_digest", "replayed_jti"])
def test_workload_assertion_fails_closed(verifier, signed_assertion, fault):
    with pytest.raises(WorkloadIdentityError):
        verifier.verify(signed_assertion.with_fault(fault))
```

- [ ] **Step 2: Run RED**

```powershell
uv run --project apps/api pytest apps/api/tests/unit/test_workload_identity.py -q
```

Expected: collection fails because `app.domain.installations` does not exist.

- [ ] **Step 3: Implement the exact assertion contract**

```python
class WorkloadClaims(BaseModel):
    iss: Literal["commitarc", "revenueos", "signalloop"]
    aud: Literal["commitarc", "revenueos", "signalloop"]
    sub: UUID
    tenant_key: str
    capability: str
    body_sha256: str
    idempotency_key: str
    jti: UUID
    iat: int
    exp: int
```

The JWT header uses exactly `alg=EdDSA`, `kid` equal to the active installation key ID, and `typ=JWT`; the checked-in fixture uses concrete key ID `phase1-test-key-1`. `sub` is the installation ID. `body_sha256` is base64url SHA-256 of the exact transmitted request bytes (empty bytes for no body), avoiding cross-language JSON reserialization. The shared fixture contains a test public key, body bytes, expected digest, compact JWT, and decoded claims; Python and TypeScript tests must verify the same vector. Sign with an Ed25519 private-key secret reference; persist only key ID/public key/status on `ProductInstallation`. Persist `NativeProjectionCursor`, `NativeProjectionReceipt`, and consumed mutation `jti` values. The migration declares `revision = "p1_install_20260809"`, `down_revision = "p1_control_20260809"`, and adds the installation key/version/status plus projection/cursor/receipt tables. Accept at most a two-minute lifetime and 30-second clock skew. Rotation overlaps old/new public keys for a bounded window and audits the actor.

- [ ] **Step 4: Run GREEN**

```powershell
uv run --project apps/api pytest apps/api/tests/unit/test_workload_identity.py -q
uv run --project apps/api ruff check apps/api/app/domain/installations apps/api/tests/unit/test_workload_identity.py
```

- [ ] **Step 5: Commit**

```powershell
git add apps/api/app/domain/installations apps/api/app/domain/tenants/models.py apps/api/app/models.py apps/api/app/alembic/versions/p1_install_20260809_add_installation_security.py apps/api/tests/unit/test_workload_identity.py apps/api/tests/fixtures/workload-identity-vector.json
git commit -m "feat: add tenant workload identity"
```

### Task 2: Replace CommitArc's static integration token with installation verification

**Files:**
- Create: `C:\My Workspace\eCRM\.worktrees\enterprise-tenancy\src\server\integrations\workload-identity.ts`
- Create: `C:\My Workspace\eCRM\.worktrees\enterprise-tenancy\src\server\integrations\installation-context.ts`
- Modify: `C:\My Workspace\eCRM\.worktrees\enterprise-tenancy\prisma\schema.prisma`
- Create: `C:\My Workspace\eCRM\.worktrees\enterprise-tenancy\prisma\migrations\20260809130700_add_organization_installations\migration.sql`
- Create: `C:\My Workspace\eCRM\.worktrees\enterprise-tenancy\src\app\api\platform\projections\installations\route.ts`
- Modify: `C:\My Workspace\eCRM\.worktrees\enterprise-tenancy\src\app\api\shared-records\route.ts`
- Modify: `C:\My Workspace\eCRM\.worktrees\enterprise-tenancy\src\app\api\workflow-events\route.ts`
- Create: `C:\My Workspace\eCRM\.worktrees\enterprise-tenancy\src\app\api\integrations\signalloop\canary\route.ts`
- Test: `C:\My Workspace\eCRM\.worktrees\enterprise-tenancy\src\server\integrations\workload-identity.test.ts`
- Create: `C:\My Workspace\eCRM\.worktrees\enterprise-tenancy\src\server\integrations\workload-identity-vector.json`

- [ ] **Step 1: Write failing authority tests**

```typescript
it.each(["expired", "wrong-audience", "wrong-tenant", "wrong-digest", "replay"])(
  "rejects %s workload assertion",
  async (fault) => expect(resolveInstallationContext(requestWithFault(fault))).rejects.toThrow(WorkloadIdentityError),
)
```

- [ ] **Step 2: Run RED**

```powershell
npm test -- src/server/integrations/workload-identity.test.ts
```

- [ ] **Step 3: Implement server-derived installation context**

Add `OrganizationInstallation` (control-plane installation ID, organization ID, tenant key, product code, status, outbound issuer, outbound private-key secret reference, projection version), `OrganizationInstallationKey` (installation, key ID, public key, status, valid-from/to), and `IntegrationReplayReceipt` (installation, JTI, expiry) with tenant-scoped constraints. The signed installation projection route applies create/rotate/revoke changes idempotently and never receives private key material; deployment secret configuration supplies only the named outbound secret reference. Use `jose.jwtVerify` with the active local installation key. Resolve `organizationId` from local `OrganizationInstallation.tenantKey -> Organization.key`; never access the SignalLoop database or accept authority from an ordinary header, query, or body. Require endpoint-specific capability, exact raw-body digest, idempotency key, and unused replay ID before calling `withOrganization`. The same module exposes `createWorkloadAssertion` for CommitArc-to-RevenueOS calls, using the local secret reference and never exposing it to browser code. Rotation keeps the prior public key valid only through its projected overlap time; revocation fails closed. Keep the old shared token disabled unless `INTEGRATION_AUTH_MODE=legacy-local-test`, and reject that mode in production.

```typescript
export async function resolveInstallationContext(request: Request): Promise<InstallationContext>
export async function createWorkloadAssertion(input: WorkloadAssertionInput): Promise<string>
```

- [ ] **Step 4: Run GREEN**

```powershell
npx prisma validate
npx prisma generate
npm test -- src/server/integrations/workload-identity.test.ts src/server/shared-records src/server/workflow-events
npm run typecheck
```

- [ ] **Step 5: Commit**

```powershell
git add prisma/schema.prisma prisma/migrations/20260809130700_add_organization_installations src/server/integrations src/app/api/platform/projections/installations/route.ts src/app/api/shared-records/route.ts src/app/api/workflow-events/route.ts src/app/api/integrations/signalloop/canary/route.ts
git commit -m "fix: secure commit arc integration identity"
```

### Task 3: Build the CommitArc client and projection ingestion in RevenueOS

**Files:**
- Create: `apps/api/app/integrations/commit_arc_client.py`
- Create: `apps/api/app/domain/native_integration/schemas.py`
- Create: `apps/api/app/domain/native_integration/service.py`
- Create: `apps/api/app/api/routes/native_integration.py`
- Modify: `apps/api/app/api/main.py`
- Test: `apps/api/tests/unit/test_commit_arc_client.py`
- Test: `apps/api/tests/api/routes/test_native_integration.py`

- [ ] **Step 1: Write failing tenant/digest/idempotency tests**

```python
def test_client_signs_same_tenant_and_body_digest(client, fake_http):
    client.list_business_projection(TENANT_A, installation_id=INSTALL_A, cursor="c1")
    claims = fake_http.last_workload_claims()
    assert claims.tenant_key == TENANT_A
    assert claims.body_sha256 == fake_http.last_body_sha256()
```

- [ ] **Step 2: Run RED**

```powershell
uv run --project apps/api pytest apps/api/tests/unit/test_commit_arc_client.py apps/api/tests/api/routes/test_native_integration.py -q
```

- [ ] **Step 3: Implement bounded contracts**

`CommitArcClient` exposes `canary`, `list_business_projection(cursor)`, `publish_workflow_state(command)`, and `fetch_essentials_context(subject, cursor)`. `NativeIntegrationService` stores source event ID/version, tenant, safe record identifier, payload digest, observed time, cursor, and reconciliation status. Duplicate source versions are unchanged; lower versions are rejected; tenant/key drift blocks the installation. All httpx calls have bounded connect/read timeouts and retry only idempotent operations.

```python
class CommitArcClient(Protocol):
    async def canary(self, tenant_key: str) -> CanaryResult: ...
    async def list_business_projection(self, tenant_key: str, installation_id: UUID, cursor: str | None) -> ProjectionPage: ...
    async def publish_workflow_state(self, tenant_key: str, command: WorkflowCommand) -> WriteResult: ...
    async def fetch_essentials_context(self, tenant_key: str, issuer: str, subject: str) -> EssentialsContext: ...
```

- [ ] **Step 4: Run GREEN**

```powershell
uv run --project apps/api pytest apps/api/tests/unit/test_commit_arc_client.py apps/api/tests/api/routes/test_native_integration.py -q
```

- [ ] **Step 5: Commit**

```powershell
git add apps/api/app/integrations/commit_arc_client.py apps/api/app/domain/native_integration apps/api/app/api/routes/native_integration.py apps/api/app/api/main.py apps/api/tests/unit/test_commit_arc_client.py apps/api/tests/api/routes/test_native_integration.py
git commit -m "feat: ingest commit arc revenue context"
```

### Task 4: Link intervention dispatch and outcome evidence end to end

**Files:**
- Modify: `apps/api/app/domain/interventions/service.py`
- Modify: `apps/api/app/domain/outreach/action_queue_service.py`
- Modify: `apps/api/app/domain/outreach/outbox_service.py`
- Create: `apps/api/app/domain/native_integration/outcome_service.py`
- Modify: `apps/workers/worker_app/intervention_worker.py`
- Test: `apps/api/tests/domain/test_native_intervention_flow.py`
- Test: `apps/workers/tests/unit/test_enforcement_gate.py`

- [ ] **Step 1: Write the failing synthetic flow test**

```python
def test_signal_to_policy_to_dispatch_to_outcome_is_traceable(flow):
    outcome = flow.run_synthetic(tenant="ara-global", source_event="commit-7")
    assert outcome.trace == ["signal", "policy", "intervention", "outbox", "provider_attempt", "outcome"]
    assert outcome.tenant_key == "ara-global"
    assert outcome.real_provider_calls == 0
```

- [ ] **Step 2: Run RED**

```powershell
uv run --project apps/api pytest apps/api/tests/domain/test_native_intervention_flow.py -q
```

- [ ] **Step 3: Implement policy-gated dispatch**

Before enqueue, recheck tenant/product entitlement, capability, published knowledge, consent/suppression, jurisdiction/quiet hours, autonomy, budget/frequency caps, provider readiness, idempotency, and kill switch. A CommitArc workflow command uses its installation client; a SignalLoop engagement command uses the tenant queue. Persist provider attempt, delivery result, cost, CommitArc revenue milestone, and attribution to signal/decision/intervention. Any missing knowledge/consent suppresses rather than guesses or sends.

```python
def dispatch(intervention: Intervention, context: EnforcementContext) -> DispatchResult:
    decision = enforcement_gate.evaluate(intervention, context)
    return outbox.enqueue(intervention) if decision.allowed else DispatchResult.suppressed(decision.reason)
```

- [ ] **Step 4: Run GREEN**

```powershell
uv run --project apps/api pytest apps/api/tests/domain/test_native_intervention_flow.py -q
uv run --project apps/workers pytest apps/workers/tests/unit/test_enforcement_gate.py -q
```

- [ ] **Step 5: Commit**

```powershell
git add apps/api/app/domain/interventions/service.py apps/api/app/domain/outreach/action_queue_service.py apps/api/app/domain/outreach/outbox_service.py apps/api/app/domain/native_integration/outcome_service.py apps/workers/worker_app/intervention_worker.py apps/api/tests/domain/test_native_intervention_flow.py apps/workers/tests/unit/test_enforcement_gate.py
git commit -m "feat: connect revenue interventions to outcomes"
```

### Task 5: Gate tenant activation with native canaries and reconciliation

**Files:**
- Create: `apps/api/app/domain/native_integration/canary_service.py`
- Test: `apps/api/tests/domain/test_native_canary_service.py`

- [ ] **Step 1: Write failing readiness tests**

```python
def test_failed_product_canary_blocks_readiness(service):
    result = service.verify_all(tenant_key="ara-global", fail_product="signalloop")
    assert result.ready is False
    assert result.by_product["signalloop"].result_code == "CANARY_FAILED"
```

- [ ] **Step 2: Run RED**

```powershell
uv run --project apps/api pytest apps/api/tests/domain/test_native_canary_service.py -q
```

- [ ] **Step 3: Implement canary evidence**

Return one result per product with installation ID, capability, safe canary ID, start/end, result code, reconciliation counts, and artifact hash. Store no credential or business payload. Retry only the failed idempotent canary and retain the prior failure evidence.

```python
class NativeReadiness(BaseModel):
    ready: bool
    by_product: dict[ProductCode, CanaryEvidence]
```

- [ ] **Step 4: Run GREEN**

```powershell
uv run --project apps/api pytest apps/api/tests/domain/test_native_canary_service.py -q
```

- [ ] **Step 5: Commit**

```powershell
git add apps/api/app/domain/native_integration/canary_service.py apps/api/tests/domain/test_native_canary_service.py
git commit -m "test: gate tenants on native integration canaries"
```

### Task 6: Native integration security gate

- [ ] Prove ARA credentials, keys, cursors, IDs, and idempotency keys cannot operate on AI Consulting, and vice versa.
- [ ] Prove replay, stale projection, wrong body digest, disabled installation, removed entitlement, expired key, and provider outage fail closed.
- [ ] Prove there are no direct cross-database connections in environment templates, source, or runtime process lists.
- [ ] Prove synthetic acceptance uses fake providers and records zero outbound email, SMS, chat, voice, or scheduling calls.
