# Calendar Scheduler Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade scheduling intent into an independently metered, provider-neutral autonomous booking workflow with confirmation and reconciliation.

**Architecture:** Evolve existing scheduling requests into a richer workflow without breaking timeline/Calendly behavior. Persist meeting types, bindings, offer versions, confirmations, immutable provider commands, and receipts. A bounded worker owns availability, confirmation, booking, retry, DLQ, and unknown-outcome reconciliation.

**Tech Stack:** FastAPI, SQLModel/Alembic, APScheduler workers, existing Calendly webhook seam, pytest.

---

### Task 1: Workflow, meeting type, binding, offer, command, and receipt models

**Files:**
- Modify: `apps/api/app/domain/scheduling/models.py`
- Modify: `apps/api/app/domain/scheduling/schemas.py`
- Create: `apps/api/app/alembic/versions/p1_calendar_scheduler_agent_20260816.py`
- Test: `apps/api/tests/domain/test_calendar_scheduler_models.py`

- [x] Add RED tests for tenant/workspace composite ownership, immutable offer/
  receipt identity, valid transitions, and migration of current requests.
- [x] Implement models and a forward/backfill-safe migration preserving existing
  scheduling request IDs, statuses, timeline events, and Calendly receipts.
- [x] Run model, existing scheduling, and migration tests GREEN.
- [x] Commit with `feat: model autonomous calendar workflows`.

### Task 2: Time, availability, and confirmation engine

**Files:**
- Create: `apps/api/app/domain/scheduling/availability.py`
- Create: `apps/api/app/domain/scheduling/providers.py`
- Modify: `apps/api/app/domain/scheduling/service.py`
- Test: `apps/api/tests/domain/test_calendar_availability.py`

- [x] Add RED tests for IANA timezone validation, DST boundaries, working hours,
  holidays, buffers, notice, expiry, conflicts, and one confirmation per offer.
- [x] Implement provider-neutral free/busy and deterministic slot calculation.
- [x] Persist offer version/digest and explicit confirmation evidence.
- [x] Run scheduling domain tests GREEN.
- [x] Commit with `feat: calculate and confirm meeting slots`.

### Task 3: Durable booking worker and Calendly adapter

**Files:**
- Create: `apps/api/app/domain/scheduling/worker.py`
- Create: `apps/api/app/domain/scheduling/calendly_adapter.py`
- Modify: `apps/workers/worker_app/main.py`
- Test: `apps/api/tests/workers/test_calendar_scheduler_worker.py`

- [x] Add RED tests for atomic claims, final availability recheck, stable provider
  key, accepted-then-timeout unknown outcome, lease recovery, DLQ, and kill switch.
- [x] Implement command-envelope dispatch and receipt persistence. Never retry an
  ambiguous invocation until provider lookup proves no event was created.
- [x] Run worker plus existing webhook replay tests GREEN.
- [x] Commit with `feat: book meetings with durable recovery`.

### Task 4: APIs, webhook integration, and reconciliation

**Files:**
- Modify: `apps/api/app/api/routes/scheduling.py`
- Create: `apps/api/app/domain/scheduling/reconciliation.py`
- Test: `apps/api/tests/api/routes/test_calendar_scheduler.py`
- Modify: `apps/api/tests/api/routes/test_scheduling_webhook.py`

- [ ] Add RED tests for meeting types/bindings, intent, availability, confirmation,
  reschedule/cancel, role/IDOR, idempotency, webhook tenant binding, and reconcile.
- [ ] Implement strict APIs, durable HTTP idempotency, capability checks, audit,
  monotonic webhook application, and receipt-backed operator reconciliation.
- [ ] Confirm paid Email/Voice dependency is required only for channel messages,
  not provider-native invitations.
- [ ] Run all scheduling tests, Ruff, and one-head Alembic check GREEN.
- [ ] Commit with `feat: expose autonomous calendar scheduling`.
