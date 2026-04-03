# Story 2.5: Implement Reply Detection and Signal Branching

Status: ready-for-dev

## Story

As a marketing admin,
I want the system to automatically detect positive email replies and pause sequences,
so that interested prospects don't receive additional automated emails after engaging.

## Acceptance Criteria

1. **Given** a REPLIED event from SendGrid **When** the reply content is analyzed **Then** keyword-based positive signal detection runs against the reply text
2. **Given** positive keywords are detected ("interested", "yes", "let's", "schedule", "demo", "call me") **When** the signal is classified **Then** ContactSequenceState.status is set to PAUSED and signal_type = "email_positive_reply" and signal_detected_at is set
3. **Given** a hard BOUNCED event **When** it is processed **Then** ContactSequenceState.status is set to STOPPED with signal_type = "hard_bounce"
4. **Given** an UNSUBSCRIBED event **When** it is processed **Then** ContactSequenceState.status is STOPPED, signal_type = "unsubscribed", and the contact email is added to the suppression list
5. **Given** a positive signal is detected **When** downstream systems are notified **Then** a signal-detected event is emitted (stored in DB) for Epic 4 automated followup
6. **Given** negative or neutral reply content **When** the signal is classified **Then** the sequence continues (status stays ACTIVE)

## Tasks / Subtasks

- [ ] Task 1: Create apps/api/app/domain/signals/ module (AC: all)
  - [ ] signal_detector.py with detect_email_signal(reply_text) → SignalResult
  - [ ] SignalResult: signal_type (str), confidence (float), matched_keywords (list)
- [ ] Task 2: Implement keyword-based positive signal detection (AC: 1,2)
  - [ ] Positive keywords list: ["interested", "yes", "let's talk", "schedule", "demo", "call me", "sounds good", "tell me more", "set up a time"]
  - [ ] Case-insensitive matching
  - [ ] Return confidence based on keyword count (1 keyword = 0.6, 2+ = 0.9)
- [ ] Task 3: Integrate signal detection into webhook event processing (AC: 1,2,3,4)
  - [ ] On REPLIED: run signal detector, if positive → pause sequence
  - [ ] On BOUNCED (hard): stop sequence immediately
  - [ ] On UNSUBSCRIBED: stop sequence, add to suppression
- [ ] Task 4: Create signal event record for downstream automation (AC: 5)
  - [ ] SignalEvent model: id, contact_id, campaign_id, channel (email/voice), signal_type, confidence, source_event_id, created_at
  - [ ] Alembic migration for signal_events table
- [ ] Task 5: Implement suppression list check in sequence worker (AC: 4)
  - [ ] Before sending any email, check suppression list
  - [ ] If suppressed, skip and set STOPPED
- [ ] Task 6: Write unit tests for signal detection (AC: 1,2,6)
  - [ ] Test positive detection with various phrasings
  - [ ] Test neutral/negative content passes through
- [ ] Task 7: Write integration tests for signal → pause/stop flow (AC: 2,3,4)

## Dev Notes

- Keep signal detection simple — keyword-based is sufficient for MVP
- Do NOT use LLM for email signal detection (save LLM for voice only)
- Signal events are the bridge to Epic 4 automated followup triggers

### References
- [Source: architecture.md#Section-5 — step 6 reply detection]
- [Source: prd.md#FR19 — detect positive intent signals]
- [Source: prd.md#FR20 — classify signal confidence]
- [Source: prd.md#FR-S1 — positive email triggers followup call]

## Dev Agent Record
### Agent Model Used
### Debug Log References
### Completion Notes List
### File List
