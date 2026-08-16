# Lead Preparation Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert existing prospect scoring and briefs into a versioned, explainable, autonomous, recoverable Lead Preparation Agent.

**Architecture:** Preserve deterministic scoring and existing prospecting APIs while extracting rules into published policies. Durable jobs collect tenant-scoped evidence, create immutable score/package versions, reserve registry capacity, and route references to paid downstream agents. A bounded worker owns leases, retries, DLQ, and reconciliation.

**Tech Stack:** FastAPI, SQLModel, Alembic, existing prospecting/shared-record services, worker scheduler, pytest.

---

### Task 1: Versioned score policy and immutable outputs

**Files:**
- Create: `apps/api/app/domain/lead_preparation/models.py`
- Create: `apps/api/app/domain/lead_preparation/scoring.py`
- Modify: `apps/api/app/models.py`
- Create: `apps/api/app/alembic/versions/p1_lead_preparation_agent_20260816.py`
- Test: `apps/api/tests/domain/test_lead_preparation_scoring.py`

- [x] Write RED tests proving the migrated default policy reproduces current
  scores and records feature contributions, exclusions, freshness, and policy
  version.
- [x] Run the focused test and observe missing-module failure.
- [x] Implement `LeadScoringPolicy`, `LeadScoreVersion`, `LeadEvidenceItem`, and
  `LeadPreparationPackage`; make published policies immutable by service contract.
- [x] Run scoring and migration-chain tests GREEN.
- [x] Commit with `feat: version lead preparation scores`.

### Task 2: Durable preparation job and autonomous loop

**Files:**
- Create: `apps/api/app/domain/lead_preparation/service.py`
- Create: `apps/api/app/domain/lead_preparation/worker.py`
- Modify: `apps/workers/worker_app/main.py`
- Test: `apps/api/tests/workers/test_lead_preparation_worker.py`

- [x] Add RED tests for event idempotency, atomic claim, stale lease recovery,
  evidence failure retry, terminal suppression, capacity reservation, and DLQ.
- [x] Run and confirm the absent worker/claim behavior.
- [x] Implement `PENDING` through `ROUTED` transitions with conditional claims,
  bounded backoff, no invented evidence, and atomic package/usage/audit finalization.
- [x] Run worker and scoring tests GREEN.
- [x] Commit with `feat: run autonomous lead preparation`.

### Task 3: Policy administration and package routing APIs

**Files:**
- Create: `apps/api/app/domain/lead_preparation/schemas.py`
- Create: `apps/api/app/api/routes/lead_preparation.py`
- Modify: `apps/api/app/api/main.py`
- Test: `apps/api/tests/api/routes/test_lead_preparation.py`

- [ ] Add RED tests for policy dry-run/publish, job creation, package history,
  approve/reject/route, cross-workspace denial, idempotency, and dependency denial.
- [ ] Implement strict tenant/workspace APIs using durable idempotency and audit.
- [ ] Ensure routing to Email/Voice requires an active paid registry dependency and
  passes consent/suppression again.
- [ ] Run API/domain/worker tests and Ruff GREEN.
- [ ] Commit with `feat: administer lead preparation agents`.

### Task 4: Recovery and outcome evaluation

**Files:**
- Create: `apps/api/app/domain/lead_preparation/reconciliation.py`
- Test: `apps/api/tests/domain/test_lead_preparation_reconciliation.py`

- [ ] Add RED tests for unknown source outcome, missing terminal package, usage
  mismatch, audited DLQ replay, and outcome ingestion without self-modifying policy.
- [ ] Implement reconciliation reports and authorized repair decisions.
- [ ] Run the complete lead preparation gate and migration heads check.
- [ ] Commit with `fix: reconcile lead preparation outcomes`.
