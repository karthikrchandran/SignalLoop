# Story 4.4: Call Review Screen

Status: ready-for-dev

## Story

As a marketing admin or sales team member,
I want to review individual call recordings, transcripts, and unanswered questions,
so that I can evaluate AI call quality and follow up on specific prospect interactions.

## Acceptance Criteria

1. **Given** calls have been made **When** I navigate to Call Log **Then** I see a filterable table with: contact name, date, duration, outcome, signal type, scheduling status
2. **Given** filters are available **When** I filter by campaign, date range, outcome, or signal **Then** the table updates accordingly
3. **Given** I click on a call **When** the detail panel opens **Then** I see: audio player for recording, full transcript, list of unanswered questions, and signal/scheduling details
4. **Given** a call has unanswered questions **When** I view them **Then** each question is displayed as a separate item that can be marked as "answered" or "needs followup"
5. **Given** I want to take manual action **When** I click action buttons **Then** I can: send demo email to prospect, flag for sales team, pause contact's sequence

## Tasks / Subtasks

- [ ] Task 1: Create call list API endpoint GET /api/v1/calls (AC: 1,2)
  - [ ] Returns paginated list of CallSessions with joined contact info
  - [ ] Filter parameters: campaign_id, outcome, date_from, date_to, has_signal, scheduling_interest
  - [ ] Sort by: created_at desc (default), duration, outcome
- [ ] Task 2: Create call detail API endpoint GET /api/v1/calls/{id} (AC: 3,4)
  - [ ] Returns: CallSession with full transcript, recording_url, unanswered_questions array, scheduling_interest, signal events
- [ ] Task 3: Create Call Log frontend page (AC: 1,2)
  - [ ] Table columns: Contact, Campaign, Date/Time, Duration, Outcome, Signal, Scheduling
  - [ ] Filter bar: campaign dropdown, date range picker, outcome dropdown, signal checkbox
  - [ ] Pagination controls
- [ ] Task 4: Create Call Detail side panel (AC: 3,4)
  - [ ] Audio player: play recording from Twilio recording URL
  - [ ] Transcript section: scrollable text with timestamps
  - [ ] Unanswered questions section: list with action buttons
  - [ ] Signal/scheduling info: prominent display
- [ ] Task 5: Implement manual action buttons (AC: 5)
  - [ ] "Send Demo Email" → triggers demo email via SendGrid to the contact
  - [ ] "Flag for Sales" → creates a flag/note visible in contact signals
  - [ ] "Pause Sequence" → sets ContactSequenceState.status = PAUSED for this contact
  - [ ] Each action logged in audit trail
- [ ] Task 6: Write API tests for call list and detail endpoints (AC: 1,2,3)
- [ ] Task 7: Write frontend component tests (AC: 3,4)

## Dev Notes

- Twilio recording URLs are accessible via authenticated Twilio API — may need to proxy through our API
- Transcript is stored in CallSession.transcript as text — no special formatting needed for MVP
- Unanswered questions are stored as JSONB array in CallSession
- Audio player can use standard HTML5 `<audio>` element with Twilio recording URL

### References
- [Source: ux-design-specification.md#Section-5.5 — Call Log screen]
- [Source: prd.md#FR31 — call review with recording playback]
- [Source: prd.md#FR32 — transcript review]
- [Source: prd.md#FR33 — manual followup actions]

## Dev Agent Record
### Agent Model Used
### Debug Log References
### Completion Notes List
### File List
