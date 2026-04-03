# Story 2.4: Synchronize Consent and Suppression Across Channels

Status: in-progress

## Story

As a compliance-conscious operator,
I want consent and suppression status synchronized across all connected provider channels,
so that prohibited contacts are never actioned regardless of which channel processes them.

## Acceptance Criteria

1. **Given** a contact's suppression or consent status changes (manual override, provider callback, or regulatory import)
   **When** the synchronization process runs
   **Then** canonical status is updated in the `contacts` table and propagated to all active channel boundaries
   **And** the update is recorded with actor attribution and timestamp.

2. **Given** a worker attempts to action a contact
   **When** the consent/suppression check runs before action execution
   **Then** contacts with any blocking suppression status are skipped
   **And** the skipped action records a visible policy reason code in the contact timeline.

3. **Given** a suppression list import is submitted
   **When** the import is processed
   **Then** all matching contacts in any workspace are marked suppressed atomically
   **And** duplicate suppression of already-suppressed contacts is idempotent (no error, no duplicate record).

4. **Given** a provider reverses a suppression (e.g., re-subscribe via email)
   **When** the re-subscribe event is received and validated
   **Then** the contact's channel-specific suppression is lifted with audit record
   **And** global suppression entries (manual DNC) are NOT automatically lifted by provider events.

## Tasks / Subtasks

- [x] **Task 1 – Consent sync service** (AC: 1, 2)
  - [x] `consent_sync_service.py` — sync consent status across channels for a given contact
  - [x] Integration with `ContactProgression` suppression flag checking

- [ ] **Task 2 – Suppression management API** (AC: 1, 3, 4)
  - [ ] `POST /suppressions/import` — bulk suppression import (CSV or JSON list of emails/phones)
  - [ ] `POST /suppressions/{contactId}` — manual DNC add with reason and actor attribution
  - [ ] `DELETE /suppressions/{contactId}/{channel}` — lift channel-specific (non-global) suppression
  - [ ] Enforce `admin` role for DNC add/remove endpoints
  - [ ] Idempotency: duplicate suppression insert is a no-op

- [ ] **Task 3 – Pre-action consent gate in execution worker** (AC: 2)
  - [ ] Before each action dispatch, call `consent_sync_service.is_actionable(contact_id, channel)`
  - [ ] If not actionable: skip with `reason_code=SUPPRESSION_BLOCK` or `reason_code=CONSENT_WITHDRAWN`
  - [ ] Write skipped-action record to `contact_state_history` and MongoDB timeline

- [ ] **Task 4 – Provider re-subscribe handler** (AC: 4)
  - [ ] Extend webhook normalization pipeline to handle `channel_resubscribe` event type
  - [ ] On receipt: lift per-channel suppression only; validate global DNC is not overridden
  - [ ] Write audit record with `event_source=provider` attribution

- [ ] **Task 5 – Tests** (AC: 1, 2, 3, 4)
  - [ ] Unit test: suppression check blocks contact before action
  - [ ] Unit test: duplicate import is idempotent (no duplicate rows)
  - [ ] Unit test: provider re-subscribe does not lift global DNC
  - [ ] Integration test: suppression import marks contacts and worker skips them with reason code

## Dev Notes

### Architecture Compliance

- Canonical suppression status lives in PostgreSQL `contacts.suppression_status`. Channel-specific overrides stored in a `contact_channel_suppression` table (add if not already present).
- Do NOT allow provider callbacks to automatically clear global/manual DNC entries. Only admin role actions can modify global DNC.
- All suppression/consent changes must be audit-logged with actor, timestamp, source (manual/provider/import), and correlation_id.
- The consent gate in the worker must be a SYNCHRONOUS blocking check before any provider call. Do not allow optimistic out-of-order execution.

### Suppression Status Taxonomy

| Status | Lifted by provider event? | Lifted by admin? |
|--------|--------------------------|------------------|
| `global_dnc` | No | Yes (admin only) |
| `email_unsubscribed` | Yes (re-subscribe event) | Yes |
| `sms_opt_out` | Yes | Yes |
| `regulatory_block` | No | Yes (admin only) |

### Suggested File Touch Points

- `apps/api/app/domain/contacts/consent_sync_service.py` (extend existing)
- `apps/api/app/api/routes/suppressions.py` (new)
- `apps/workers/worker_app/outreach/execution_worker.py` (add consent gate)
- `apps/api/app/api/routes/webhooks.py` (add re-subscribe handler)
- `apps/api/tests/api/routes/test_suppressions.py` (new)
- `apps/workers/tests/unit/test_consent_gate.py` (new)

### References

- [Source: epics.md#Story-2.4-Synchronize-Consent-and-Suppression-Across-Channels]
- [Source: architecture.md#Data-Architecture]
- [Source: architecture.md#Agent-Consistency-Rules]
- [Source: architecture.md#Error-Semantics-Operator-Taxonomy]

## Dev Agent Record

### Agent Model Used

_To be completed_

### Debug Log References

### Completion Notes List

- `consent_sync_service.py` created in increment-3 (2026-04-02) as part of Epic 2 continuation batch.
- Suppression API, pre-action consent gate, and re-subscribe handler (Tasks 2-4) pending.

### File List

- `apps/api/app/domain/contacts/consent_sync_service.py`
