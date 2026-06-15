# Provider Side-Effect Safety Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ensure SignalLoop trigger and post-call email side effects persist a durable intent before calling an external provider and do not resend on retry.

**Architecture:** Reuse the existing `OutboxEvent` durable-intent pattern from `apps/api/app/api/routes/calls.py`. Each email-producing action creates or reuses a stable outbox key, commits it before the adapter call, passes the same key as provider idempotency metadata, and marks the outbox event published only after an accepted provider response.

**Tech Stack:** FastAPI domain services, SQLModel, pytest, unittest mocks, provider registry, `OutboxEvent`.

---

## Task 1: Harden Signal Trigger Email Actions

**Files:**
- Modify: `apps/api/app/domain/signals/trigger_service.py`
- Modify: `apps/api/tests/domain/test_trigger_service.py`

- [x] **Step 1: Write failing trigger email intent tests**

Add tests proving `send_demo_email`, `email_sales_team`, and `send_resource_email` create one committed outbox intent, pass a stable `idempotency_key`, mark it published after success, and skip duplicate sends when `process_signal()` is retried for the same signal/action.

- [x] **Step 2: Run trigger tests and verify RED**

Run:

```powershell
$env:PROJECT_NAME='SignalLoop'; $env:POSTGRES_SERVER='localhost'; $env:POSTGRES_USER='postgres'; $env:FIRST_SUPERUSER='admin@example.com'; $env:FIRST_SUPERUSER_PASSWORD='local-dev-password'; uv run pytest tests/domain/test_trigger_service.py -q
```

Expected: new tests fail because trigger email actions currently call the adapter without outbox intent/idempotency.

- [x] **Step 3: Implement trigger outbox intent helper**

Add a focused helper in `trigger_service.py` that builds keys shaped as `signal:{signal_id}:action:{action}`, uses `enqueue_outbox_event()`, treats already-published events as duplicate sends, raises/blocks unpublished duplicates, and calls `mark_outbox_published()` after accepted provider response.

- [x] **Step 4: Run trigger tests and verify GREEN**

Run the same focused trigger test command. Expected: all trigger service tests pass.

## Task 2: Harden API Post-Call Summary Worker

**Files:**
- Modify: `apps/api/app/workers/postcall_worker.py`
- Modify: `apps/api/tests/workers/test_postcall_worker.py`

- [x] **Step 1: Write failing post-call summary intent tests**

Add tests proving `_send_summary()` creates a `postcall:{call_session_id}:summary_email` outbox event before sending, passes that key to the adapter, marks it published after success, and skips duplicate sends when the outbox event is already published.

- [x] **Step 2: Run post-call worker tests and verify RED**

Run:

```powershell
$env:PROJECT_NAME='SignalLoop'; $env:POSTGRES_SERVER='localhost'; $env:POSTGRES_USER='postgres'; $env:FIRST_SUPERUSER='admin@example.com'; $env:FIRST_SUPERUSER_PASSWORD='local-dev-password'; uv run pytest tests/workers/test_postcall_worker.py -q
```

Expected: new tests fail because `_send_summary()` currently sends without a durable intent or adapter idempotency key.

- [x] **Step 3: Implement post-call summary outbox intent**

Reuse `enqueue_outbox_event()` and `mark_outbox_published()` in `postcall_worker.py`. Keep workspace provider resolution via `resolve_email_adapter()`, use runtime team notification resolution, and avoid broad worker rewrites.

- [x] **Step 4: Run post-call worker tests and verify GREEN**

Run the same focused post-call worker command. Expected: all post-call worker tests pass.

## Task 3: Verify Existing Call Action Safety and Status

**Files:**
- Modify: `_bmad-output/implementation-artifacts/signalloop-phase1-open-review-fix-plan-2026-06-07.md`

- [x] **Step 1: Run focused call action regression tests**

Run:

```powershell
$env:PROJECT_NAME='SignalLoop'; $env:POSTGRES_SERVER='localhost'; $env:POSTGRES_USER='postgres'; $env:FIRST_SUPERUSER='admin@example.com'; $env:FIRST_SUPERUSER_PASSWORD='local-dev-password'; uv run pytest tests/unit/test_call_manual_actions.py -q
```

Expected: existing manual call action outbox/idempotency tests pass unchanged.

- [x] **Step 2: Update BMAD open review status**

Record that trigger-service and API post-call summary email sends now use durable outbox intent before provider side effects, while duplicate `apps/workers/worker_app/postcall_worker.py` still needs separate ownership confirmation before patching.

- [x] **Step 3: Run combined focused gate**

Run:

```powershell
$env:PROJECT_NAME='SignalLoop'; $env:POSTGRES_SERVER='localhost'; $env:POSTGRES_USER='postgres'; $env:FIRST_SUPERUSER='admin@example.com'; $env:FIRST_SUPERUSER_PASSWORD='local-dev-password'; uv run pytest tests/domain/test_trigger_service.py tests/workers/test_postcall_worker.py tests/unit/test_call_manual_actions.py -q
git diff --check
```

Expected: focused tests pass and whitespace check is clean.

## Task 4: Prevent Stale Unknown Worker Outcomes From Auto-Retrying

**Files:**
- Modify: `apps/api/app/workers/sequence_worker.py`
- Modify: `apps/api/app/workers/call_worker.py`
- Modify: `apps/api/tests/workers/test_sequence_worker.py`
- Modify: `apps/api/tests/workers/test_call_worker.py`

- [x] **Step 1: Write failing stale unknown outcome tests**

Add tests proving stale `SendRequest.status == pending` rows and stale `CallSession.twilio_status == "initiating"` rows do not call the provider again.

- [x] **Step 2: Run stale outcome tests and verify RED**

Run:

```powershell
$env:PROJECT_NAME='SignalLoop'; $env:POSTGRES_SERVER='localhost'; $env:POSTGRES_USER='postgres'; $env:FIRST_SUPERUSER='admin@example.com'; $env:FIRST_SUPERUSER_PASSWORD='local-dev-password'; uv run pytest tests/workers/test_sequence_worker.py::test_process_single_does_not_resend_stale_pending_unknown_outcome tests/workers/test_call_worker.py::test_initiate_call_does_not_redial_stale_initiating_unknown_outcome -q
```

Expected: both tests fail against the old implementation because stale unknown outcomes are retried.

- [x] **Step 3: Change stale pending/initiating branches to skip provider calls**

Keep retries only for known failed sends/calls. Treat stale pending/initiating rows as unknown provider outcomes that require operator/provider reconciliation rather than automatic resend/redial.

- [x] **Step 4: Run worker tests and verify GREEN**

Run:

```powershell
$env:PROJECT_NAME='SignalLoop'; $env:POSTGRES_SERVER='localhost'; $env:POSTGRES_USER='postgres'; $env:FIRST_SUPERUSER='admin@example.com'; $env:FIRST_SUPERUSER_PASSWORD='local-dev-password'; uv run pytest tests/workers/test_sequence_worker.py tests/workers/test_call_worker.py -q
```

Expected: sequence and call worker suites pass.

## Task 5: Close Review Findings For Failure States And Worker Package

**Files:**
- Modify: `apps/api/app/domain/signals/trigger_service.py`
- Modify: `apps/api/app/workers/postcall_worker.py`
- Modify: `apps/workers/worker_app/postcall_worker.py`
- Modify: `apps/api/tests/domain/test_trigger_service.py`
- Modify: `apps/api/tests/workers/test_postcall_worker.py`
- Create: `apps/workers/tests/unit/test_postcall_worker.py`

- [x] **Step 1: Add RED tests for unpublished intents and rejected providers**

Add tests proving unpublished outbox intents do not get treated as completed duplicates and rejected provider responses do not mark intents published.

- [x] **Step 2: Add RED tests for the active `signalloop-workers` post-call path**

Add tests around `worker_app.postcall_worker._process_session()` because `apps/workers/worker_app/main.py` schedules that worker.

- [x] **Step 3: Fix intent state handling**

Published intent means duplicate completed action and can be skipped. Unpublished intent means unknown/in-progress provider outcome and raises instead of reporting success. Provider rejection leaves the intent unpublished and raises.

- [x] **Step 4: Run review-fix tests**

Run:

```powershell
$env:PROJECT_NAME='SignalLoop'; $env:POSTGRES_SERVER='localhost'; $env:POSTGRES_USER='postgres'; $env:FIRST_SUPERUSER='admin@example.com'; $env:FIRST_SUPERUSER_PASSWORD='local-dev-password'; uv run pytest tests/domain/test_trigger_service.py::test_process_signal_resource_email_does_not_retry_unpublished_intent tests/domain/test_trigger_service.py::test_process_signal_resource_email_rejection_leaves_intent_unpublished tests/workers/test_postcall_worker.py::test_send_summary_rejects_unpublished_intent_without_resend tests/workers/test_postcall_worker.py::test_send_summary_rejection_leaves_intent_unpublished -q
```

Expected: 4 passed.

Run from `apps/workers`:

```powershell
$env:PROJECT_NAME='SignalLoop'; $env:POSTGRES_SERVER='localhost'; $env:POSTGRES_USER='postgres'; $env:FIRST_SUPERUSER='admin@example.com'; $env:FIRST_SUPERUSER_PASSWORD='local-dev-password'; uv run pytest tests/unit/test_postcall_worker.py -q
```

Expected: 3 passed.

## Task 6: Close Scheduled Worker Sequence And Call Retry Gaps

**Files:**
- Modify: `apps/workers/worker_app/sequence_worker.py`
- Modify: `apps/workers/worker_app/call_worker.py`
- Create: `apps/workers/tests/unit/test_side_effect_retry_guards.py`

- [x] **Step 1: Add RED tests for scheduled worker stale outcomes**

Add tests proving `worker_app.sequence_worker._process_single()` does not resend an existing pending `SendRequest` and `worker_app.call_worker._initiate_one()` does not redial an existing initiating `CallSession`.

- [x] **Step 2: Fix scheduled worker retry guards**

Treat any existing pending send or initiating call session as an unknown provider outcome that must not be retried automatically.

- [x] **Step 3: Run scheduled worker unit tests**

Run from `apps/workers`:

```powershell
$env:PROJECT_NAME='SignalLoop'; $env:POSTGRES_SERVER='localhost'; $env:POSTGRES_USER='postgres'; $env:FIRST_SUPERUSER='admin@example.com'; $env:FIRST_SUPERUSER_PASSWORD='local-dev-password'; uv run pytest tests/unit -q
```

Expected: 8 passed.
