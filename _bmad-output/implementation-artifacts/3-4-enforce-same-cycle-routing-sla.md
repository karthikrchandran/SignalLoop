# Story 3.4: Enforce Same-Cycle Routing SLA

Status: backlog

## Story

As an operations leader,
I want qualifying signals processed and routed within the target cycle window (60 seconds for p95),
so that lead momentum is preserved and high-intent contacts are not left waiting.

## Acceptance Criteria

1. **Given** a medium or strong intent signal is ingested
   **When** downstream routing execution completes
   **Then** the elapsed time from `signal.detected_at` to `routing_decision.decided_at` is captured
   **And** p95 routing latency meets the 60-second SLA (NFR3).

2. **Given** a routing SLA breach occurs (routing completes > 60s after signal detection)
   **When** the breach is detected
   **Then** a SLA breach event is emitted to the operational monitoring pipeline
   **And** the breach is visible in the campaign health dashboard within the dead-letter SLA window (NFR8).

3. **Given** the routing SLA tracker is active
   **When** SLA metrics are aggregated
   **Then** p50 and p95 latency per campaign are accessible via the operations KPI endpoint
   **And** the data refreshes at minimum every 5 minutes.

## Tasks / Subtasks

- [ ] **Task 1 – SLA tracking on routing decisions** (AC: 1)
  - [ ] Add `routing_sla_ms` column to `routing_decisions` table (elapsed ms from signal detected_at)
  - [ ] Populate on routing decision write in routing engine
  - [ ] Add Alembic migration (or extend routing tables migration from 3.3)

- [ ] **Task 2 – SLA breach detection and event emission** (AC: 2)
  - [ ] After routing decision write, if `routing_sla_ms > 60000`: emit `routing_sla_breach` event to MongoDB operational events collection
  - [ ] Include: campaign_id, contact_id, signal_id, routing_sla_ms, detected_at, decided_at

- [ ] **Task 3 – SLA metrics aggregation endpoint** (AC: 3)
  - [ ] `GET /workspaces/{wsId}/campaigns/{campaignId}/routing-sla` returning: p50_ms, p95_ms, breach_count, window_start, window_end
  - [ ] Compute from `routing_decisions` in PostgreSQL (window: last 24h default, configurable via query param)
  - [ ] Response cached in Redis for 5 minutes per campaign

- [ ] **Task 4 – Tests** (AC: 1, 2, 3)
  - [ ] Unit test: routing engine captures sla_ms correctly
  - [ ] Unit test: breach event emitted when sla_ms > 60000
  - [ ] Unit test: breach event NOT emitted when within SLA
  - [ ] Integration test: SLA endpoint returns correct p95/p50 for mock decision data

## Dev Notes

### Architecture Compliance

- SLA measurement is a cross-cutting concern that must NOT add latency to the routing critical path. Write `routing_sla_ms` synchronously as part of the routing decision insert (one row, same transaction).
- SLA breach event emission is fire-and-forget to MongoDB. Do not block routing commit on MongoDB write.
- Redis cache for SLA endpoint: key `sla:{workspace_id}:{campaign_id}`, TTL 300s. Invalidate on new routing decision.
- SLA threshold is configurable via environment variable `ROUTING_SLA_THRESHOLD_MS` (default: 60000).

### Suggested File Touch Points

- `apps/api/app/domain/routing/routing_engine.py` (extend with SLA tracking)
- `apps/api/app/domain_models.py` (add routing_sla_ms to RoutingDecision)
- `apps/api/app/api/routes/campaign_sla.py` (new endpoint)
- `apps/api/app/infrastructure/db/mongodb/mongo_schema.py` (add sla_breach event write)
- `apps/api/tests/domain/test_routing_sla.py` (new)

### References

- [Source: epics.md#Story-3.4-Enforce-Same-Cycle-Routing-SLA]
- [Source: architecture.md#Agent-Consistency-Rules]
- NFR3: Medium/strong intent signals must trigger routing within 60 seconds for p95.
- NFR8: Dead-letter entries must be visible within 60 seconds.

## Dev Agent Record

### Agent Model Used

_To be completed_

### Debug Log References

### Completion Notes List

### File List
