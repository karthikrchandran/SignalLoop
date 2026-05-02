# Story 5.3: Surface Campaign Health, Failures, and Dead-Letter Visibility

Status: completed

## Story

As an operations user,
I want real-time campaign health and failure visibility including dead-letter items,
so that I can identify and recover incidents quickly.

## Acceptance Criteria

1. **Given** worker, queue, and provider execution telemetry is captured
   **When** a failure, retry, or dead-letter event occurs
   **Then** the affected campaign's health dashboard reflects the event within 60 seconds (NFR8)
   **And** dead-letter entries are visible with: contact_id, action_type, failure_reason, retry_count, first_failed_at, retry_eligible.

2. **Given** a campaign health dashboard is requested
   **When** the data is fetched
   **Then** it shows: active workflow count, success rate (last 1h, 24h), failure count by type, current dead-letter queue depth, and provider error distribution.

3. **Given** dead-letter items are visible
   **When** an authorized operator clicks "Retry"
   **Then** the item is re-queued with a fresh retry counter
   **And** the retry is attributed to the operator with timestamp.

4. **Given** dead-letter items have retry-ineligible status (e.g., max global retries exceeded, suppressed contact)
   **When** the operator views the item
   **Then** retry is visually disabled with an explanation tooltip
   **And** a "Dismiss" action is available to clear it from the queue with attribution.

## Tasks / Subtasks

- [x] **Task 1 – Campaign health aggregation endpoint** (AC: 2)
  - [x] `GET /workspaces/{wsId}/campaigns/{campaignId}/health` — returns current health snapshot
  - [x] Compute from `action_queue` (dead_letter count, retry count), `outbox_events` (success/failure count), `routing_decisions` (last 24h)
  - [x] Cache in Redis (TTL: 30s) per campaign
  - [x] Include: `{active_count, success_count_1h, success_count_24h, failure_count_24h, dead_letter_count, provider_errors_by_type}`

- [x] **Task 2 – Dead-letter visibility API** (AC: 1, 3, 4)
  - [x] `GET /workspaces/{wsId}/campaigns/{campaignId}/dead-letters?page=`
  - [x] `POST /workspaces/{wsId}/campaigns/{campaignId}/dead-letters/{itemId}/retry` — operator re-queue action
  - [x] `POST /workspaces/{wsId}/campaigns/{campaignId}/dead-letters/{itemId}/dismiss` — operator dismiss
  - [x] Retry endpoint validates retry eligibility; returns explicit error if retry-ineligible

- [x] **Task 3 – Dead-letter SLA enforcement** (AC: 1)
  - [x] When `action_queue_service` writes a dead-letter entry, insert a row to the PostgreSQL `dead_letter_events` table immediately
  - [x] Include: campaign_id, contact_id, action_type, failure_reason, dead_lettered_at
  - [x] Health dashboard reads from PostgreSQL `action_queue` (current queue state) and `dead_letter_events` (event history) for SLA measurement

- [x] **Task 4 – Web UI for campaign health dashboard** (AC: 1, 2, 3, 4)
  - [x] `apps/web/src/features/monitoring/CampaignHealthPage.tsx`
  - [x] Summary strip: success rate, failure count, dead-letter count (color-coded by severity)
  - [x] Dead-letter queue table with: contact, action, failure reason, retry count, actions (Retry | Dismiss)
  - [x] Retry-ineligible items show disabled Retry button with tooltip reason
  - [x] WebSocket or polling (30s) for live updates (UX: "Last updated X seconds ago")

- [x] **Task 5 – Tests** (AC: 1, 2, 3, 4)
  - [x] Unit test: dead-letter entry emits MongoDB event immediately
  - [x] Unit test: retry-eligible item re-queued with fresh counter
  - [x] Unit test: retry-ineligible item returns error code
  - [x] Integration test: health endpoint reflects dead-letter count from action_queue

## Dev Notes

### Architecture Compliance

- Health data is a live aggregate view — do NOT materialize into a separate health table that requires background sync. Pull from live `action_queue` on demand; cache in Redis.
- Dead-letter visibility SLA (NFR8): entry must appear in the API within 60 seconds of the queue write. Write to the PostgreSQL `dead_letter_events` table synchronously inside the `action_queue_service` transaction to guarantee this without additional polling lag.
- Retry max: check `settings.MAX_RETRY_COUNT` before allowing retry. If `retry_count >= max`, set `retry_eligible = false` in the API response.
- WebSocket endpoint for push-based live updates: `ws://api/ws/campaigns/{campaignId}/health` — invalidate Redis key and push delta on queue state change. Fall back to 30s polling in UI.

### Suggested File Touch Points

- `apps/api/app/api/routes/campaign_health.py` (new)
- `apps/api/app/domain/outreach/action_queue_service.py` (extend dead-letter write)
- `apps/api/alembic/versions/{hash}_create_dead_letter_events.py` (new migration for `dead_letter_events` table)
- `apps/web/src/features/monitoring/CampaignHealthPage.tsx` (new)
- `apps/api/tests/api/routes/test_campaign_health.py` (new)

### References

- [Source: epics.md#Story-5.3-Surface-Campaign-Health-Failures-and-Dead-Letter-Visibility]
- NFR8: Dead-letter entries must be visible within 60 seconds.
- [Source: architecture.md#Agent-Consistency-Rules]

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6

### Debug Log References

- Alembic `.pyc` cache caused stale `down_revision` display; resolved via psql DDL fallback + `alembic stamp`.
- `Campaign.created_by` NOT NULL: fixed by adding `created_by=uuid.uuid4()` in test fixture.

### Completion Notes List

- All 4 ACs satisfied.
- Migration applied via psql DDL (columns + table) then `alembic stamp c1d2e3f4a5b6`.
- Redis health cache uses 30s TTL; tests mock Redis via `unittest.mock`.
- Retry-ineligible check uses `settings.MAX_RETRY_COUNT = 3`.

### File List

- `apps/api/app/domain_models.py`
- `apps/api/app/domain/outreach/action_queue_service.py`
- `apps/api/app/core/config.py`
- `apps/api/app/alembic/versions/c1d2e3f4a5b6_add_dead_letter_events.py` (new)
- `apps/api/app/api/routes/campaign_health.py` (new)
- `apps/api/app/api/main.py`
- `apps/web/src/features/monitoring/CampaignHealthPage.tsx` (new)
- `apps/api/tests/api/routes/test_campaign_health.py` (new)
