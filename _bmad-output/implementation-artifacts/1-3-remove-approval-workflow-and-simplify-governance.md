# Story 1.3: Remove Approval Workflow and Simplify Governance

Status: ready-for-dev

## Story

As a marketing admin,
I want templates to publish directly without an approval gate,
so that I can quickly create and activate campaigns without unnecessary workflow steps.

## Acceptance Criteria

1. **Given** routes/approvals.py exists **When** it is deleted **Then** no /api/v1/approvals endpoints exist
2. **Given** domain/policies/approval_service.py exists **When** it is deleted **Then** no approval workflow logic remains
3. **Given** governance policies exist **When** they are simplified **Then** only daily_cap and quiet_hours governance checks remain
4. **Given** templates required approval before publishing **When** the gate is removed **Then** templates can be published directly with an audit log entry
5. **Given** PolicyApprovalRequest model exists **When** it and related models are removed **Then** Alembic migration drops the table

## Tasks / Subtasks

- [ ] Task 1: Delete apps/api/app/api/routes/approvals.py (AC: 1)
- [ ] Task 2: Delete apps/api/app/domain/policies/approval_service.py (AC: 2)
- [ ] Task 3: Remove approval-related routes from router registration (AC: 1)
- [ ] Task 4: Simplify governance service to daily_cap + quiet_hours checks only (AC: 3)
- [ ] Task 5: Remove approval gate from template/campaign publish flow (AC: 4)
- [ ] Task 6: Create Alembic migration to drop PolicyApprovalRequest and related tables (AC: 5)
- [ ] Task 7: Run pytest (AC: 1)

## Dev Notes

- Keep governance as a simple cap-check service: check_daily_cap(channel, count) and is_quiet_hours(timezone)
- Templates go straight from draft → active with audit log
### References
- [Source: prd.md#FR12 — daily send caps per channel]
- [Source: prd.md#FR13 — quiet hours enforcement]

## Dev Agent Record
### Agent Model Used
### Debug Log References
### Completion Notes List
### File List
