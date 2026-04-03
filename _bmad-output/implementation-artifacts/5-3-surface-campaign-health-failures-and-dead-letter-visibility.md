# Story 5.3: Surface Campaign Health, Failures, and Dead-Letter Visibility

Status: backlog

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

- [ ] **Task 1 – Campaign health aggregation endpoint** (AC: 2)
  - [ ] `GET /workspaces/{wsId}/campaigns/{campaignId}/health` — returns current health snapshot
  - [ ] Compute from `action_queue` (dead_letter count, retry count), `outbox_events` (success/failure count), `routing_decisions` (last 24h)
  - [ ] Cache in Redis (TTL: 30s) per campaign
  - [ ] Include: `{active_count, success_count_1h, success_count_24h, failure_count_24h, dead_letter_count, provider_errors_by_type}`

- [ ] **Task 2 – Dead-letter visibility API** (AC: 1, 3, 4)
  - [ ] `GET /workspaces/{wsId}/campaigns/{campaignId}/dead-letters?page=`
  - [ ] `POST /workspaces/{wsId}/campaigns/{campaignId}/dead-letters/{itemId}/retry` — operator re-queue action
  - [ ] `POST /workspaces/{wsId}/campaigns/{campaignId}/dead-letters/{itemId}/dismiss` — operator dismiss
  - [ ] Retry endpoint validates retry eligibility; returns explicit error if retry-ineligible

- [ ] **Task 3 – Dead-letter SLA enforcement** (AC: 1)
  - [ ] When `action_queue_service` writes a dead-letter entry, emit event to MongoDB `dead_letter_events` collection immediately
  - [ ] Include: campaign_id, contact_id, action_type, failure_reason, dead_lettered_at
  - [ ] Health dashboard reads from both PostgreSQL (queue state) and MongoDB (event history) for SLA measurement

- [ ] **Task 4 – Web UI for campaign health dashboard** (AC: 1, 2, 3, 4)
  - [ ] `apps/web/src/features/monitoring/CampaignHealthPage.tsx`
  - [ ] Summary strip: success rate, failure count, dead-letter count (color-coded by severity)
  - [ ] Dead-letter queue table with: contact, action, failure reason, retry count, actions (Retry | Dismiss)
  - [ ] Retry-ineligible items show disabled Retry button with tooltip reason
  - [ ] WebSocket or polling (30s) for live updates (UX: "Last updated X seconds ago")

- [ ] **Task 5 – Tests** (AC: 1, 2, 3, 4)
  - [ ] Unit test: dead-letter entry emits MongoDB event immediately
  - [ ] Unit test: retry-eligible item re-queued with fresh counter
  - [ ] Unit test: retry-ineligible item returns error code
  - [ ] Integration test: health endpoint reflects dead-letter count from action_queue

## Dev Notes

### Architecture Compliance

- Health data is a live aggregate view — do NOT materialize into a separate health table that requires background sync. Pull from live `action_queue` on demand; cache in Redis.
- Dead-letter visibility SLA (NFR8): entry must appear in the API within 60 seconds of the queue write. Use MongoDB event emission in `action_queue_service` to satisfy this without API-to-DB polling lag.
- Retry max: check `settings.MAX_RETRY_COUNT` before allowing retry. If `retry_count >= max`, set `retry_eligible = false` in the API response.
- WebSocket endpoint for push-based live updates: `ws://api/ws/campaigns/{campaignId}/health` — invalidate Redis key and push delta on queue state change. Fall back to 30s polling in UI.

### Suggested File Touch Points

- `apps/api/app/api/routes/campaign_health.py` (new)
- `apps/api/app/domain/outreach/action_queue_service.py` (extend dead-letter write)
- `apps/api/app/infrastructure/db/mongodb/mongo_schema.py` (dead_letter_events write)
- `apps/web/src/features/monitoring/CampaignHealthPage.tsx` (new)
- `apps/api/tests/api/routes/test_campaign_health.py` (new)

### References

- [Source: epics.md#Story-5.3-Surface-Campaign-Health-Failures-and-Dead-Letter-Visibility]
- NFR8: Dead-letter entries must be visible within 60 seconds.
- [Source: architecture.md#Agent-Consistency-Rules]

## Dev Agent Record

### Agent Model Used

_To be completed_

### Debug Log References

### Completion Notes List

### File List
