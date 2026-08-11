# Enterprise Phase 1 Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the enterprise-grade SignalLoop control and execution plane while preserving eCRM and RevenueOS as independent product boundaries.

**Architecture:** SignalLoop is the source of tenant, policy, consent, provider, and operational state. It persists immutable projection intents, executes them through restart-safe workers, and records retry, acknowledgement, dead-letter, reconciliation, and audit state. eCRM and RevenueOS receive authenticated projections through stable HTTP seams; their local authorization and application data remain independent.

**Tech Stack:** FastAPI, SQLModel, PostgreSQL, Alembic, Dramatiq workers, HTTPX, cryptographic workload assertions, pytest, Playwright.

---

## File map

- `apps/api/app/domain/projections/`: persisted projection intents, dispatcher, retry state, reconciliation and audit events.
- `apps/workers/worker_app/`: scheduled projection processing and recovery jobs.
- `apps/api/app/domain/revenue_intelligence/`: durable RevenueOS interventions and policy decisions.
- `apps/api/app/infrastructure/providers/`: credential-backed email, SMS, voice and chat provider adapters.
- `apps/api/tests/` and `apps/workers/tests/`: failure, replay, isolation, recovery and policy tests.
- `C:\My Workspace\eCRM`: consumer implementation only; this repository never changes its local tenant model.

### Task 1: Persist idempotent projection intents

**Files:** `apps/api/app/domain/tenants/models.py`, `apps/api/app/models.py`, `apps/api/app/domain/projections/outbox.py`, `apps/api/app/alembic/versions/`, `apps/api/tests/unit/test_projection_outbox.py`

- [ ] Write failing tests proving canonical payload idempotency and conflicting same-version rejection.
- [ ] Add `SuiteProjectionOutbox` with immutable payload digest, attempt state, next attempt, acknowledgement receipt and dead-letter reason; enforce installation/kind/version uniqueness.
- [ ] Add an enqueue service that verifies the installation belongs to the tenant and never overwrites a version.
- [ ] Run focused tests, lint, Alembic head rehearsal, then commit.

### Task 2: Deliver, retry, dead-letter and reconcile projections

**Files:** `apps/api/app/domain/projections/dispatcher.py`, `apps/api/app/domain/projections/reconciliation.py`, `apps/workers/worker_app/projection_worker.py`, `apps/workers/worker_app/main.py`, respective API/worker tests.

- [ ] Write failing tests for signed delivery, transient retry, permanent dead-letter, duplicate receipt and restart recovery.
- [ ] Claim pending outbox rows transactionally; sign canonical envelopes with the existing short-lived workload assertion; use bounded exponential backoff and immutable attempt audit data.
- [ ] Add a worker schedule plus reconciliation that compares product status receipts and re-enqueues only missing or newer versions.
- [ ] Require product endpoint/key configuration before live delivery; otherwise retain the intent as a visible configuration-blocked operational state.
- [ ] Run API and worker tests, lint and migration tests, then commit.

### Task 3: Make RevenueOS interventions durable and governed

**Files:** `apps/api/app/domain/revenue_intelligence/models.py`, `service.py`, `persistence.py`, `apps/api/app/api/routes/`, migrations and tests.

- [ ] Write failure tests for duplicate idempotency keys, failed dispatch, denied consent/policy and restart recovery.
- [ ] Persist intervention proposals, policy evidence, dispatch attempts, outcomes and retry/dead-letter state by tenant.
- [ ] Route all execution through the policy/consent decision before provider dispatch; audit both allowed and denied outcomes.
- [ ] Expose tenant-scoped operational status and retry controls with capability checks.
- [ ] Run focused tests and commit.

### Task 4: Harden provider execution and consent controls

**Files:** provider registry/adapters, `domain/policies`, `domain/sequences`, queue worker tests.

- [ ] Write failing tests for missing encrypted credentials, provider rejection, consent revocation after queueing, suppression, rate ceiling and callback idempotency.
- [ ] Use configured encrypted credentials and per-workspace provider selections; make fake adapters explicit local/test-only behavior rather than a production fallback.
- [ ] Re-evaluate consent, suppression, quiet-hours, caps and policy at dispatch time, emit an audit outcome, and dead-letter only recoverable provider failures according to policy.
- [ ] Test provider callback verification and exactly-once event ingestion.
- [ ] Run focused API and worker tests and commit.

### Task 5: Complete cross-product operations and isolation gates

**Files:** support access context, action/outbox services, shared-record reconciliation, admin routes and operational tests.

- [ ] Propagate support-grant context across all data-plane reads, queue writes, workers, shared-record paths and audits; uniform deny on mismatch/expiry/revocation.
- [ ] Add operational health views for projection lag, provider credentials, retries/dead letters, policy denials and reconciliation drift.
- [ ] Verify eCRM and RevenueOS are addressed only over projection seams; do not add direct database access or browser-selected tenant headers.
- [ ] Run the broad API suite, worker suite, web build and targeted browser tests; document only external receiver/credential configuration that cannot be locally exercised.

