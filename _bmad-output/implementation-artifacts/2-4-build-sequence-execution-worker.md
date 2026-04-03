# Story 2.4: Build Sequence Execution Worker

Status: ready-for-dev

## Story

As a system operator,
I want an automated worker that sends scheduled emails without manual intervention,
so that email sequences execute reliably on their configured schedules.

## Acceptance Criteria

1. **Given** the worker is running **When** it polls every 60 seconds **Then** it queries ContactSequenceState where status=ACTIVE and next_send_at <= NOW
2. **Given** due contacts are found **When** the worker processes them **Then** it loads the step template, merges contact fields, creates a SendRequest, and calls the SendGrid adapter
3. **Given** an email is sent successfully **When** the worker updates state **Then** current_step is advanced, next_send_at is set to now + delay_days for the next step
4. **Given** a contact is on the final step **When** the email sends successfully **Then** ContactSequenceState.status is set to COMPLETED
5. **Given** a send fails **When** the worker retries **Then** it retries with exponential backoff up to 5 attempts, then marks FAILED
6. **Given** daily email cap is configured **When** the cap is reached **Then** no more emails are sent until the next day
7. **Given** quiet hours are configured **When** the current time falls in quiet hours **Then** emails are deferred to the next available window
8. **Given** any email is sent **When** the audit system records it **Then** an audit event is created with send details

## Tasks / Subtasks

- [ ] Task 1: Create apps/workers/worker_app/sequence_worker.py (AC: 1,2,3,4)
  - [ ] Main loop: poll every 60s
  - [ ] Query: SELECT * FROM contact_sequence_state WHERE status='ACTIVE' AND next_send_at <= NOW() ORDER BY next_send_at LIMIT 50
  - [ ] Template merge: replace {{token}} with contact field values
  - [ ] Create SendRequest with idempotency_key = f"{contact_id}:{sequence_id}:{step_order}"
  - [ ] Call SendGrid adapter
  - [ ] On success: advance step or complete
- [ ] Task 2: Implement retry logic with exponential backoff (AC: 5)
  - [ ] Track retry_count on SendRequest
  - [ ] Backoff: 60s, 300s, 900s, 3600s, 7200s
  - [ ] After 5 failures: mark SendRequest FAILED, log error
- [ ] Task 3: Implement daily cap enforcement (AC: 6)
  - [ ] Query today's send count: SELECT COUNT(*) FROM send_request WHERE DATE(created_at) = TODAY AND status != 'FAILED'
  - [ ] Compare against governance daily_cap setting
  - [ ] Skip sending if cap reached, log warning
- [ ] Task 4: Implement quiet hours check (AC: 7)
  - [ ] Check current time against configured quiet hours (e.g., 9pm-8am recipient timezone or UTC fallback)
  - [ ] If in quiet hours: skip, next_send_at stays unchanged (will be picked up next poll after quiet hours)
- [ ] Task 5: Add audit logging for every send (AC: 8)
- [ ] Task 6: Add worker entry point to docker compose and worker Dockerfile (AC: 1)
- [ ] Task 7: Write unit tests for template merging, cap check, quiet hours logic (AC: 2,6,7)
- [ ] Task 8: Write integration test for full send cycle (mock SendGrid) (AC: 1,2,3,4)

## Dev Notes

- Worker runs as a separate process (not in the API server)
- Use SELECT ... FOR UPDATE SKIP LOCKED to prevent parallel workers from double-processing
- Idempotency key prevents duplicate sends even on crash/restart
- Batch size of 50 contacts per poll to avoid long transactions

### References
- [Source: architecture.md#Section-6 — sequence_worker process]
- [Source: architecture.md#Section-5 — Email Sequence Engine 6-step flow]
- [Source: prd.md#FR17 — automated sending on schedule]
- [Source: prd.md#FR12 — daily send caps]
- [Source: prd.md#FR13 — quiet hours]

## Dev Agent Record
### Agent Model Used
### Debug Log References
### Completion Notes List
### File List
