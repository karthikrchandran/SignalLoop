# Story 4.2: Automated Followup Triggers

Status: ready-for-dev

## Story

As a marketing admin,
I want the system to automatically take followup actions when positive signals are detected,
so that interested prospects get immediate attention without manual intervention.

## Acceptance Criteria

1. **Given** a positive email signal is detected **When** the trigger fires **Then** a followup call is queued in call_worker AND a demo links email is sent via SendGrid
2. **Given** a voice call detects scheduling interest **When** the trigger fires **Then** a scheduling request record is created AND the sales team is emailed with prospect details
3. **Given** a positive call without scheduling interest **When** the trigger fires **Then** a follow-up resource email is sent to the prospect
4. **Given** trigger rules exist **When** an admin views them **Then** they can see which triggers are enabled/disabled
5. **Given** an admin disables a trigger **When** a matching signal occurs **Then** the disabled trigger does not fire
6. **Given** any automated action fires **When** it completes **Then** an audit trail entry records the trigger, signal source, and action taken

## Tasks / Subtasks

- [ ] Task 1: Create apps/api/app/domain/signals/trigger_service.py (AC: 1,2,3,6)
  - [ ] TriggerService class with process_signal(signal_event) method
  - [ ] Rule engine: match signal_type → list of actions
  - [ ] Default rules:
    - email_positive_reply → [queue_followup_call, send_demo_email]
    - scheduling_requested → [create_scheduling_request, email_sales_team]
    - voice_positive_interest → [send_resource_email]
  - [ ] Execute each action, log audit event per action
- [ ] Task 2: Implement followup call queueing action (AC: 1)
  - [ ] Create CallRequest with trigger_reason="positive_email_signal"
  - [ ] Schedule for next available slot via call_worker
- [ ] Task 3: Implement demo links email action (AC: 1)
  - [ ] Send pre-configured demo links email template to prospect via SendGrid
  - [ ] Template includes: product demo link, calendar booking link
- [ ] Task 4: Implement scheduling request creation (AC: 2)
  - [ ] Create SchedulingRequest model: contact_id, campaign_id, signal_event_id, status (PENDING/CONTACTED/BOOKED/DECLINED), created_at
  - [ ] Send notification email to configured sales team address
- [ ] Task 5: Implement resource email action (AC: 3)
  - [ ] Send pre-configured follow-up resources email to prospect
- [ ] Task 6: Create trigger rules API (AC: 4,5)
  - [ ] GET /api/v1/triggers — list trigger rules with enabled/disabled status
  - [ ] PUT /api/v1/triggers/{id} — enable/disable a trigger
  - [ ] Store trigger rules in DB or config
- [ ] Task 7: Write audit trail entries for all automated actions (AC: 6)
- [ ] Task 8: Write unit tests for trigger service (AC: 1,2,3)
- [ ] Task 9: Write integration tests for signal→trigger→action flow (AC: 1,2,3,6)

## Dev Notes

- Triggers run synchronously when a signal is detected (in the same worker process)
- Keep trigger rules simple — no complex rule engine needed for MVP
- Demo links and resource email templates should be admin-configurable (but can start with hardcoded for MVP)

### References
- [Source: architecture.md#Section-5 — signal actions and email sequence engine links]
- [Source: prd.md#FR-S1 — positive email triggers followup call + demo email]
- [Source: prd.md#FR-S2 — voice scheduling creates request + team notification]

## Dev Agent Record
### Agent Model Used
### Debug Log References
### Completion Notes List
### File List
