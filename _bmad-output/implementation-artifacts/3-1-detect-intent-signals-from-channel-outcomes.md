# Story 3.1: Detect Intent Signals from Channel Outcomes

Status: backlog

## Story

As a Marketing Ops Admin,
I want intent signals detected automatically from email replies and call outcomes,
so that qualified contacts can be acted on quickly without manual review.

## Acceptance Criteria

1. **Given** an inbound email response or call outcome event arrives via the provider webhook
   **When** the signal detection process evaluates the event
   **Then** a `SignalArtifact` is produced and stored for qualifying events (reply with content, positive call sentiment, transcript keyword match)
   **And** non-qualifying events (bounces, auto-replies, no-answer with no voicemail) are stored log-only without triggering routing.

2. **Given** a signal artifact is created
   **When** signal metadata is persisted
   **Then** it includes: contact_id, campaign_id, channel, signal_type, raw_content_ref, detected_at, confidence_tier (populated in 3.2), correlation_id.

3. **Given** multiple signals arrive for the same contact in the same cycle
   **When** signals are processed
   **Then** each signal is evaluated independently and stored separately
   **And** deduplication prevents the same raw event from generating two signal records.

## Tasks / Subtasks

- [ ] **Task 1 – Signal domain model and migration** (AC: 1, 2)
  - [ ] Add `signal_artifacts` table (contact_id, campaign_id, signal_id, channel, signal_type, raw_content_ref, confidence_tier, detected_at, correlation_id, triggered_routing)
  - [ ] Add Alembic migration chained after `e5f6a7b8c9d0`
  - [ ] Unique constraint on `(raw_event_id, channel)` to prevent duplicate signal creation

- [ ] **Task 2 – Signal detection service** (AC: 1, 2)
  - [ ] `apps/api/app/domain/signals/signal_detection_service.py`
  - [ ] Email signal detection: detect reply with user-authored content (exclude auto-reply headers)
  - [ ] Call signal detection: map call outcome codes to signal types (connected+voicemail vs. connected+conversation)
  - [ ] Emit `SignalArtifact` on qualifying events; skip and log on non-qualifying

- [ ] **Task 3 – Integration with webhook pipeline** (AC: 1, 3)
  - [ ] On normalized `ProviderEvent` creation (from Story 2.3), call signal detection service
  - [ ] Pass `idempotency_key` from provider event to prevent duplicate detection on webhook retry

- [ ] **Task 4 – Tests** (AC: 1, 2, 3)
  - [ ] Unit test: email reply with user content produces signal artifact
  - [ ] Unit test: auto-reply (X-Autoreply or In-Reply-To with no body) produces no signal
  - [ ] Unit test: duplicate raw event ID blocked by constraint / dedup check
  - [ ] Integration test: call outcome with positive sentiment stored as signal artifact

## Dev Notes

### Architecture Compliance

- Signal artifacts are operational state stored in PostgreSQL. Raw content (email body excerpts, transcript refs) should be stored by reference or truncated to avoid PII accumulation in the hot DB path. Full content goes to MongoDB event store.
- Signal detection is triggered by the provider event pipeline, not as a polling job.
- Do NOT mix signal detection logic with routing logic. Detection creates the artifact; routing (3.3) consumes it.

### Signal Types

| Signal Type | Channel | Qualifying Condition |
|-------------|---------|---------------------|
| `email_reply` | email | User-authored reply content, no auto-reply headers |
| `voicemail_left` | telephony | Call connected, voicemail recorded |
| `conversation_completed` | telephony | Call connected + duration >= 30s |
| `positive_transcript_keyword` | telephony | Transcript contains configured positive-intent keywords |
| `booking_intent` | telephony/email | Explicit scheduling request detected |

### Suggested File Touch Points

- `apps/api/app/domain/signals/signal_detection_service.py` (new)
- `apps/api/app/domain_models.py` (add SignalArtifact)
- `apps/api/app/alembic/versions/*_add_signal_artifacts.py` (new migration)
- `apps/api/app/domain/providers/` (extend event processing to call detection)
- `apps/api/tests/domain/test_signal_detection_service.py` (new)

### References

- [Source: epics.md#Story-3.1-Detect-Intent-Signals-from-Channel-Outcomes]
- [Source: architecture.md#Data-Architecture]
- [Source: architecture.md#API-Communication-Patterns]

## Dev Agent Record

### Agent Model Used

_To be completed_

### Debug Log References

### Completion Notes List

### File List
