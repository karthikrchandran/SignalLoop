# Story 2.1: Define Sequence Data Model and Migration

Status: ready-for-dev

## Story

As a backend engineer,
I want to create the SQLModel tables for the email sequence engine,
so that the database schema supports multi-step email sequences with contact tracking.

## Acceptance Criteria

1. **Given** no sequence tables exist **When** the Alembic migration runs **Then** EmailSequence, SequenceStep, ContactSequenceState, SendRequest, and EmailEvent tables are created
2. **Given** EmailSequence model is defined **When** a sequence is created **Then** it has: id (UUID), campaign_id (FK), name (str), active (bool), created_by (UUID), created_at, updated_at
3. **Given** SequenceStep model is defined **When** steps are added **Then** each has: id (UUID), sequence_id (FK), step_order (int), delay_days (int), subject_template (str), body_template (text), created_at
4. **Given** ContactSequenceState model is defined **When** a contact is enrolled **Then** it tracks: contact_id (FK), sequence_id (FK), current_step (int), next_send_at (datetime), status (enum: ACTIVE/PAUSED/STOPPED/COMPLETED), signal_type (str nullable), signal_detected_at (datetime nullable)
5. **Given** SendRequest model is defined **When** an email is queued **Then** it has: id (UUID), contact_sequence_state_id (FK), step_order (int), idempotency_key (str unique), provider_message_id (str nullable), status (enum: PENDING/SENT/FAILED), created_at, sent_at
6. **Given** EmailEvent model is defined **When** a webhook arrives **Then** it stores: id (UUID), send_request_id (FK), event_type (str), timestamp (datetime), raw_payload (JSONB)
7. **Given** all models have appropriate indexes **When** queries run **Then** lookups by campaign_id, sequence_id, contact_id, status, and next_send_at are indexed

## Tasks / Subtasks

- [ ] Task 1: Create apps/api/app/domain/sequences/ module with __init__.py (AC: all)
- [ ] Task 2: Create EmailSequence SQLModel in apps/api/app/domain/sequences/models.py (AC: 2)
- [ ] Task 3: Create SequenceStep SQLModel (AC: 3)
- [ ] Task 4: Create ContactSequenceState SQLModel with status enum (AC: 4)
- [ ] Task 5: Create SendRequest SQLModel with idempotency_key unique constraint (AC: 5)
- [ ] Task 6: Create EmailEvent SQLModel with JSONB payload (AC: 6)
- [ ] Task 7: Add composite indexes for query patterns: (sequence_id, status, next_send_at), (contact_id, sequence_id), (send_request_id, event_type) (AC: 7)
- [ ] Task 8: Generate Alembic migration and verify upgrade/downgrade (AC: 1)
- [ ] Task 9: Write unit tests for model creation and enum behavior (AC: all)

## Dev Notes

- Use SQLModel (not raw SQLAlchemy) — project convention
- Status enums should be Python Enum classes, stored as VARCHAR
- ContactSequenceState has unique constraint on (contact_id, sequence_id) — one enrollment per sequence
- next_send_at is critical for worker polling — must be indexed

### References
- [Source: architecture.md#Section-5 — Email Sequence Engine data model]
- [Source: architecture.md#Section-7 — Domain objects: EmailSequence, SequenceStep, ContactSequenceState, SendRequest, EmailEvent]
- [Source: prd.md#FR14-FR18 — workflow execution requirements]

## Dev Agent Record
### Agent Model Used
### Debug Log References
### Completion Notes List
### File List
