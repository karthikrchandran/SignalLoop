# Story 4.5: Sequence Monitor

Status: ready-for-dev

## Story

As a marketing admin,
I want to see how contacts are progressing through each email sequence,
so that I can identify bottlenecks and understand campaign effectiveness.

## Acceptance Criteria

1. **Given** a sequence has enrolled contacts **When** I view the sequence monitor **Then** I see a visual timeline showing contacts at each step
2. **Given** contacts have different states **When** the breakdown is displayed **Then** I see counts for: active (at each step), paused (signal detected), stopped (bounce/unsub), completed
3. **Given** a contact has a positive signal **When** it is displayed **Then** the contact shows the signal type and triggered followup actions
4. **Given** I want per-contact detail **When** I click on a contact **Then** I see: current step number, next send time, signal history, and followup actions taken
5. **Given** the sequence has overall metrics **When** they are displayed **Then** I see: total enrolled, completion rate, average time to complete, signal detection rate

## Tasks / Subtasks

- [ ] Task 1: Create sequence progress API endpoint GET /api/v1/sequences/{id}/progress (AC: 1,2,5)
  - [ ] Returns: step-by-step breakdown with contact counts per status
  - [ ] Per step: step_order, step_subject, contacts_at_step, contacts_completed_step
  - [ ] Overall: total_enrolled, active_count, paused_count, stopped_count, completed_count
  - [ ] Metrics: completion_rate, avg_completion_days, signal_rate
- [ ] Task 2: Create sequence contacts list endpoint GET /api/v1/sequences/{id}/contacts (AC: 3,4)
  - [ ] Returns: paginated list of ContactSequenceState with contact info
  - [ ] Include: current_step, next_send_at, status, signal_type, signal_detected_at
  - [ ] Filter by: status (active/paused/stopped/completed)
- [ ] Task 3: Create Sequence Monitor frontend page (AC: 1,2)
  - [ ] Visual timeline: horizontal or vertical step progression with contact count bubbles
  - [ ] Step labels showing subject and delay
  - [ ] Color-coded status indicators (green=active, yellow=paused, red=stopped, blue=completed)
- [ ] Task 4: Create contact state breakdown panel (AC: 2,3)
  - [ ] Pie or bar chart showing status distribution
  - [ ] Paused contacts list with signal details
  - [ ] Stopped contacts list with reason (bounce/unsub)
- [ ] Task 5: Create contact detail view (AC: 4)
  - [ ] Click on contact → show: current step, next send time, all signals, followup actions
  - [ ] Link to call review if voice signals exist
- [ ] Task 6: Create overall sequence metrics display (AC: 5)
  - [ ] KPI cards: total enrolled, completion rate, signal rate, avg completion time
- [ ] Task 7: Write API tests for progress and contacts endpoints (AC: 1,2)
- [ ] Task 8: Write frontend component tests (AC: 1,3)

## Dev Notes

- Sequence progress is the primary way admins understand email campaign health
- Visual timeline should clearly show where contacts are "stuck" or pausing
- Consider loading this view incrementally if sequence has many contacts (pagination)

### References
- [Source: ux-design-specification.md#Section-5.6 — Sequence Monitor screen]
- [Source: prd.md#FR24 — campaign visibility]
- [Source: prd.md#FR25 — sequence progress monitoring]

## Dev Agent Record
### Agent Model Used
### Debug Log References
### Completion Notes List
### File List
