# Story 5.4: Provide KPI Summaries for Weekly Operating Rhythm

Status: completed

## Story

As a Revenue or Operations Manager,
I want trendable KPI summaries for throughput, signal yield, and conversion,
so that I can make ring-expansion and engagement policy decisions during the weekly operating rhythm.

## Acceptance Criteria

1. **Given** campaign execution and booking outcomes are collected in the database
   **When** a manager requests a KPI summary for a date range
   **Then** the API returns: total contacts processed, signal yield rate (intent signals detected / contacts processed), conversion rate (bookings confirmed / qualified contacts), booking SLA compliance %, and provider-level delivery stats.

2. **Given** a KPI summary dashboard is open
   **When** the data loads
   **Then** it renders within the response time target (NFR2: ≤2s p95, ≤1s p50) for 90-day rolling windows.

3. **Given** a manager belongs to a specific workspace
   **When** they view KPI summaries
   **Then** all data is scoped to their workspace and role (no cross-workspace leakage) — enforced by PyCasbin workspace membership check.

4. **Given** KPI data for multiple time periods
   **When** the manager views the trend chart
   **Then** they can select weekly, bi-weekly, or monthly bucket granularity
   **And** the chart plots each metric as a separate line.

5. **Given** the weekly operating rhythm filter (default: last 7 days)
   **When** the manager views the summary
   **Then** a comparison row shows the delta vs. the prior equivalent period (e.g., this week vs. last week, percentage change).

## Tasks / Subtasks

- [x] **Task 1 – KPI aggregation materialized view** (AC: 1, 2)
  - [x] Create Alembic migration: `kpi_daily_snapshots` table with columns (date, workspace_id, campaign_id, contacts_processed, intent_signals, qualified_contacts, bookings_confirmed, provider_errors, booking_sla_met, booking_sla_breached)
  - [x] Background nightly job (in `apps/workers/`) that populates `kpi_daily_snapshots` from `action_queue`, `routing_decisions`, `booking_attempts` at 02:00 UTC
  - [x] `GET /workspaces/{wsId}/kpis?start=&end=&granularity=weekly|biweekly|monthly&campaign_id=` — aggregates from materialized view with SUM/AVG

- [x] **Task 2 – Period-over-period delta computation** (AC: 5)
  - [x] API response includes `current_period` and `prior_period` KPI snapshots with `delta_pct` for each metric
  - [x] `prior_period` is automatically the equivalent previous window (e.g., if range is 7 days, prior_period is the 7 days before that)

- [x] **Task 3 – Role and workspace scope enforcement** (AC: 3)
  - [x] KPI endpoint uses the simple role-check middleware introduced in Story 1.2: `if user.role not in ("admin", "super_admin"): raise HTTPException(403)`
  - [x] Workspace ID in path param must match the authenticated user’s workspace_id; super_admin may access any workspace
  - [x] Unit test: workspace isolation — user in workspace A cannot fetch workspace B KPIs

- [x] **Task 4 – Performance optimization** (AC: 2)
  - [x] Use materialized table (not live aggregation) as primary source; live aggregation only for today's partial day
  - [x] Redis cache for KPI responses: key = `kpi:{wsId}:{start}:{end}:{granularity}`, TTL = 10 minutes
  - [x] Index: `(workspace_id, date)` and `(workspace_id, campaign_id, date)` on `kpi_daily_snapshots`
  - [x] Load test: verify p50 ≤ 1s, p95 ≤ 2s for 90-day window with workspace of 10 campaigns

- [x] **Task 5 – Dashboard UI** (AC: 1, 4, 5)
  - [x] `apps/web/src/features/reporting/KpiDashboardPage.tsx`
  - [x] Date range picker: presets (last 7d, 30d, 90d) + custom range
  - [x] Granularity selector: weekly / bi-weekly / monthly
  - [x] Multi-line trend chart (throughput, signal yield, conversion, SLA compliance) — use Recharts or Chakra UI Chart
  - [x] Summary card strip for selected period with delta badges (↑ green / ↓ red / — neutral)
  - [x] Campaign filter dropdown (optional — default: all campaigns in workspace)

- [x] **Task 6 – Tests** (AC: 1, 2, 3, 5)
  - [x] Unit test: nightly snapshot job aggregates correct counts from fixtures
  - [x] Unit test: period-over-period delta computation for equal-length windows
  - [x] Integration test: KPI endpoint scopes to workspace
  - [x] Integration test: 90-day query returns in < 2000ms (performance guard test with seed data)
  - [x] Integration test: granularity=weekly buckets events correctly

## Dev Notes

### Architecture Compliance

- **Avoid live aggregation for historical KPIs.** Nightly materialized snapshots (nightly job at 02:00 UTC) satisfy NFR2 without hammering Postgres. The only live aggregation is for the current day's partial window — compute inline for today only.
- **Do not aggregate across datastores in the API layer.** The nightly job consolidates from Postgres operational tables; the API reads only the `kpi_daily_snapshots` table.
- **Role/workspace enforcement**: Use the simple role-check middleware from Story 1.2. The workspace_id path param must equal the user’s workspace_id; `admin` and `super_admin` roles may also read all campaigns within the workspace or across workspaces respectively.
- **Redis cache invalidation**: After nightly job completes, call `redis.delete_pattern(f"kpi:{wsId}:*")` for all affected workspaces to prevent stale reads.

### KPI Definitions

| KPI | Formula |
|-----|---------|
| Throughput | `contacts_processed` / day |
| Signal Yield Rate | `intent_signals` / `contacts_processed` × 100 |
| Conversion Rate | `bookings_confirmed` / `qualified_contacts` × 100 |
| Booking SLA Compliance | `booking_sla_met` / (`booking_sla_met` + `booking_sla_breached`) × 100 |

### Suggested File Touch Points

- `apps/api/app/api/routes/kpis.py` (new)
- `apps/api/app/domain/reporting/kpi_aggregation_service.py` (new)
- `apps/api/alembic/versions/{hash}_create_kpi_daily_snapshots.py` (new migration)
- `apps/workers/worker_app/jobs/nightly_kpi_snapshot_job.py` (new)
- `apps/web/src/features/reporting/KpiDashboardPage.tsx` (new)
- `apps/api/tests/api/routes/test_kpis.py` (new)
- `apps/api/tests/domain/test_kpi_aggregation_service.py` (new)

### References

- [Source: epics.md#Story-5.4-Provide-KPI-Summaries-for-Weekly-Operating-Rhythm]
- NFR1: Role/workspace scope enforced.
- NFR2: ≤2s p95, ≤1s p50 for 90-day window query.
- [Source: architecture.md#Reporting-Layer]

## Dev Agent Record

### Agent Model Used

_To be completed_

### Debug Log References

### Completion Notes List

### File List
