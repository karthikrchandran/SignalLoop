# Story 2.3: Integrate Provider Adapters and Event Normalization

Status: in-progress

## Story

As a platform engineer,
I want standardized adapter contracts and normalized provider events,
so that external channels (email, telephony, transcription, scheduling) behave consistently within the core workflow.

## Acceptance Criteria

1. **Given** email, telephony, transcription, and scheduling integrations
   **When** the system dispatches an outreach action to a provider
   **Then** the call passes through a standardized `NotificationProviderAdapter` contract
   **And** the adapter is swappable without changes to the core execution worker.

2. **Given** a provider returns an outcome or posts a callback
   **When** the adapter processes the response
   **Then** an internal `ProviderEvent` is emitted with required envelope fields (provider_id, external_ref_id, event_type, channel, normalized_status, raw_payload, correlation_id, received_at)
   **And** the event is persisted to the `provider_event_log` table.

3. **Given** a provider response fails schema validation
   **When** validation runs on the inbound payload
   **Then** a validation-failure `ProviderEvent` is stored with `status=validation_failed` and raw payload preserved
   **And** the failure is surfaced to operations monitoring within the SLA window (NFR19).

4. **Given** multiple provider adapters are registered
   **When** the worker selects an adapter for a given channel and campaign strategy
   **Then** the correct adapter is resolved via the adapter registry without hard-coded conditionals in worker code.

## Tasks / Subtasks

- [x] **Task 1 – Provider adapter ABC and domain models** (AC: 1, 2)
  - [x] `NotificationProviderAdapter` abstract base class in `apps/api/app/domain/providers/`
  - [x] `ProviderCredential` model (workspace_id, channel, provider_type, credentials_encrypted, is_active)
  - [x] `ProviderEventLog` model (provider_id, external_ref_id, event_type, channel, normalized_status, raw_payload_json, correlation_id, received_at)
  - [x] Alembic migration `e5f6a7b8c9d0` (provider tables included)

- [ ] **Task 2 – Adapter implementations (stub providers)** (AC: 1, 4)
  - [ ] `EmailProviderAdapter(NotificationProviderAdapter)` — stub implementation for development/test
  - [ ] `TelephonyProviderAdapter(NotificationProviderAdapter)` — stub implementation
  - [ ] `SchedulingProviderAdapter(NotificationProviderAdapter)` — stub implementation
  - [ ] Adapter registry: `{channel_type: adapter_class}` dict loaded on startup

- [ ] **Task 3 – Inbound event normalization pipeline** (AC: 2, 3)
  - [ ] Webhook receiver endpoint: `POST /webhooks/providers/{provider_id}/events`
  - [ ] Validate inbound payload against `ProviderEventEnvelope` schema (Pydantic)
  - [ ] On success: persist normalized `ProviderEventLog` entry, emit internal domain event for worker consumption
  - [ ] On validation failure: persist raw payload with `status=validation_failed`; emit ops alert event within 60s SLA

- [ ] **Task 4 – MongoDB event store integration** (AC: 2)
  - [ ] Extend `mongo_schema.py` to write normalized provider events to `provider_events` collection
  - [ ] Include: `event_type`, `channel`, `normalized_status`, `external_ref_id`, `correlation_id`, `received_at`

- [ ] **Task 5 – Adapter contract tests** (AC: 1, 2, 3)
  - [ ] Contract test for each adapter: verify it implements required ABC methods
  - [ ] Integration test for webhook endpoint: valid payload normalizes correctly
  - [ ] Integration test for webhook endpoint: invalid payload produces validation_failed log entry
  - [ ] Test that adapter registry resolves correct adapter type per channel

## Dev Notes

### Architecture Compliance

- `NotificationProviderAdapter` must define: `send(action: ActionQueue) -> ProviderEvent`, `handle_callback(raw_event: dict) -> ProviderEvent`.
- Adapters must NEVER throw raw provider errors to callers; always wrap in semantic taxonomy.
- Provider credentials must be encrypted at rest. Use the secret storage pattern (environment-resolved secrets); never log credential values.
- Webhook endpoint is public-facing but must validate an HMAC signature from the provider. Use a per-provider signing secret stored in `ProviderCredential`.
- Normalized status values: `delivered`, `failed`, `bounced`, `no_answer`, `voicemail`, `connected`, `transcribed`, `scheduled`, `cancelled`, `validation_failed`.

### Suggested File Touch Points

- `apps/api/app/domain/providers/adapter_abc.py` (extend existing ABC)
- `apps/api/app/domain/providers/email_adapter.py` (new stub)
- `apps/api/app/domain/providers/telephony_adapter.py` (new stub)
- `apps/api/app/domain/providers/scheduling_adapter.py` (new stub)
- `apps/api/app/domain/providers/registry.py` (new)
- `apps/api/app/api/routes/webhooks.py` (new)
- `apps/api/app/infrastructure/db/mongodb/mongo_schema.py` (extend)
- `apps/api/tests/api/routes/test_webhooks.py` (new)
- `apps/workers/worker_app/outreach/execution_worker.py` (wire adapter registry)

### Key Libraries

| Library | Purpose |
|---------|---------|
| Pydantic | Schema validation for inbound webhook payloads |
| hmac / hashlib | HMAC signature validation for webhook security |
| motor | MongoDB event storage |

### References

- [Source: epics.md#Story-2.3-Integrate-Provider-Adapters-and-Event-Normalization]
- [Source: architecture.md#Data-Architecture]
- [Source: architecture.md#API-Communication-Patterns]
- [Source: architecture.md#Error-Semantics-Operator-Taxonomy]

## Dev Agent Record

### Agent Model Used

_To be completed_

### Debug Log References

### Completion Notes List

- `NotificationProviderAdapter` ABC, `ProviderCredential`, and `ProviderEventLog` domain models created in increment-2 (2026-04-01) as Epic 2 foundation.
- MongoDB event store helpers (`mongo_schema.py`) created in increment-2.
- Adapter stub implementations, webhook endpoint, and normalization pipeline (Tasks 2-5) pending.

### File List

- `apps/api/app/domain/providers/adapter_abc.py` (NotificationProviderAdapter ABC)
- `apps/api/app/domain_models.py` (ProviderCredential, ProviderEventLog)
- `apps/api/app/alembic/versions/e5f6a7b8c9d0_add_epic2_foundation_tables.py`
- `apps/api/app/infrastructure/db/mongodb/mongo_schema.py`
