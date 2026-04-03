# Story 3.4: Call Scheduling and Daily Cap Worker

Status: ready-for-dev

## Story

As a system operator,
I want an automated worker that schedules and initiates outbound calls throughout the day,
so that 50 cold calls are made daily without manual intervention.

## Acceptance Criteria

1. **Given** the worker is running **When** it polls every 30 seconds **Then** it checks the daily call count and queries the call queue for due CallRequests
2. **Given** the daily cap is set to 50 **When** 50 calls have been made today **Then** no more calls are initiated until the next day
3. **Given** calls are queued **When** they are distributed **Then** they are spread across available hours (not all at once)
4. **Given** quiet hours are configured (e.g., before 9am or after 6pm recipient timezone) **When** the current time is in quiet hours **Then** calls are deferred
5. **Given** a CallRequest is due **When** the worker processes it **Then** it creates a CallSession, initiates the call via Twilio adapter, and updates the CallRequest status to IN_PROGRESS
6. **Given** a campaign is activated with a voice script **When** contacts are enrolled **Then** CallRequests are created with trigger_reason = "campaign_activation"
7. **Given** a positive email signal is detected **When** a followup call is triggered **Then** a CallRequest is created with trigger_reason = "positive_email_signal"

## Tasks / Subtasks

- [ ] Task 1: Create apps/workers/worker_app/call_worker.py (AC: 1,2,3,4,5)
  - [ ] Main loop: poll every 30s
  - [ ] Daily cap check: COUNT CallRequests WHERE DATE(created_at) = TODAY AND status != FAILED
  - [ ] Due query: SELECT * FROM call_request WHERE status = 'QUEUED' AND scheduled_at <= NOW() ORDER BY scheduled_at LIMIT 5
  - [ ] For each due request: create CallSession, call TwilioVoiceAdapter.initiate_call(), update status
- [ ] Task 2: Implement call distribution algorithm (AC: 3)
  - [ ] Given 50 calls and 9 available hours (9am-6pm): ~5.5 calls/hour, ~1 every 11 minutes
  - [ ] When campaign activates: distribute CallRequest.scheduled_at evenly across available hours
  - [ ] Add small random jitter (±2 minutes) to avoid predictable patterns
- [ ] Task 3: Implement quiet hours enforcement (AC: 4)
  - [ ] Check contact timezone (or UTC fallback) against quiet hours config
  - [ ] If in quiet hours: skip, leave scheduled_at unchanged
- [ ] Task 4: Implement campaign activation call enrollment (AC: 6)
  - [ ] When campaign activates with voice_script_id: create CallRequest for each contact
  - [ ] Set scheduled_at using distribution algorithm from Task 2
  - [ ] Set trigger_reason = "campaign_activation"
- [ ] Task 5: Implement signal-triggered call creation (AC: 7)
  - [ ] Listen for positive_email_signal events
  - [ ] Create CallRequest with trigger_reason = "positive_email_signal"
  - [ ] Set scheduled_at = next available slot (not quiet hours)
- [ ] Task 6: Add worker entry point and compose configuration (AC: 1)
- [ ] Task 7: Write unit tests for distribution algorithm and cap check (AC: 2,3)
- [ ] Task 8: Write integration test for full call scheduling cycle (mock Twilio) (AC: 1,5)

## Dev Notes

- Worker runs as separate process alongside sequence_worker
- 50 calls/day = ~5-6 calls per hour across a 9-hour window
- Distribution prevents overwhelming Twilio or having all calls bunch up
- Call worker should be idempotent — if it crashes and restarts, it should not double-dial
- Use SELECT ... FOR UPDATE SKIP LOCKED to prevent parallel workers from double-processing

### References
- [Source: architecture.md#Section-6 — call_worker process]
- [Source: architecture.md#Section-4 — Call scheduling and daily cap]
- [Source: prd.md#FR-V7 — daily call cap (50)]
- [Source: prd.md#FR-V8 — timezone-aware quiet hours]
- [Source: prd.md#FR-S1 — positive email triggers followup call]

## Dev Agent Record
### Agent Model Used
### Debug Log References
### Completion Notes List
### File List
