# QA Test Summary — Sprint Corrective Stories CC-3, CC-4, CC-5

**Scope:** All corrective stories (CC-3, CC-4, CC-5) — backend API routes and frontend E2E  
**QA Engineer:** Quinn  
**Date:** 2025-07-10  
**Result:** ✅ All new tests passing

---

## Overall Results

| Suite | File | Tests | Result |
|---|---|---|---|
| CC-5 Backend — Governance uniqueness | `apps/api/tests/api/routes/test_controls.py` | 18 / 18 | ✅ Pass |
| CC-3 Frontend E2E — Sequences | `apps/web/tests/sequences.spec.ts` | 6 / 6 | ✅ Pass |
| CC-4 Frontend E2E — Voice scripts | `apps/web/tests/voice-agents.spec.ts` | 6 / 6 | ✅ Pass |

**Total new tests added this sprint: 30** (18 backend + 12 frontend)

---

## CC-5: Governance Uniqueness — Backend

**Story:** Ensure `GlobalControlState` enforces partial unique index constraints so duplicate pause/resume operations do not create extra rows.

**File:** `apps/api/tests/api/routes/test_controls.py`  
**Run command:** `uv run pytest tests/api/routes/test_controls.py -v` (from `apps/api/`)  
**Result:** 18 / 18 passed (1.54s)

### New tests added (lines ~400–480)

| Test | Assertion |
|---|---|
| `test_pause_campaign_idempotent_no_duplicate_row` | Pausing the same campaign twice yields exactly 1 `GlobalControlState` row for that `workspace_id + campaign_id` pair |
| `test_global_and_campaign_states_are_independent` | A global pause and a campaign pause in the same workspace produce 2 separate rows (one with `campaign_id IS NULL`, one with `campaign_id` set) |
| `test_pause_same_workspace_different_campaigns_independent` | Pausing two different campaigns in the same workspace yields 2 rows with distinct `campaign_id` values |

These tests directly exercise the two partial unique indexes:
- `uq_global_control_state_workspace_global` — unique on `(workspace_id)` WHERE `campaign_id IS NULL`
- `uq_global_control_state_workspace_campaign` — unique on `(workspace_id, campaign_id)` WHERE `campaign_id IS NOT NULL`

---

## CC-3: Sequence CRUD — Frontend E2E

**Story:** Sequence management UI (create, edit, delete, enroll) wired to real backend endpoints.

**File:** `apps/web/tests/sequences.spec.ts`  
**Run command:** `npx playwright test sequences.spec.ts --no-deps --project=chromium` (from `apps/web/`)  
**Result:** 6 / 6 passed

### Test inventory

| Test | What it covers |
|---|---|
| Sequences page loads and shows the sequence list | GET `/api/v1/sequences/` + detail + progress; list renders, selected sequence steps visible |
| Create new sequence opens dialog, submits, and shows success feedback | POST `/api/v1/sequences/` + PUT `.../steps`; dialog open/fill/submit flow; "Sequence created." feedback |
| Edit existing sequence sends PUT and shows success feedback | PUT `/api/v1/sequences/:id`; dialog pre-filled with existing data; "Sequence updated." feedback |
| Delete sequence sends DELETE and removes item from list | DELETE `/api/v1/sequences/:id`; "Sequence deleted." feedback; item removed from sidebar |
| Enroll contacts calls enroll endpoint and shows feedback | POST `/api/v1/sequences/:id/enroll`; "Enrolled 3 contacts." message from API |
| API error on load shows error alert | GET returns 500; error alert visible, no crash |

### Key implementation notes
- All tests use mock routes (`page.route`) — no live server required.
- Auth bypassed via `localStorage.setItem("access_token", "e2e-test-token")`.
- Step form fields (subject + body template) must be non-empty for the create submit to pass validation.

---

## CC-4: Voice Script CRUD — Frontend E2E

**Story:** Voice script management UI (create, edit, deactivate) and readiness card display.

**File:** `apps/web/tests/voice-agents.spec.ts`  
**Run command:** `npx playwright test voice-agents.spec.ts --no-deps --project=chromium` (from `apps/web/`)  
**Result:** 6 / 6 passed

### Test inventory

| Test | What it covers |
|---|---|
| Voice Setup page shows scripts and readiness cards when fully configured | GET `/api/v1/scripts/` + `/api/v1/voice/readiness`; script list and 3 "configured" readiness cards |
| Readiness cards show warning state when integrations are not configured | Readiness endpoint returns all `configured: false`; warning badges visible |
| Create new script opens dialog, submits POST, and shows success feedback | POST `/api/v1/scripts/`; dialog open/fill/submit; "Script created." feedback |
| Edit existing script sends PUT and shows success feedback | PUT `/api/v1/scripts/:id`; pre-filled dialog; "Script updated." feedback |
| Deactivate script sends DELETE and shows feedback | DELETE `/api/v1/scripts/:id`; "Script deactivated." feedback |
| API error on voice page load shows error alert | GET returns 500; error alert visible, no crash |

---

## Pre-existing Backend Coverage (no gaps found)

The gap analysis at the start of this sprint confirmed adequate coverage already existed for:

- **CC-3 sequences API:** `apps/api/tests/api/routes/test_sequences.py` — CRUD, step upsert, enrollment, 404 handling
- **CC-4 scripts API:** `apps/api/tests/api/routes/test_scripts.py` — CRUD, status transitions, 404 handling  
- **CC-5 pause/resume (non-uniqueness):** `apps/api/tests/api/routes/test_controls.py` (existing 15 tests) — global pause/resume, per-campaign pause/resume, unknown campaign 404

No changes were needed to these files beyond the 3 new CC-5 uniqueness tests.

---

## Regression Risk

Low. All new tests use full route isolation (mock handlers) on the frontend and database-rollback fixtures on the backend. No shared mutable state between test cases.
