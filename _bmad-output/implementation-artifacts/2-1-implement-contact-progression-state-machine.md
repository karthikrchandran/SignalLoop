# Story 2.1: Implement Contact Progression State Machine

Status: in-progress

## Story

As a system operator,
I want each contact to move through deterministic workflow states,
so that progression is reliable, auditable, and resumable after failures.

## Acceptance Criteria

1. **Given** a contact enters an active campaign
   **When** execution actions occur across outreach stages
   **Then** the system persists per-contact state transitions in order
   **And** duplicate state-transition requests are idempotent (same prior state = no-op; wrong prior state = rejected).

2. **Given** an invalid state transition is attempted (e.g., enrolled → booked without passing nurture)
   **When** the transition is submitted
   **Then** the system rejects it with a semantic error response identifying the invalid transition
   **And** no state-history record is created.

3. **Given** a contact's current progression state
   **When** the state is queried
   **Then** the API returns the current state, last-transition timestamp, and the allowed next transitions.

4. **Given** a contact transitions state
   **When** the event is committed
   **Then** a `ContactStateHistory` entry is written with actor_id, reason_code, correlation_id, and timestamp
   **And** the event is mirrored to the MongoDB audit envelope for immutable audit trail.

## Tasks / Subtasks

- [x] **Task 1 – Domain models and migration** (AC: 1, 2, 4)
  - [x] `contacts` table (id, email, first_name, company, timezone, workspace_id, status, timestamps)
  - [x] `contact_progression` table (contact_id, campaign_id, current_state, version, unique constraint)
  - [x] `contact_state_history` table (contact_id, campaign_id, from_state, to_state, actor_id, reason_code, correlation_id, created_at)
  - [x] `outbox_events` table with unique `idempotency_key` constraint
  - [x] `action_queue` table
  - [x] Alembic migration `e5f6a7b8c9d0` chained correctly after governance migration

- [x] **Task 2 – Progression service and transition logic** (AC: 1, 2)
  - [x] `_ALLOWED_TRANSITIONS` map defining valid state paths
  - [x] `transition_contact_state(contact_id, campaign_id, to_state, actor_id, reason_code, correlation_id)` with optimistic locking
  - [x] Raise `ValueError` with semantic error on invalid transitions
  - [x] Create/update `ContactProgression` record and append `ContactStateHistory` row atomically

- [x] **Task 3 – Domain tests** (AC: 1, 2)
  - [x] Valid transition succeeds and history is recorded
  - [x] Invalid transition raises `ValueError`
  - [x] Tests run against in-memory SQLite engine (no external DB dependency)

- [ ] **Task 4 – HTTP API exposure** (AC: 3)
  - [ ] `GET /contacts/{contactId}/progression?campaignId=` returning current state + allowed transitions
  - [ ] `POST /contacts/{contactId}/progression/transition` with idempotency key
  - [ ] Role guard: `operator` or higher required
  - [ ] Integration tests for valid/invalid transitions via HTTP

- [ ] **Task 5 – MongoDB audit mirroring** (AC: 4)
  - [ ] On successful state transition, write event envelope to MongoDB `contact_events` collection
  - [ ] Envelope: `{event_type, contact_id, campaign_id, from_state, to_state, actor_id, reason_code, correlation_id, timestamp}`

## Dev Notes

### Architecture Compliance

- Contact progression state belongs to the `contacts` domain. Keep transition logic in `progression_service.py`; route handlers must not duplicate transition logic.
- States: `enrolled` → `nurture` → `signaled` → `booking` → `confirmed` | `handed_off` | `failed` | `suppressed`. Do not invent states not in this list.
- All side-effecting endpoints require `Idempotency-Key` header.
- Semantic error taxonomy: invalid transitions → `SYSTEM_ERROR` with reason code `INVALID_STATE_TRANSITION`.
- MongoDB writes are fire-and-forget (best-effort audit); do not let MongoDB failures roll back the Postgres transaction.

### Existing Implementation (from increment-3 notes)

The domain layer is complete as of 2026-04-02:
- `apps/api/app/domain/contacts/progression_service.py` — fully implemented
- `apps/api/app/domain_models.py` — Contact, ContactProgression, ContactStateHistory models defined
- `apps/api/app/alembic/versions/e5f6a7b8c9d0_add_epic2_foundation_tables.py` — migration applied

What remains is the HTTP API exposure (Task 4) and MongoDB mirroring (Task 5).

### Suggested File Touch Points

- `apps/api/app/api/routes/contacts.py` (create or extend)
- `apps/api/app/domain/contacts/progression_service.py` (extend for MongoDB mirror call)
- `apps/api/tests/api/routes/test_contact_progression.py` (new)
- `apps/api/app/infrastructure/db/mongodb/mongo_schema.py` (event write helper)

### Testing Requirements

- HTTP integration tests must cover: valid transition, invalid transition (wrong prior state), duplicate transition (idempotency).
- MongoDB mirror test can use a mock/stub to avoid real Mongo dependency in fast-test suite.

### Key Libraries

| Library | Purpose |
|---------|---------|
| SQLModel / SQLAlchemy | ORM + migration |
| motor | Async MongoDB driver for audit events |
| anyio | Async test support |

### References

- [Source: epics.md#Story-2.1-Implement-Contact-Progression-State-Machine]
- [Source: architecture.md#Data-Architecture]
- [Source: architecture.md#API-Communication-Patterns]
- [Source: architecture.md#Error-Semantics-Operator-Taxonomy]

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6 (GitHub Copilot)

### Debug Log References

- Domain tests: `pytest tests/domain/test_progression_service.py` → 2 passed (valid transition, invalid transition rejection)
- Domain tests: `pytest tests/domain/test_outbox_service.py` → passed

### Completion Notes List

- Epic 2 domain foundation (Contact, ContactProgression, ContactStateHistory, OutboxEvent, ActionQueue, ProviderCredential, ProviderEventLog) implemented in increment-2 (2026-04-01).
- Progression service with `_ALLOWED_TRANSITIONS` and `transition_contact_state` implemented in increment-3 (2026-04-02).
- Alembic migration `e5f6a7b8c9d0` created and validated.
- HTTP API exposure and MongoDB mirroring (Tasks 4-5) remain pending.

### File List

- `apps/api/app/domain_models.py` (Contact, ContactProgression, ContactStateHistory, OutboxEvent, ActionQueue, ProviderCredential, ProviderEventLog)
- `apps/api/app/domain/contacts/progression_service.py`
- `apps/api/app/domain/outreach/outbox_service.py`
- `apps/api/app/domain/outreach/action_queue_service.py`
- `apps/api/app/alembic/versions/e5f6a7b8c9d0_add_epic2_foundation_tables.py`
- `apps/api/tests/domain/test_progression_service.py`
- `apps/api/tests/domain/test_outbox_service.py`
