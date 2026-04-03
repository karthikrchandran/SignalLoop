# Story 5.2: Capture Immutable Operational Audit Trail

Status: backlog

## Story

As a compliance and operations stakeholder,
I want all significant user and system actions audit-logged with immutable records,
so that accountability, investigation, and regulatory compliance are reliable and supportable.

## Acceptance Criteria

1. **Given** any operationally significant action occurs (campaign activation, policy change, approval submission, governance override, state transition)
   **When** the action is committed
   **Then** a tamper-resistant audit record is written to MongoDB `audit_events` collection with: actor_id, actor_role, action_type, target_resource, correlation_id, timestamp, and summary_payload.

2. **Given** audit records exist for a workspace
   **When** an authorized admin queries the audit log
   **Then** records are filterable by: actor, action_type, date range, correlation_id
   **And** results are returned paginated with accurate total count.

3. **Given** audit records are retained
   **When** a retention policy window is configured (1-10 years per NFR22)
   **Then** records older than the window can be exported to CSV/JSON on demand
   **And** the export completes within 2 hours for up to the maximum configured window (NFR22).

4. **Given** an audit record is written
   **When** any subsequent process reads it
   **Then** the record is identical to the original write (no mutation, no soft-delete hiding)
   **And** any attempt to modify an existing audit record is rejected at the infrastructure level.

## Tasks / Subtasks

- [ ] **Task 1 – Audit event schema and MongoDB collection** (AC: 1, 4)
  - [ ] Define `AuditEvent` Pydantic model: {event_id, actor_id, actor_role, workspace_id, action_type, target_resource_type, target_resource_id, correlation_id, timestamp, summary_payload_json}
  - [ ] Create MongoDB `audit_events` collection with `(workspace_id, timestamp)` compound index
  - [ ] Enforce append-only at application layer: no update/delete calls; document MongoDB collection-level write concern

- [ ] **Task 2 – Audit event writer utility** (AC: 1, 4)
  - [ ] Extend `apps/api/app/infrastructure/db/mongodb/mongo_schema.py` with `append_audit_event(event: AuditEvent)` function
  - [ ] Called from: governance routes, approval routes, progression service, campaign activation, policy changes (already partially in place from 1.4)

- [ ] **Task 3 – Audit log query API** (AC: 2)
  - [ ] `GET /workspaces/{wsId}/audit-log?actor=&action_type=&from=&to=&correlation_id=&page=&limit=`
  - [ ] Backed by MongoDB query with pagination using `skip`/`limit` or cursor-based (prefer cursor for large datasets)
  - [ ] Requires `admin` role

- [ ] **Task 4 – Audit export endpoint** (AC: 3)
  - [ ] `POST /workspaces/{wsId}/audit-log/export` — initiates async export job (JSON or CSV)
  - [ ] Returns job_id; poll `GET /workspaces/{wsId}/audit-log/export/{jobId}` for status/download URL
  - [ ] Export uses streaming to avoid memory pressure for large windows

- [ ] **Task 5 – Audit coverage sweep** (AC: 1)
  - [ ] Verify `append_audit_event` is called from ALL significant action surfaces:
    - [x] Governance policy create/update (1.4)
    - [x] Approval submit/approve/reject (1.4)
    - [ ] Campaign activate/pause/archive
    - [ ] Template publish
    - [ ] Suppression add/remove
    - [ ] Routing rule create/update
    - [ ] Booking state change
  - [ ] Add missing calls where not yet wired

- [ ] **Task 6 – Tests** (AC: 1, 2, 3, 4)
  - [ ] Unit test: audit event written with all required fields
  - [ ] Unit test: audit query with date filter returns correct subset
  - [ ] Integration test: admin can query own workspace audit log
  - [ ] Integration test: cross-workspace audit access denied

## Dev Notes

### Architecture Compliance

- MongoDB `audit_events` is the single authoritative source for the audit trail. Do NOT duplicate audit records in PostgreSQL.
- Write concern for audit events: `{w: "majority", j: true}` — ensure durability before returning.
- Never soft-delete or update audit records. Do not add `deleted_at` or `is_active` to the collection.
- Actor identity comes from the JWT token; always resolve actor_id and actor_role from the current request context.
- For export: use MongoDB's cursor streaming + incremental write to S3/local temp storage. Do NOT load entire result set into memory.

### Action Type Registry

Use snake_case string constants for action_type:
- `campaign_activated`, `campaign_paused`, `campaign_archived`
- `policy_created`, `policy_updated`
- `approval_submitted`, `approval_approved`, `approval_rejected`
- `template_published`, `template_cloned`
- `suppression_added`, `suppression_removed`
- `routing_rule_created`, `routing_rule_updated`
- `contact_state_transitioned`
- `booking_confirmed`, `booking_escalated`
- `global_pause_applied`, `global_resume_applied`

### Suggested File Touch Points

- `apps/api/app/infrastructure/db/mongodb/mongo_schema.py` (extend append_audit_event)
- `apps/api/app/api/routes/audit_log.py` (new)
- `apps/api/app/domain/audit/audit_export_service.py` (new)
- `apps/api/tests/api/routes/test_audit_log.py` (new)

### References

- [Source: epics.md#Story-5.2-Capture-Immutable-Operational-Audit-Trail]
- [Source: architecture.md#Data-Architecture]
- NFR21: Operationally significant actions must be audit-logged.
- NFR22: Audit records must support 1-10 year retention and export within 2 hours.

## Dev Agent Record

### Agent Model Used

_To be completed_

### Debug Log References

### Completion Notes List

### File List
