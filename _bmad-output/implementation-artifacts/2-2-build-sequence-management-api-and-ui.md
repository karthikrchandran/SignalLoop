# Story 2.2: Build Sequence Management API and UI

Status: ready-for-dev

## Story

As a marketing admin,
I want to create and manage multi-step email sequences through the web UI,
so that I can build automated email campaigns with different content at each step.

## Acceptance Criteria

1. **Given** I am an authenticated admin **When** I POST /api/v1/sequences with name and campaign_id **Then** a new EmailSequence is created and returned
2. **Given** a sequence exists **When** I PUT /api/v1/sequences/{id}/steps with an array of steps **Then** steps are created/updated with correct ordering and delay_days
3. **Given** a sequence has steps **When** I GET /api/v1/sequences/{id} **Then** the sequence and all its steps are returned in order
4. **Given** I am on the Sequences page **When** I click "New Sequence" **Then** I see a form with name, campaign selector, and a vertical timeline step builder
5. **Given** I am building a sequence **When** I add steps **Then** each step has: subject line, body editor with personalization tokens ({{first_name}}, {{company}}), and delay days from previous step
6. **Given** a sequence is configured **When** I click preview **Then** I see what a recipient would see at each step with sample data
7. **Given** a campaign has a sequence **When** I POST /api/v1/campaigns/{id}/activate **Then** the campaign activates and contacts are enrolled in the sequence with status ACTIVE

## Tasks / Subtasks

- [ ] Task 1: Create apps/api/app/api/routes/sequences.py with CRUD endpoints (AC: 1,2,3)
  - [ ] POST /api/v1/sequences — create
  - [ ] GET /api/v1/sequences — list (filterable by campaign_id)
  - [ ] GET /api/v1/sequences/{id} — detail with steps
  - [ ] PUT /api/v1/sequences/{id} — update name/active
  - [ ] PUT /api/v1/sequences/{id}/steps — batch upsert steps
  - [ ] DELETE /api/v1/sequences/{id} — soft delete
- [ ] Task 2: Create SequenceService in apps/api/app/domain/sequences/service.py (AC: 1,2,3,7)
  - [ ] create_sequence, update_sequence, add_steps, get_with_steps
  - [ ] activate_campaign: enroll all campaign contacts as ACTIVE with next_send_at = now for step 1
- [ ] Task 3: Register routes in the main router (AC: 1)
- [ ] Task 4: Create Sequence Builder page component in frontend (AC: 4,5)
  - [ ] Vertical timeline layout with step cards
  - [ ] Each card: subject input, rich text body editor, delay days input
  - [ ] Personalization token insertion buttons
  - [ ] Add/remove/reorder step controls
- [ ] Task 5: Create sequence preview component (AC: 6)
  - [ ] Show rendered email with sample contact data at each step
- [ ] Task 6: Add campaign activation endpoint that enrolls contacts (AC: 7)
- [ ] Task 7: Write API tests for sequence CRUD and campaign activation (AC: all)

## Dev Notes

- Vertical timeline layout per UX spec — each step is a card on a vertical line
- Personalization tokens: {{first_name}}, {{last_name}}, {{company}}, {{title}} — merge from contact record
- Campaign activation creates ContactSequenceState for each campaign contact

### References
- [Source: ux-design-specification.md#Section-5.3 — Sequence Builder screen]
- [Source: architecture.md#Section-5 — Email Sequence Engine flow]
- [Source: prd.md#FR14 — multi-step sequences, FR15 — personalization tokens]

## Dev Agent Record
### Agent Model Used
### Debug Log References
### Completion Notes List
### File List
