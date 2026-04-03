# Story 4.4: Apply Fallback Escalation on Booking Failure

Status: backlog

## Story

As a Marketing Ops Admin,
I want automatic fallback escalation when automated booking fails,
so that high-intent contacts are not lost due to scheduling system failures or provider outages.

## Acceptance Criteria

1. **Given** a booking attempt reaches the configured failure threshold (max retries or provider-terminal error)
   **When** fallback logic executes
   **Then** the contact is escalated to the configured fallback path (manual review queue or alternate outreach sequence)
   **And** the escalation reason and required next action are recorded.

2. **Given** an escalated contact is in the manual review queue
   **When** an authorized operator views the queue
   **Then** they can see: contact details, booking failure reason, number of attempts, campaign context, and available next-action options (re-try booking, send manual follow-up, reassign to SE).

3. **Given** an operator takes action on an escalated contact
   **When** they select and confirm an action
   **Then** the chosen action is executed and the contact state updates accordingly
   **And** the action is attributed to the operator with timestamp and reason.

4. **Given** no fallback path is configured for a campaign
   **When** booking failure threshold is hit
   **Then** the contact is moved to `nurture` state with reason code `BOOKING_FAILED_NO_FALLBACK`
   **And** an operational alert is raised so the admin can configure a fallback.

## Tasks / Subtasks

- [ ] **Task 1 – Fallback escalation model** (AC: 1, 2, 4)
  - [ ] Add `escalation_queue` table (contact_id, campaign_id, booking_attempt_id, escalation_reason, escalation_type, status, assigned_to, created_at, resolved_at)
  - [ ] Escalation types: `manual_review`, `alternate_sequence`, `admin_alert`
  - [ ] Status values: `pending`, `resolved`, `dismissed`
  - [ ] Add Alembic migration

- [ ] **Task 2 – Fallback escalation service** (AC: 1, 4)
  - [ ] `apps/api/app/domain/bookings/escalation_service.py`
  - [ ] `escalate_booking_failure(contact_id, campaign_id, booking_attempt_id, reason)` — create escalation record, determine escalation type from campaign config
  - [ ] On no fallback config: shift contact to `nurture`, emit admin alert event
  - [ ] On config found: route to appropriate escalation path

- [ ] **Task 3 – Escalation queue API** (AC: 2, 3)
  - [ ] `GET /workspaces/{wsId}/escalations?status=pending` — requires `operator` or `admin`
  - [ ] `POST /workspaces/{wsId}/escalations/{escalationId}/resolve` — operator takes action (retry, manual-follow-up, reassign)
  - [ ] Include full contact and booking context in GET response

- [ ] **Task 4 – Web UI for escalation management** (AC: 2, 3)
  - [ ] `apps/web/src/features/escalations/EscalationQueuePage.tsx`
  - [ ] List pending escalations with contact summary, failure reason, attempt count
  - [ ] Action panel: select next action, confirm, and submit

- [ ] **Task 5 – Integration with booking service** (AC: 1)
  - [ ] From `booking_service.py` (4.1): on max-retry failure, call `escalation_service.escalate_booking_failure()`
  - [ ] Ensure no infinite loop: escalated contacts cannot re-trigger automatic booking without operator action

- [ ] **Task 6 – Tests** (AC: 1, 2, 3, 4)
  - [ ] Unit test: max-retry failure triggers escalation
  - [ ] Unit test: no fallback config shifts contact to nurture with alert
  - [ ] Unit test: operator resolve marks escalation resolved and transitions contact
  - [ ] Integration test: escalation appears in queue API after booking failure

## Dev Notes

### Architecture Compliance

- Fallback escalation is the last safety net in the booking flow. Do not skip it even in partial implementations.
- Fallback config is per-campaign and set up during campaign creation (add `fallback_escalation_type` field to campaign_channel_strategy if not present).
- The escalation service must be callable from both the booking worker (automatic failure trigger) and the API (manual operator re-escalation).
- Escalated contacts must NOT be automatically re-tried by the execution worker until an operator action explicitly re-queues them.

### Fallback Path Resolution Order

1. Check campaign-level fallback config (`fallback_escalation_type`)
2. If `manual_review` → add to escalation queue
3. If `alternate_sequence` → transition to `nurture` with a different template sequence
4. If no config → transition to `nurture` with `BOOKING_FAILED_NO_FALLBACK` + admin alert

### Suggested File Touch Points

- `apps/api/app/domain/bookings/escalation_service.py` (new)
- `apps/api/app/domain_models.py` (add EscalationQueue)
- `apps/api/app/api/routes/escalations.py` (new)
- `apps/api/app/alembic/versions/*_add_escalation_queue.py` (new)
- `apps/web/src/features/escalations/EscalationQueuePage.tsx` (new)
- `apps/api/tests/domain/test_escalation_service.py` (new)

### References

- [Source: epics.md#Story-4.4-Apply-Fallback-Escalation-on-Booking-Failure]
- [Source: architecture.md#Agent-Consistency-Rules]
- [Source: architecture.md#Error-Semantics-Operator-Taxonomy]

## Dev Agent Record

### Agent Model Used

_To be completed_

### Debug Log References

### Completion Notes List

### File List
