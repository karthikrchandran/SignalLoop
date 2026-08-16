# Commercial Agent Registry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a tenant-isolated, slot-enforced registry for independently configured SignalLoop agent deployments and type-specific capacity.

**Architecture:** Add a focused `commercial_agents` domain beside the suite tenant control plane. Database constraints establish tenant, installation, workspace, catalog, entitlement, deployment, dependency, and usage ownership; transactional services enforce slot activation and usage reservation. Tenant-admin APIs use existing suite capabilities, durable HTTP idempotency, and append-only audit.

**Tech Stack:** FastAPI, SQLModel/SQLAlchemy, PostgreSQL/Alembic, pytest, Ruff.

---

### Task 1: Catalog, entitlement, deployment, dependency, and usage models

**Files:**
- Create: `apps/api/app/domain/commercial_agents/__init__.py`
- Create: `apps/api/app/domain/commercial_agents/models.py`
- Modify: `apps/api/app/models.py`
- Create: `apps/api/app/alembic/versions/p1_commercial_agent_registry_20260816.py`
- Test: `apps/api/tests/domain/test_commercial_agent_registry.py`

- [x] **Step 1: Write the failing model contract test**

```python
def test_agent_deployment_is_unique_inside_tenant_and_workspace(session):
    session.add_all([catalog(), entitlement(slots=1), deployment(name="primary")])
    session.commit()
    assert session.exec(select(AgentDeployment)).one().status == AgentDeploymentStatus.DRAFT
```

- [x] **Step 2: Run the test and verify RED**

Run: `uv run --env-file C:/Users/K.Ramachandran/eMailVoice/.env --directory apps/api pytest tests/domain/test_commercial_agent_registry.py -q`
Expected: collection fails because `app.domain.commercial_agents.models` does not exist.

- [x] **Step 3: Implement focused models and migration**

Define `AgentType`, `AgentDeploymentStatus`, `AgentCatalogDefinition`,
`AgentPlanEntitlement`, `AgentDeployment`, `AgentDependency`,
`AgentCapacityOverride`, `AgentUsageLedger`, and `AgentLifecycleEvent`. Use
composite uniqueness for catalog version, tenant contract version, deployment
name, and usage idempotency. Every mutable record has tenant/installation/
workspace ownership columns where applicable.

- [x] **Step 4: Run model and migration-chain tests GREEN**

Run: `uv run --env-file C:/Users/K.Ramachandran/eMailVoice/.env --directory apps/api pytest tests/domain/test_commercial_agent_registry.py tests/unit/test_phase1_migration_chain.py -q`
Expected: all tests pass and `uv run --directory apps/api alembic heads` prints one head.

- [x] **Step 5: Commit**

```text
git add apps/api/app/domain/commercial_agents apps/api/app/models.py apps/api/app/alembic/versions apps/api/tests/domain/test_commercial_agent_registry.py
git commit -m "feat: add commercial agent registry models"
```

### Task 2: Atomic activation and dependency enforcement

**Files:**
- Create: `apps/api/app/domain/commercial_agents/service.py`
- Modify: `apps/api/tests/domain/test_commercial_agent_registry.py`

- [x] **Step 1: Add failing activation tests**

```python
def test_activation_rejects_sixth_deployment_for_five_slots(session): ...
def test_two_sessions_cannot_claim_final_slot(engine): ...
def test_campaign_manager_requires_active_channel_agents(session): ...
def test_cross_tenant_workspace_binding_is_rejected(session): ...
```

- [x] **Step 2: Verify RED**

Run the focused registry test and confirm missing `activate_deployment` behavior.

- [x] **Step 3: Implement transactional services**

Add `validate_deployment`, `activate_deployment`, `suspend_deployment`,
`resume_deployment`, and `retire_deployment`. Activation locks the tenant row,
loads one active entitlement, validates an active SignalLoop installation and
workspace binding, counts slot-consuming states, checks dependencies, then writes
the lifecycle event in the same transaction.

- [x] **Step 4: Verify GREEN including the two-session race**

Run: `uv run --env-file C:/Users/K.Ramachandran/eMailVoice/.env --directory apps/api pytest tests/domain/test_commercial_agent_registry.py -q`

- [x] **Step 5: Commit**

```text
git add apps/api/app/domain/commercial_agents apps/api/tests/domain/test_commercial_agent_registry.py
git commit -m "feat: enforce commercial agent slots"
```

### Task 3: Capacity reservation, finalization, and recovery

**Files:**
- Create: `apps/api/app/domain/commercial_agents/capacity.py`
- Test: `apps/api/tests/domain/test_commercial_agent_capacity.py`

- [x] **Step 1: Add RED tests for reserve, replay, release, unknown, and reconcile**

```python
def test_same_usage_key_is_counted_once(session): ...
def test_pre_effect_failure_releases_reservation(session): ...
def test_unknown_outcome_holds_capacity_until_reconciled(session): ...
def test_capacity_limit_is_atomic_across_sessions(engine): ...
```

- [x] **Step 2: Verify expected failures**

Run the capacity test and confirm the module/API is absent.

- [x] **Step 3: Implement the usage ledger state machine**

Use `RESERVED`, `FINALIZED`, `RELEASED`, and `UNKNOWN` states. Lock the deployment
and billing-day aggregate before reserving. Stable `(deployment, metric,
idempotency_key)` uniqueness makes retry free. Reconciliation requires capability,
receipt/reason, and an audit lifecycle event.

- [x] **Step 4: Run focused tests GREEN**

Run both commercial-agent domain test files.

- [x] **Step 5: Commit**

```text
git add apps/api/app/domain/commercial_agents apps/api/tests/domain/test_commercial_agent_capacity.py
git commit -m "feat: meter agent capacity durably"
```

### Task 4: Tenant-admin registry API

**Files:**
- Create: `apps/api/app/domain/commercial_agents/schemas.py`
- Create: `apps/api/app/api/routes/commercial_agents.py`
- Modify: `apps/api/app/api/main.py`
- Modify: `apps/api/app/domain/tenants/capabilities.py`
- Test: `apps/api/tests/api/routes/test_commercial_agents.py`

- [x] **Step 1: Add RED HTTP tests**

Cover catalog read, deployment create, validate/activate/suspend/resume/retire,
same-key replay, changed-payload conflict, role denial, and cross-tenant IDOR.

- [x] **Step 2: Verify route absence**

Run the route test and confirm 404/missing capability failures.

- [x] **Step 3: Implement strict schemas and routes**

Require `CurrentUser`, tenant header/path scope, `agents.admin.manage`, and
`IdempotencyKeyDep`. Execute mutations through `run_idempotent_mutation` and append
secret-free audit in the same final transaction. Never return credential material.

- [x] **Step 4: Verify route, domain, Ruff, and migration head**

Run focused tests, `uv run --directory apps/api ruff check app/domain/commercial_agents app/api/routes/commercial_agents.py tests/domain/test_commercial_agent_registry.py tests/domain/test_commercial_agent_capacity.py tests/api/routes/test_commercial_agents.py`, and `uv run --directory apps/api alembic heads`.

- [ ] **Step 5: Commit**

```text
git add apps/api/app/api apps/api/app/domain apps/api/tests
git commit -m "feat: expose commercial agent administration"
```
