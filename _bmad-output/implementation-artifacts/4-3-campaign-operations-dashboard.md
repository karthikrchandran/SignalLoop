# Story 4.3: Campaign Operations Dashboard

Status: ready-for-dev

## Story

As a marketing admin,
I want a real-time operations dashboard showing email and call metrics,
so that I can monitor campaign performance and take action when needed.

## Acceptance Criteria

1. **Given** emails have been sent **When** I view email metrics **Then** I see counts of: sent, delivered, opened, replied, bounced (with percentages)
2. **Given** calls have been made **When** I view call metrics **Then** I see counts of: calls made, answered, voicemail, no-answer, scheduling requests
3. **Given** signals have been detected **When** I view signal metrics **Then** I see signal counts by type (positive email, positive call, scheduling, bounce, unsub) and channel
4. **Given** campaigns are active **When** I view campaign metrics **Then** I see each campaign with: name, status, contacts count, emails sent, calls made, signals detected
5. **Given** the daily call cap is 50 **When** I view the dashboard **Then** I see current progress (e.g., "42/50 calls made today")
6. **Given** I want to control a campaign **When** I click pause/resume **Then** the campaign state changes and workers respect the new state

## Tasks / Subtasks

- [ ] Task 1: Create dashboard metrics API endpoints (AC: 1,2,3,4,5)
  - [ ] GET /api/v1/dashboard/email-metrics?campaign_id=X&date_range=7d
    - Query SendRequest and EmailEvent tables for counts
  - [ ] GET /api/v1/dashboard/call-metrics?campaign_id=X&date_range=7d
    - Query CallRequest and CallSession tables for counts
  - [ ] GET /api/v1/dashboard/signals?campaign_id=X&date_range=7d
    - Query SignalEvent table for counts by type and channel
  - [ ] GET /api/v1/dashboard/campaigns
    - Active campaigns with aggregate metrics
  - [ ] GET /api/v1/dashboard/daily-cap-status
    - Today's call count vs configured cap
- [ ] Task 2: Create dashboard service in apps/api/app/domain/dashboard/service.py (AC: 1,2,3,4,5)
  - [ ] Aggregate queries with date filtering
  - [ ] Campaign-level and global rollups
  - [ ] Daily cap progress calculation
- [ ] Task 3: Create Operations Dashboard frontend page (AC: 1,2,3,4,5,6)
  - [ ] Top row: 4 KPI metric cards (total emails sent, total calls made, total signals, conversion rate)
  - [ ] Middle: active campaigns table with per-campaign metrics
  - [ ] Bottom left: recent events feed (last 20 events)
  - [ ] Bottom right: daily call cap progress bar
  - [ ] Date range selector (today, 7d, 30d)
- [ ] Task 4: Implement campaign pause/resume (AC: 6)
  - [ ] PUT /api/v1/campaigns/{id}/pause — set campaign.status = PAUSED
  - [ ] PUT /api/v1/campaigns/{id}/resume — set campaign.status = ACTIVE
  - [ ] Workers check campaign.status before processing contacts
- [ ] Task 5: Write API tests for dashboard endpoints (AC: 1,2,3,4,5)
- [ ] Task 6: Write frontend tests for dashboard rendering (AC: 3)

## Dev Notes

- Dashboard should load fast — use aggregate queries, not per-record iteration
- Consider caching dashboard metrics in Redis with short TTL (30s) if queries are slow
- Date range filtering on all metrics endpoints
- Campaign pause/resume must be immediate — workers check before each action

### References
- [Source: ux-design-specification.md#Section-5.7 — Operations Dashboard]
- [Source: prd.md#FR24 — campaign visibility dashboard]
- [Source: prd.md#FR25 — daily cap visibility]

## Dev Agent Record
### Agent Model Used
### Debug Log References
### Completion Notes List
### File List
