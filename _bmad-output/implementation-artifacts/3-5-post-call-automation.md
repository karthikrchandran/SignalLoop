# Story 3.5: Post-Call Automation

Status: ready-for-dev

## Story

As a sales team member,
I want to receive an email summary after every AI call with transcript and next steps,
so that I can follow up on interested prospects without listening to recordings.

## Acceptance Criteria

1. **Given** a call completes **When** the postcall worker processes it **Then** a structured summary is generated within 60 seconds
2. **Given** the summary is generated **When** it is emailed to the team **Then** it includes: contact name/company, call duration, outcome, transcript summary, unanswered questions, and scheduling interest flag
3. **Given** the prospect expressed scheduling interest **When** the summary is sent **Then** the email prominently flags "SCHEDULING REQUESTED" and includes prospect details
4. **Given** the prospect had unanswered questions **When** the summary is sent **Then** the email lists each unanswered question for the team to prepare answers
5. **Given** the summary email is sent via SendGrid **When** delivery is tracked **Then** the send is logged in audit events
6. **Given** a call failed (no answer, busy, voicemail) **When** the postcall worker processes it **Then** a brief status update is logged (not a full summary email)
7. **Given** the postcall worker runs **When** it processes completed calls **Then** it updates CallSession.postcall_status to "summary_sent" or "skipped"

## Tasks / Subtasks

- [ ] Task 1: Create apps/workers/worker_app/postcall_worker.py (AC: 1,6,7)
  - [ ] Event-driven: triggered when CallSession.outcome is set to a terminal state
  - [ ] Or polling: check CallSessions WHERE outcome IS NOT NULL AND postcall_status IS NULL
  - [ ] For ANSWERED calls: generate summary, send email
  - [ ] For non-ANSWERED calls: log brief status, set postcall_status = "skipped"
- [ ] Task 2: Create summary generator in apps/api/app/domain/voice/summary_generator.py (AC: 1,2,3,4)
  - [ ] Input: CallSession (with transcript, unanswered_questions, scheduling_interest)
  - [ ] Output: structured summary with sections
  - [ ] Format as HTML email template:
    - Header: "Call Summary — {contact_name} at {company}"
    - Key metrics: duration, outcome
    - Transcript summary (first 500 chars or key points)
    - Unanswered questions list (highlighted)
    - Scheduling interest flag (prominent banner if true)
    - Link to full recording
- [ ] Task 3: Send summary email via SendGrid adapter (AC: 2,5)
  - [ ] To: configured team email address(es)
  - [ ] Subject: "[EngageHub] Call Summary — {contact_name}" or "[SCHEDULING] {contact_name} — interested"
  - [ ] HTML body from summary generator
  - [ ] Log audit event for send
- [ ] Task 4: Handle scheduling interest specially (AC: 3)
  - [ ] If scheduling_interest = true: create a scheduling request record in DB
  - [ ] Flag for manual action by sales team
- [ ] Task 5: Update CallSession.postcall_status (AC: 7)
  - [ ] After summary sent: postcall_status = "summary_sent"
  - [ ] After skip (non-answered): postcall_status = "skipped"
- [ ] Task 6: Write unit tests for summary generator (AC: 2,3,4)
- [ ] Task 7: Write integration test for postcall flow (mock SendGrid) (AC: 1,5,7)

## Dev Notes

- Postcall worker is the third worker process (alongside sequence_worker and call_worker)
- Summary generation should be fast — no LLM needed, just template + data formatting
- Team notification email address should be configurable (settings/env var)
- Keep summaries concise — sales team wants actionable info, not raw transcripts

### References
- [Source: architecture.md#Section-6 — postcall_worker process]
- [Source: architecture.md#Section-4 — Post-call summary and notification]
- [Source: prd.md#FR-V5 — unanswered question logging for team review]
- [Source: prd.md#FR-V6 — scheduling intent detection]

## Dev Agent Record
### Agent Model Used
### Debug Log References
### Completion Notes List
### File List
