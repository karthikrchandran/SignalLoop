# Story 4.1: Trigger Booking Workflow for Qualified Contacts

Status: backlog

## Story

As a Marketing Ops Admin,
I want qualified contacts to automatically enter a booking workflow once routed to the booking state,
so that demo conversion is accelerated without manual intervention.

## Acceptance Criteria

1. **Given** a contact is routed to `booking` state by the routing engine
   **When** booking orchestration starts
   **Then** the scheduling bridge adapter is invoked with required contact and context payload (contact details, campaign context, available time slots source)
   **And** a booking attempt record is created with `status=pending`.

2. **Given** the scheduling bridge call is made
   **When** the invocation succeeds
   **Then** the booking attempt record updates to `status=awaiting_confirmation`
   **And** a contact timeline entry is added: "Booking initiated — awaiting confirmation".

3. **Given** the scheduling bridge call fails (timeout, provider error)
   **When** the failure is handled
   **Then** the booking attempt is marked `status=failed` with error reason
   **And** fallback escalation (Story 4.4) is triggered if retry limit is reached.

4. **Given** a booking attempt is already pending for a contact-campaign pair
   **When** a duplicate booking trigger arrives
   **Then** the duplicate is ignored (idempotent) and the existing attempt record is returned.

## Tasks / Subtasks

- [ ] **Task 1 – Booking domain models and migration** (AC: 1, 2, 4)
  - [ ] Add `booking_attempts` table (contact_id, campaign_id, attempt_id, status, provider_ref, initiated_at, context_payload_json, error_reason, retry_count)
  - [ ] Unique constraint: `(contact_id, campaign_id)` may have multiple attempts; track by attempt_id
  - [ ] Add Alembic migration

- [ ] **Task 2 – Booking orchestration service** (AC: 1, 2, 3)
  - [ ] `apps/api/app/domain/bookings/booking_service.py`
  - [ ] `initiate_booking(contact_id, campaign_id, context)` — idempotency check, invoke scheduling adapter, create attempt record
  - [ ] Handle adapter success/failure; update attempt status accordingly
  - [ ] Trigger `contact.state_transition("booking_initiated")` on success

- [ ] **Task 3 – Scheduling provider adapter** (AC: 1)
  - [ ] Extend provider adapter registry with `SchedulingProviderAdapter`
  - [ ] Stub implementation that simulates async booking initiation
  - [ ] Emit normalized `ProviderEvent` on callback receipt

- [ ] **Task 4 – Integration with progression state machine** (AC: 2)
  - [ ] On booking initiation success: call `progression_service.transition_contact_state` to `booking_initiated`
  - [ ] Write timeline entry to MongoDB contact events collection

- [ ] **Task 5 – Tests** (AC: 1, 2, 3, 4)
  - [ ] Unit test: successful initiation creates pending attempt
  - [ ] Unit test: duplicate trigger returns existing attempt (idempotent)
  - [ ] Unit test: provider failure marks attempt failed and triggers escalation check
  - [ ] Integration test: routing → booking trigger → attempt created → timeline entry visible

## Dev Notes

### Architecture Compliance

- Booking orchestration belongs to the `bookings` domain. Do NOT put scheduling logic in the routing engine or worker loop directly.
- Scheduling provider callbacks come via the webhook pipeline (2.3). The booking service must handle both push (webhook) and pull (poll) completion patterns.
- Context payload sent to scheduling bridge: `{contact: {email, firstName, company, timezone}, campaign_id, booking_purpose, available_slots_url}`.
- All booking state changes must produce timeline entries in MongoDB and state transitions via `progression_service`.

### Booking States

| State | Meaning |
|-------|---------|
| `pending` | Initiation sent, waiting for provider ACK |
| `awaiting_confirmation` | Provider accepted, waiting for contact to confirm slot |
| `confirmed` | Booking confirmed — see Story 4.2 |
| `failed` | Provider error or rejected |
| `escalated` | Routed to fallback — see Story 4.4 |

### Suggested File Touch Points

- `apps/api/app/domain/bookings/booking_service.py` (new)
- `apps/api/app/domain_models.py` (add BookingAttempt)
- `apps/api/app/domain/providers/scheduling_adapter.py` (extend from 2.3)
- `apps/api/app/alembic/versions/*_add_booking_tables.py` (new)
- `apps/api/tests/domain/test_booking_service.py` (new)

### References

- [Source: epics.md#Story-4.1-Trigger-Booking-Workflow-for-Qualified-Contacts]
- [Source: architecture.md#Data-Architecture]
- [Source: architecture.md#Agent-Consistency-Rules]

## Dev Agent Record

### Agent Model Used

_To be completed_

### Debug Log References

### Completion Notes List

### File List
