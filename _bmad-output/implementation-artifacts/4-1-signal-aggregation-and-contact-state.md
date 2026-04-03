# Story 4.1: Signal Aggregation and Contact State

Status: ready-for-dev

## Story

As a marketing admin,
I want a unified view of all signals detected for each contact across email and voice channels,
so that I can understand where each prospect stands in the outreach journey.

## Acceptance Criteria

1. **Given** signals are detected from email (reply, bounce, unsub) and voice (answered, scheduling, positive interest) **When** they are stored **Then** all signals are in a single signal_events table with channel, type, confidence, and source
2. **Given** a contact has signals from both channels **When** I GET /api/v1/contacts/{id}/signals **Then** I receive a chronological list of all signal events
3. **Given** SignalEvent records exist **When** they are queried **Then** each record includes: contact_id, campaign_id, channel (email/voice), signal_type, confidence, source_event_id, metadata (JSONB), created_at
4. **Given** aggregated signals exist **When** the contact list is displayed **Then** each contact row shows their latest signal type and channel
5. **Given** a SignalEvent is created **When** downstream systems need it **Then** the event is available for automated followup triggers (Story 4.2)

## Tasks / Subtasks

- [ ] Task 1: Create/verify SignalEvent SQLModel in apps/api/app/domain/signals/models.py (AC: 1,3)
  - [ ] If not already created in Story 2.5, create here
  - [ ] Fields: id (UUID), contact_id (FK), campaign_id (FK), channel (enum: email/voice), signal_type (str), confidence (float), source_event_id (UUID nullable), metadata (JSONB nullable), created_at
  - [ ] Index on (contact_id, created_at), (campaign_id, signal_type)
- [ ] Task 2: Create/verify Alembic migration for signal_events (AC: 1)
- [ ] Task 3: Create signal aggregation service in apps/api/app/domain/signals/aggregation_service.py (AC: 2,4)
  - [ ] get_contact_signals(contact_id) → list of SignalEvent ordered by created_at desc
  - [ ] get_latest_signal(contact_id) → most recent SignalEvent or None
  - [ ] get_campaign_signal_summary(campaign_id) → counts by signal_type and channel
- [ ] Task 4: Create API endpoint GET /api/v1/contacts/{id}/signals (AC: 2)
  - [ ] Returns list of SignalEvent for the contact
  - [ ] Filterable by channel, signal_type, date range
- [ ] Task 5: Update contact list API to include latest signal info (AC: 4)
  - [ ] Add latest_signal_type and latest_signal_channel to contact list response
- [ ] Task 6: Ensure email signal detection (Story 2.5) writes to SignalEvent table (AC: 1,5)
- [ ] Task 7: Ensure voice call outcomes write to SignalEvent table (AC: 1,5)
  - [ ] ANSWERED → signal_type="call_answered"
  - [ ] scheduling_interest=true → signal_type="scheduling_requested"
  - [ ] Positive interest detected → signal_type="voice_positive_interest"
- [ ] Task 8: Write unit tests for aggregation service (AC: 2,4)
- [ ] Task 9: Write API tests for signals endpoint (AC: 2)

## Dev Notes

- SignalEvent is the central record for all cross-channel signal data
- This story may overlap with Story 2.5 (email signals) — coordinate to avoid duplication
- Voice signals are written from the conversation engine and postcall worker

### References
- [Source: architecture.md#Section-7 — AuditEvent and signal state tracking]
- [Source: prd.md#FR19 — detect positive intent signals from channel outcomes]
- [Source: prd.md#FR20 — classify signal confidence]

## Dev Agent Record
### Agent Model Used
### Debug Log References
### Completion Notes List
### File List
