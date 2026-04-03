# Story 4.3: Generate Context-Rich Sales Handoff Packet

Status: backlog

## Story

As a Sales Engineer,
I want a handoff packet that includes the full contact interaction timeline, intent rationale, and key signals,
so that I can run an effective demo without needing to re-discover information already gathered by outreach.

## Acceptance Criteria

1. **Given** a contact reaches `handed_off` or `confirmed` state
   **When** the handoff packet is generated
   **Then** it includes: contact profile, chronological interaction timeline, classified signals with confidence tiers, top detected objections/keywords, and call transcript excerpts.

2. **Given** an authorized sales user accesses the handoff surface
   **When** they request the packet
   **Then** they can see contact context, intent rationale, and booking confirmation details
   **And** the packet is scoped to the sales user's authorized workspace (no cross-workspace leakage).

3. **Given** template and offer-pack context exists for the campaign
   **When** the packet is generated
   **Then** it includes: templates used, guardrails applied, and personalization values resolved for this contact.

4. **Given** the SE provides feedback on the handoff quality
   **When** feedback is submitted
   **Then** it is stored and linked to the handoff packet and contact record
   **And** feedback is visible to admin users for template improvement loops (UX-DR12, UX-DR13).

## Tasks / Subtasks

- [ ] **Task 1 – Handoff packet domain model** (AC: 1, 2, 3)
  - [ ] Add `handoff_packets` table (contact_id, campaign_id, booking_attempt_id, generated_at, packet_json, workspace_id)
  - [ ] Add `handoff_feedback` table (packet_id, submitted_by, rating, feedback_text, submitted_at)
  - [ ] Add Alembic migration

- [ ] **Task 2 – Handoff packet generation service** (AC: 1, 3)
  - [ ] `apps/api/app/domain/bookings/handoff_service.py`
  - [ ] `generate_handoff_packet(contact_id, campaign_id, booking_attempt_id)` — aggregate:
    - Contact profile (from `contacts` table)
    - Interaction timeline (from MongoDB `contact_events` collection, sorted by timestamp)
    - Signal artifacts with confidence tiers and reason codes
    - Transcript excerpts (top 3 by signal strength)
    - Template/offer-pack context for campaign
    - Booking confirmation details
  - [ ] Persist packet as JSON in `handoff_packets` table

- [ ] **Task 3 – Handoff packet API** (AC: 2, 4)
  - [ ] `GET /contacts/{contactId}/handoff-packet?campaignId=` — workspace-scoped, requires `sales_engineer` role
  - [ ] `POST /contacts/{contactId}/handoff-packet/feedback` — submit SE feedback
  - [ ] `GET /workspaces/{wsId}/handoff-feedback` — admin view of feedback entries (requires `admin` role)

- [ ] **Task 4 – Web UI for SE handoff surface** (AC: 2, 3, 4)
  - [ ] `apps/web/src/features/handoff/HandoffPacketPage.tsx` — SE view: contact card, timeline, signals, transcripts, booking details
  - [ ] Feedback widget at bottom of packet page (rating 1-5 + comment)
  - [ ] Admin: feedback list in template management area

- [ ] **Task 5 – Tests** (AC: 1, 2, 3, 4)
  - [ ] Unit test: packet generator assembles all required sections
  - [ ] Unit test: cross-workspace access is denied
  - [ ] Integration test: feedback submitted links to packet and contact

## Dev Notes

### Architecture Compliance

- Packet generation reads from both PostgreSQL (contact, campaign, booking, signals) and MongoDB (event timeline). Use parallel async queries where possible.
- The packet `packet_json` column stores the final assembled JSON for fast retrieval — do not regenerate on every request.
- Regenerate the packet on: new signal artifact added, booking state update, or explicit SE refresh request.
- SE feedback is a soft input and must NOT modify the contact progression state.
- Role: `sales_engineer` role must be added to Casbin bootstrap policies if not already present.

### Packet Structure

```json
{
  "contact": {"id", "email", "firstName", "company", "timezone"},
  "campaign": {"id", "name"},
  "booking": {"confirmed_at", "provider_ref", "booked_time"},
  "signals": [{"signal_type", "confidence_tier", "detected_at", "reason_code"}],
  "timeline": [{"action_type", "channel", "timestamp", "reason_code", "template_used"}],
  "transcripts": [{"excerpt", "call_date", "signal_keywords"}],
  "templates_used": [{"template_name", "version", "guardrails_passed"}]
}
```

### UX Requirements (UX-DR11, UX-DR12, UX-DR13)

- SE handoff UX includes: context packet, objections/transcript highlights, handoff readiness indicator.
- Feedback captures what worked/didn't for template improvement loop.
- 30-day outcome visibility for template improvements (Template Insights) — this surface is a later enhancement; feedback storage now enables it.

### Suggested File Touch Points

- `apps/api/app/domain/bookings/handoff_service.py` (new)
- `apps/api/app/domain_models.py` (add HandoffPacket, HandoffFeedback)
- `apps/api/app/api/routes/handoff.py` (new)
- `apps/api/app/alembic/versions/*_add_handoff_tables.py` (new)
- `apps/web/src/features/handoff/HandoffPacketPage.tsx` (new)
- `apps/api/tests/domain/test_handoff_service.py` (new)

### References

- [Source: epics.md#Story-4.3-Generate-Context-Rich-Sales-Handoff-Packet]
- [Source: ux-design-specification.md#UX-DR11]
- [Source: ux-design-specification.md#UX-DR12]
- [Source: ux-design-specification.md#UX-DR13]

## Dev Agent Record

### Agent Model Used

_To be completed_

### Debug Log References

### Completion Notes List

### File List
