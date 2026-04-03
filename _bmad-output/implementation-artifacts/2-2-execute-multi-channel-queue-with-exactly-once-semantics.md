# Story 2.2: Execute Multi-Channel Queue with Exactly-Once Semantics

Status: in-progress

## Story

As a Marketing Ops Admin,
I want email and call actions to run continuously without duplicates,
so that campaigns can run unattended safely even across retries and restarts.

## Acceptance Criteria

1. **Given** queued outreach jobs with idempotency keys
   **When** a worker processes the same job twice (e.g., due to retry after transient failure)
   **Then** the outreach action is committed at most once
   **And** a duplicate attempt returns the original outcome without re-executing the side effect.

2. **Given** a job dependency is temporarily unavailable (e.g., provider timeout, Redis unavailable)
   **When** the worker detects the failure
   **Then** the action is placed in a deferred state with a scheduled retry timestamp
   **And** processing resumes automatically once the dependency is restored.

3. **Given** the deferred queue has items past their retry timestamp
   **When** the scheduler scans the queue
   **Then** eligible deferred jobs are re-enqueued for processing
   **And** jobs exceeding the maximum retry count are moved to dead-letter with reason.

4. **Given** a campaign is globally or campaign-level paused
   **When** a worker dequeues an action
   **Then** the action is not executed and is re-queued for later without consuming the idempotency window.

5. **Given** workers are processing the queue
   **When** multiple worker instances run concurrently
   **Then** each job is processed by exactly one worker (no race condition)
   **And** horizontal scaling does not produce duplicate committed actions.

## Tasks / Subtasks

- [x] **Task 1 – Action queue and outbox domain models** (AC: 1, 2, 3)
  - [x] `outbox_events` table with `idempotency_key` unique constraint and `status` (pending, committed, failed)
  - [x] `action_queue` table with `status` (queued, deferred, dead_letter), `retry_count`, `scheduled_at`, `last_error`
  - [x] Alembic migration `e5f6a7b8c9d0` (created as part of Epic 2 foundation)

- [x] **Task 2 – Outbox and action queue services** (AC: 1, 2, 3)
  - [x] `outbox_service.py` — publish event with idempotency check; mark committed/failed
  - [x] `action_queue_service.py` — enqueue, defer, dead-letter transitions
  - [x] Deduplication check: look up `idempotency_key` before executing; return cached outcome if previously committed

- [ ] **Task 3 – Worker execution loop** (AC: 1, 2, 4, 5)
  - [ ] `apps/workers/worker_app/outreach/execution_worker.py` — SELECT FOR UPDATE SKIP LOCKED loop
  - [ ] Per-action dispatch to email/call provider adapters (stub ok for this story)
  - [ ] On success: mark outbox_event committed, advance contact state via progression_service
  - [ ] On transient failure: increment retry_count, set scheduled_at = now + backoff, transition to deferred
  - [ ] On max retries exceeded: transition to dead_letter with last_error message
  - [ ] Check pause gate via enforcement_gate before each action execution

- [ ] **Task 4 – Deferred queue scheduler** (AC: 2, 3)
  - [ ] `apps/workers/worker_app/outreach/deferred_scheduler.py` — periodic scan for past-due deferred items
  - [ ] Re-enqueue eligible items; enforce max_retry_count before dead-lettering
  - [ ] Emit dead-letter event to MongoDB event store for audit visibility

- [ ] **Task 5 – Tests** (AC: 1, 2, 3, 4, 5)
  - [ ] Unit test: duplicate idempotency key returns committed outcome without re-execution
  - [ ] Unit test: third attempt on max-retried action moves to dead-letter
  - [ ] Unit test: paused campaign blocks execution but preserves queue entry
  - [ ] Integration test: two concurrent workers on same job — exactly one commits

## Dev Notes

### Architecture Compliance

- Use `SELECT FOR UPDATE SKIP LOCKED` on `action_queue` to ensure exactly-one worker picks each job. Do NOT rely on application-level locking.
- Idempotency strategy: check `outbox_events.idempotency_key` before sending to provider; if already `committed`, return stored outcome.
- Retry backoff: exponential starting at 30s, max 15m. Store `scheduled_at` in UTC.
- Max retries: configurable via environment variable, default 5.
- Dead-letter items must emit event to MongoDB `dead_letter_events` collection for ops visibility (FR33 / Story 5.3 feed).
- Do not expose worker internals directly as HTTP endpoints; use the existing `action_queue` DB table as the coordination surface.
- Pause gate: always call `enforcement_gate.check_paused(campaign_id)` before executing action (already implemented in 1.4).

### Suggested File Touch Points

- `apps/workers/worker_app/outreach/execution_worker.py` (new)
- `apps/workers/worker_app/outreach/deferred_scheduler.py` (new)
- `apps/workers/worker_app/outreach/__init__.py` (new)
- `apps/api/app/domain/outreach/outbox_service.py` (extend)
- `apps/api/app/domain/outreach/action_queue_service.py` (extend)
- `apps/workers/tests/unit/test_execution_worker.py` (new)
- `apps/workers/tests/unit/test_deferred_scheduler.py` (new)

### Key Libraries / Versions

| Library | Version | Purpose |
|---------|---------|---------|
| SQLModel / SQLAlchemy | as in template | Queue coordination via SELECT FOR UPDATE |
| asyncio | stdlib | Async worker loop |
| anyio | stdlib | Thread offload for sync DB ops |

### References

- [Source: epics.md#Story-2.2-Execute-Multi-Channel-Queue-with-Exactly-Once-Semantics]
- [Source: architecture.md#Data-Architecture]
- [Source: architecture.md#API-Communication-Patterns]
- [Source: architecture.md#Agent-Consistency-Rules]

## Dev Agent Record

### Agent Model Used

_To be completed_

### Debug Log References

### Completion Notes List

- Epic 2 foundation (outbox_service, action_queue_service, domain models) created in increment-3 (2026-04-02).
- Worker execution loop and deferred scheduler not yet implemented (Tasks 3-5 pending).

### File List

- `apps/api/app/domain/outreach/outbox_service.py`
- `apps/api/app/domain/outreach/action_queue_service.py`
- `apps/api/app/domain_models.py` (OutboxEvent, ActionQueue)
- `apps/api/app/alembic/versions/e5f6a7b8c9d0_add_epic2_foundation_tables.py`
