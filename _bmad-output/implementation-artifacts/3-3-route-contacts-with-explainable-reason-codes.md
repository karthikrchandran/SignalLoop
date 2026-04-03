# Story 3.3: Route Contacts with Explainable Reason Codes

Status: backlog

## Story

As a Marketing Ops Admin,
I want routing decisions to include explicit reason codes so that I can trust and verify every system-driven state change.

## Acceptance Criteria

1. **Given** a classified signal with `confidence_tier = medium | strong`
   **When** the routing engine evaluates the contact
   **Then** the contact is moved deterministically to nurture, booking, or handoff path based on the active routing rules
   **And** the routing decision is recorded with: next_state, reason_code, rule_reference, signal_id, confidence_tier.

2. **Given** multiple routing rules could apply to a contact
   **When** the router evaluates conditions
   **Then** rules are evaluated in priority order (configured by operator)
   **And** the first matching rule wins; no contacts are double-routed.

3. **Given** a routing decision is made
   **When** the decision record is stored
   **Then** the reason code and rule reference are accessible via the contact timeline API
   **And** the UX timeline surface shows: action card, reason code badge, rule name, template applied (if any).

4. **Given** a signal with `confidence_tier = weak | none`
   **When** the routing engine evaluates the contact
   **Then** no routing state transition is triggered
   **And** the weak signal is logged with `triggered_routing = false`.

## Tasks / Subtasks

- [ ] **Task 1 – Routing rule model and migration** (AC: 1, 2)
  - [ ] Add `routing_rules` table (workspace_id, name, priority, condition_json, target_state, is_active, created_by, updated_at)
  - [ ] Add `routing_decisions` table (contact_id, campaign_id, signal_id, applied_rule_id, next_state, reason_code, decided_at, confidence_tier)
  - [ ] Add Alembic migration

- [ ] **Task 2 – Routing rules API** (AC: 2)
  - [ ] `GET /workspaces/{wsId}/routing-rules`
  - [ ] `POST /workspaces/{wsId}/routing-rules`
  - [ ] `PATCH /workspaces/{wsId}/routing-rules/{ruleId}`
  - [ ] Priority reorder endpoint: `POST /workspaces/{wsId}/routing-rules/reorder`

- [ ] **Task 3 – Routing engine** (AC: 1, 2, 4)
  - [ ] `apps/api/app/domain/routing/routing_engine.py`
  - [ ] Load active rules by priority
  - [ ] Evaluate contact+signal against condition expression (MVP: simple field-comparison JSON grammar)
  - [ ] On match: create routing decision record, call `progression_service.transition_contact_state`
  - [ ] On no match: log signal with `triggered_routing = false`

- [ ] **Task 4 – Timeline exposure** (AC: 3)
  - [ ] Extend `GET /contacts/{contactId}/timeline` to include routing decisions with reason code and rule name
  - [ ] Ensure MongoDB event for routing decision includes all required UI fields

- [ ] **Task 5 – Tests** (AC: 1, 2, 3, 4)
  - [ ] Unit test: medium-confidence signal triggers routing to booking
  - [ ] Unit test: weak-confidence signal produces no routing decision
  - [ ] Unit test: priority ordering — higher priority rule wins over lower
  - [ ] Integration test: routing decision appears in contact timeline

## Dev Notes

### Architecture Compliance

- Routing engine is part of the `routing` domain module. Do NOT put routing logic in the worker or route handlers.
- Condition JSON grammar (MVP): `{"field": "contact.industry", "op": "equals", "value": "technology"}`. Do not eval() or exec() condition strings — use a safe interpreter.
- Target states from routing: `nurture`, `booking`, `handed_off`. Confirm only legal transitions per progression_service._ALLOWED_TRANSITIONS.
- Reason codes for routing: `STRONG_SIGNAL_BOOKING_TRIGGER`, `MEDIUM_SIGNAL_NURTURE_CONTINUE`, `RULE_MATCH_{RULE_NAME}`.

### UX Requirements (UX-DR2, UX-DR3)

- Timeline card format: `{action_type} → {reason_code} → {template_applied}`
- Routing decisions must be human-readable in the UI; reason_code must map to a human label.
- Support detail drill-down: click on action → slide-out showing rule name, signal summary, confidence tier.

### Suggested File Touch Points

- `apps/api/app/domain/routing/routing_engine.py` (new)
- `apps/api/app/domain_models.py` (add RoutingRule, RoutingDecision)
- `apps/api/app/api/routes/routing_rules.py` (new)
- `apps/api/app/api/routes/contacts.py` (extend timeline endpoint)
- `apps/api/app/alembic/versions/*_add_routing_tables.py` (new)
- `apps/api/tests/domain/test_routing_engine.py` (new)
- `apps/web/src/features/contacts/ContactTimelinePage.tsx` (update timeline cards)

### References

- [Source: epics.md#Story-3.3-Route-Contacts-with-Explainable-Reason-Codes]
- [Source: architecture.md#Data-Architecture]
- [Source: architecture.md#Agent-Consistency-Rules]
- [Source: ux-design-specification.md#UX-DR2]
- [Source: ux-design-specification.md#UX-DR3]

## Dev Agent Record

### Agent Model Used

_To be completed_

### Debug Log References

### Completion Notes List

### File List
