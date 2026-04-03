# Story 4.2: Confirm Booking and Update Progression State

Status: backlog

## Story

As a Marketing Ops Admin,
I want confirmed or failed booking outcomes reflected immediately in the contact's state,
so that downstream actions (handoff, re-nurture) are accurate and timely.

## Acceptance Criteria

1. **Given** a booking confirmation callback is received from the scheduling provider
   **When** the outcome is processed
   **Then** the booking attempt status is updated to `confirmed` with the confirmed time and provider booking reference
   **And** the contact progression state transitions to `confirmed` with reason code `BOOKING_CONFIRMED`.

2. **Given** a booking cancellation or no-show callback is received
   **When** the outcome is processed
   **Then** the booking attempt is marked `failed` or `cancelled` with reason
   **And** the contact is returned to `nurture` state for continued outreach (unless at max-retry policy threshold).

3. **Given** booking outcome processing occurs
   **When** the state change is committed
   **Then** a timeline entry is written within the NFR20 SLA (60s from callback receipt)
   **And** the entry includes: booking time, provider reference, outcome, and attribution.

4. **Given** a duplicate booking confirmation arrives (provider callback replay)
   **When** the system processes it
   **Then** the existing confirmed booking record is returned unchanged (idempotent)
   **And** no duplicate state transition is created.

## Tasks / Subtasks

- [ ] **Task 1 – Booking confirmation service** (AC: 1, 2, 4)
  - [ ] `apps/api/app/domain/bookings/booking_confirmation_service.py`
  - [ ] `process_booking_outcome(attempt_id, outcome, provider_ref, booked_at)` callable from webhook handler
  - [ ] Idempotency: if attempt already confirmed, return existing record
  - [ ] On confirmed: transition contact state, write MongoDB timeline event
  - [ ] On cancelled/no-show: transition contact to nurture, write timeline event

- [ ] **Task 2 – Webhook handler extension** (AC: 1, 2, 3)
  - [ ] Extend `apps/api/app/api/routes/webhooks.py` to handle `booking_confirmed`, `booking_cancelled`, `booking_no_show` event types
  - [ ] Call `booking_confirmation_service.process_booking_outcome()` with normalized event data
  - [ ] Return 200 immediately; process asynchronously via outbox if latency risk exists

- [ ] **Task 3 – Timeline SLA enforcement** (AC: 3)
  - [ ] Capture `timeline_entry_at` timestamp on MongoDB write
  - [ ] If `timeline_entry_at - received_at > 60s`: emit `timeline_sla_breach` operational event (NFR20)

- [ ] **Task 4 – Tests** (AC: 1, 2, 3, 4)
  - [ ] Unit test: confirmed outcome transitions contact to confirmed state
  - [ ] Unit test: cancelled outcome returns contact to nurture
  - [ ] Unit test: duplicate confirmation is idempotent
  - [ ] Integration test: booking webhook → confirmation service → timeline entry within SLA

## Dev Notes

### Architecture Compliance

- Booking outcome processing is in the `bookings` domain; webhook parsing belongs in the API layer. Keep them separate.
- State transitions must go through `progression_service` — do not write directly to `contact_progression` from the booking service.
- The handoff packet (Story 4.3) is generated after `status=confirmed`; ensure the confirmed booking record contains all required fields (booked_at, provider_ref, contact_id, campaign_id) that 4.3 will consume.
- NFR20: Calendar bridge updates must propagate to timelines within 60 seconds for p95.

### Suggested File Touch Points

- `apps/api/app/domain/bookings/booking_confirmation_service.py` (new)
- `apps/api/app/api/routes/webhooks.py` (extend)
- `apps/api/app/domain/contacts/progression_service.py` (called for state transitions)
- `apps/api/app/infrastructure/db/mongodb/mongo_schema.py` (booking timeline event)
- `apps/api/tests/domain/test_booking_confirmation_service.py` (new)

### References

- [Source: epics.md#Story-4.2-Confirm-Booking-and-Update-Progression-State]
- [Source: architecture.md#API-Communication-Patterns]
- NFR20: Calendar bridge updates propagate to timelines within 60 seconds for p95.

## Dev Agent Record

### Agent Model Used

_To be completed_

### Debug Log References

### Completion Notes List

### File List
