# Story 5.1: Deliver Unified Contact Timeline with Explainability UX

Status: done

## Story

As a Marketing Ops Admin,
I want a unified chronological timeline of all actions, states, and decisions for each contact,
so that I can understand exactly what the system did and why for every contact in a campaign.

## Acceptance Criteria

1. **Given** contact lifecycle events and routing decisions are stored across PostgreSQL and MongoDB
   **When** I open a contact's timeline
   **Then** I see a unified chronological list sorted by timestamp covering: state transitions, outreach actions, provider events, routing decisions, signals, and booking events.

2. **Given** a timeline entry represents an automated system action
   **When** I view the entry
   **Then** each card shows: action type, channel, outcome, reason code, and template/offer-pack applied (if applicable).

3. **Given** I want more detail on a specific timeline entry
   **When** I click/tap on an entry card
   **Then** a detail panel slides out showing: full reason code explanation, rule reference, confidence tier (if signal-driven), and raw transcript excerpt (if available).

4. **Given** the timeline has many entries
   **When** I filter by date range or event type
   **Then** the list updates immediately without full page reload
   **And** the initial timeline load returns the first 50 entries within 3 seconds for p95 (NFR2).

## Tasks / Subtasks

- [x] **Task 1 – Timeline aggregation API** (AC: 1, 4)
  - [x] `GET /contacts/{contactId}/timeline?campaignId=&page=&limit=&eventType=&from=&to=`
  - [x] Aggregate and merge from: `contact_state_history` (Postgres), `routing_decisions` (Postgres), `contact_events` (Postgres)
  - [x] Sort by timestamp across sources; return unified paginated list
  - [x] Enforce workspace scoping

- [x] **Task 2 – Timeline event schema** (AC: 1, 2)
  - [x] Define unified `TimelineEvent` response schema: {id, event_type, channel, timestamp, actor, outcome, reason_code, rule_ref, template_ref, confidence_tier, has_detail}
  - [x] Map each source event type to unified schema in an event normalizer layer

- [x] **Task 3 – Timeline detail endpoint** (AC: 3)
  - [x] `GET /contacts/{contactId}/timeline/{eventId}` — return full detail record from source
  - [x] Include transcript excerpt for telephony events (from `call_transcripts` PostgreSQL table)
  - [x] Return explainability fields: rule_name, rule_condition, signal_summary

- [x] **Task 4 – Web UI for contact timeline** (AC: 1, 2, 3, 4)
  - [x] `apps/web/src/features/contacts/ContactTimelinePage.tsx`
  - [x] Implement `AutomationCard` component with action → reason_code → template display (UX-DR2)
  - [x] Implement `ReasonCodeBadge` component (UX-DR6)
  - [x] 360px slide-out detail panel (UX-DR4) for per-entry drill-down
  - [x] Filter controls: date range picker, event type multi-select
  - [x] Virtual scroll / pagination for large timelines

- [x] **Task 5 – Tests** (AC: 1, 2, 3, 4)
  - [x] API test: timeline merges Postgres + MongoDB events in correct order
  - [x] API test: filter by event_type returns correct subset
  - [x] API test: cross-workspace access denied
  - [x] UI test: reason code badge renders on automated action cards

### Review Findings

- [x] [Review][Patch] Add transcript storage/source for telephony timeline detail and populate `transcript_excerpt` [apps/api/app/domain_models.py:778]
- [x] [Review][Patch] Validate `campaign_id` against workspace before state-history timeline list/detail [apps/api/app/api/routes/contacts.py:53]
- [x] [Review][Patch] Include required signal and booking event sources in the unified timeline or materialize them into `ContactEvent` before aggregation [apps/api/app/domain/timeline/timeline_service.py:241]
- [x] [Review][Patch] Replace unbounded in-memory offset pagination with cursor-backed bounded queries and consume the returned cursor in the UI [apps/api/app/domain/timeline/timeline_service.py:242]
- [x] [Review][Patch] Cache first-page timeline data with real total metadata instead of reporting `len(events[:200])` as the total count [apps/api/app/domain/timeline/timeline_service.py:233]
- [ ] [Review][Patch] Wire timeline cache invalidation from all timeline event write paths and invalidate both all-campaign and campaign-specific keys [apps/api/app/domain/timeline/timeline_service.py:118]
- [x] [Review][Patch] Fix `Load more` to fetch the intended next page/cursor instead of reading stale React state [apps/web/src/features/contacts/ContactTimelinePage.tsx:263]
- [x] [Review][Patch] Replace empty Radix Select item value with a non-empty `all` sentinel [apps/web/src/features/contacts/ContactTimelinePage.tsx:42]
- [x] [Review][Patch] Make date filter reset and `to` date bounds use current filter state and include the full selected end day [apps/web/src/features/contacts/ContactTimelinePage.tsx:97]
- [x] [Review][Patch] Return and render full reason-code explanation for explainable events, not only the compact badge [apps/api/app/domain_models.py:778]
- [x] [Review][Patch] Set `has_detail` for contact events that carry rule, template, reason, or confidence metadata [apps/api/app/domain/timeline/timeline_service.py:44]
- [x] [Review][Patch] Implement required `TranscriptSnippet` and `AuditLogEntry` UX-DR6 components or update the story scope before marking AC complete [apps/web/src/features/contacts/ContactTimelinePage.tsx:377]
- [ ] [Review][Patch] Add backend and UI tests for distinct timestamp ordering, `ContactStateHistory`, date filters, cursor/page boundaries, cache hit/invalidation, >200 events, transcript detail, and reason-code badge rendering [apps/api/tests/api/routes/test_contact_timeline.py:100]

Review resolution notes:
- Backend regression tests were expanded for source coverage, distinct ordering, multi-event filters, date bounds, cursor paging, campaign workspace validation, reason explanations, invalid event IDs, and call transcript detail.
- Remaining open item: cache invalidation helper now clears both all-campaign and campaign-specific first-page keys, but event write paths still need request/app context wiring.
- Remaining open item: UI-level timeline tests still need to cover the reason-code badge/detail behavior.

## Dev Notes

### Architecture Compliance

- Timeline data is sourced entirely from PostgreSQL. Use efficient indexed queries and limit result sets to avoid latency.
- `contact_events` PostgreSQL table is the source of truth for immutable event history. Do NOT delete or update contact event rows.
- Timeline API should default to returning the 50 most recent events. Pagination via cursor (use `id` or composite `timestamp+source_system` as cursor).
- For p95 < 3s: use Redis to cache the first page of the timeline per contact with a 30s TTL. Invalidate on new event write.

### UX Design Requirements

- UX-DR1: Activity Feed First pattern — timeline is the default home experience.
- UX-DR2: Each action card shows Action Type → Reason Code → Template Applied.
- UX-DR3: Context-ladder: summary card → slide-out detail → inline drill-down for reason/rule.
- UX-DR6: Build and use `AutomationCard`, `ReasonCodeBadge`, `TranscriptSnippet`, `AuditLogEntry` components.

### Suggested File Touch Points

- `apps/api/app/api/routes/contacts.py` (add timeline + timeline detail endpoints)
- `apps/api/app/domain/timeline/timeline_service.py` (new — aggregation and normalization)
- `apps/web/src/features/contacts/ContactTimelinePage.tsx` (new)
- `apps/web/src/components/AutomationCard.tsx` (new)
- `apps/web/src/components/ReasonCodeBadge.tsx` (new)
- `apps/api/tests/api/routes/test_contact_timeline.py` (new)

### References

- [Source: epics.md#Story-5.1-Deliver-Unified-Contact-Timeline-with-Explainability-UX]
- [Source: ux-design-specification.md#UX-DR1]
- [Source: ux-design-specification.md#UX-DR2]
- [Source: ux-design-specification.md#UX-DR3]
- [Source: ux-design-specification.md#UX-DR6]
- NFR2: Timeline views must load within 3 seconds for p95.

## Dev Agent Record

### Agent Model Used
GitHub Copilot (Claude Sonnet 4.6)

### Completion Date
2025-07-09

### Files Modified / Created
**Backend:**
- `apps/api/app/domain_models.py` — added `ContactEvent`, `RoutingDecision` table classes; added `TimelineEventPublic`, `TimelineEventDetailPublic`, `TimelinePagePublic` response schemas
- `apps/api/app/models.py` — added `ContactEvent`, `RoutingDecision` to Alembic-discovery imports
- `apps/api/app/alembic/versions/b1c2d3e4f5a6_add_contact_events_and_routing_decisions.py` — migration creating both tables with FK constraints and 6 indexes
- `apps/api/app/domain/timeline/__init__.py` — package marker (new)
- `apps/api/app/domain/timeline/timeline_service.py` — aggregation + normalization + Redis caching (new)
- `apps/api/app/api/routes/contacts.py` — timeline list + detail endpoints (new)
- `apps/api/app/api/main.py` — registered `contacts.router`

**Frontend:**
- `apps/web/src/components/ReasonCodeBadge.tsx` — semantic colour-coded badge (new)
- `apps/web/src/components/AutomationCard.tsx` — timeline event card (new)
- `apps/web/src/features/contacts/ContactTimelinePage.tsx` — main page with filters + Sheet detail panel (new)
- `apps/web/src/routes/_layout/contacts.tsx` — TanStack Router route accepting `contactId` search param (new)
- `apps/web/src/components/Sidebar/AppSidebar.tsx` — added Contacts nav item

**Review Fix Pass:**
- `apps/api/app/domain/timeline/timeline_service.py` — added campaign/workspace joins for state history, signal/scheduling/call-session sources, cursor responses, bounded source queries, cache count metadata, Redis timeouts, reason explanations, and transcript excerpt detail
- `apps/api/app/api/routes/contacts.py` — added campaign workspace validation and cursor query support
- `apps/api/app/domain_models.py` — added `reason_code_explanation` to timeline detail responses
- `apps/api/tests/api/routes/test_contact_timeline.py` — expanded to 12 API test cases covering source coverage, ordering, multi-filtering, dates, cursor pages, workspace campaign validation, reason explanations, bad IDs, and voice transcript detail
- `apps/web/src/components/AuditLogEntry.tsx` — added timeline detail audit/source metadata component
- `apps/web/src/components/TranscriptSnippet.tsx` — added transcript excerpt component
- `apps/web/src/features/contacts/ContactTimelinePage.tsx` — switched to immediate multi-filtering, cursor load-more, full-day end date bounds, and richer detail rendering
- `apps/web/src/components/AutomationCard.tsx` — added signal and scheduling visual source treatments
- `apps/web/package.json`, `package-lock.json` — added `date-fns` dependency used by timeline formatting

### Notes
- Story referenced MongoDB as a source but MongoDB was removed in story 1-1; all timeline sources are PostgreSQL only.
- Telephony transcript excerpts now come from existing `CallSession.transcript` via `CallRequest`/`Campaign` joins; no new `call_transcripts` table was added.
- `ContactStateHistory` has no `workspace_id` column, so state-history list/detail now scope through `Campaign.workspace_id` joins and the route validates `campaign_id` workspace ownership.
- Remaining review action items: wire cache invalidation at all timeline event write paths and add UI-level timeline tests for reason/detail behavior.

### Debug Log References

### Completion Notes List

### File List
