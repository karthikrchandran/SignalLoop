---
workflowType: corrective-story-set
date: "2026-05-28"
project: EngageHub
sourceProposal: "_bmad-output/planning-artifacts/sprint-change-proposal-2026-05-28-implementation-gaps.md"
status: approved
---

# Corrective Story Set: EngageHub Implementation Gaps

## Purpose

This corrective story set captures the approved change-control increment for the post-sprint implementation gaps discovered during the EngageHub end-to-end review.

These stories do not replace the original EngageHub MVP direction. They close the remaining gap between the planned MVP behavior and the currently operable admin and automation surface.

## Scope Classification

Moderate corrective increment.

## Story Set

### CC-1: Wire Signal Detection to Trigger Execution

Related prior slice:
- Story 4.2: Automated Followup Triggers

Problem:
- Trigger rules exist, but positive email reply handling is not clearly invoking the trigger execution path in production flow.

Story:
As a marketing admin,
I want positive email signals to immediately execute their configured follow-up actions,
so that interested prospects move into the next action state without manual intervention.

Acceptance Criteria:
1. Given a positive email reply is ingested through the SendGrid webhook, when the signal event is created, then trigger execution is invoked in the same operating cycle.
2. Given the default trigger rule for `email_positive_reply` is enabled, when the signal is processed, then a follow-up call request is queued and a demo email action is recorded.
3. Given trigger execution succeeds, when the contact timeline and audit log are viewed, then the signal source and triggered actions are visible with correlation context.
4. Given trigger execution fails for one action, when the failure occurs, then the failure is logged and visible without silently dropping the signal.
5. Given regression tests run, when the repaired signal path is exercised, then the test covers webhook -> signal -> trigger -> queued follow-up action.

Notes:
- Keep the fix in the existing signal domain and webhook ingestion flow.
- Do not add a new orchestration subsystem.

### CC-2: Build Provider and Operations Setup Console

Related prior slices:
- Story 4.3: Campaign Operations Dashboard
- Story 4.5: Sequence Monitor
- operational setup documentation in `docs/operations/provider-setup.md`

Problem:
- Backend capability exists for provider credentials and runtime configuration, but there is no usable in-product setup surface.

Story:
As a workspace admin,
I want a provider and operations setup console,
so that I can configure and verify SendGrid, Twilio, Deepgram, Groq, and team notification settings without editing environment files manually.

Acceptance Criteria:
1. Given I am an admin, when I open the setup console, then I can view the configured status of SendGrid, Twilio, Deepgram, Groq, and team notification email.
2. Given provider credential APIs already exist, when I save supported provider credentials, then the UI uses the real provider credential endpoints and masked values are returned.
3. Given the app depends on public callback URLs, when I open the setup console, then I see the expected SendGrid webhook URL and Twilio callback/media-stream base URLs.
4. Given runtime dependencies matter for operability, when I open the setup console, then I see a health/readiness summary for API, workers, Postgres, Redis, and webhook/callback readiness.
5. Given a required operational value is missing, when the page renders, then the missing prerequisite is called out with a clear action message.

Notes:
- This story should define a single operator-facing setup home instead of scattering provider setup across unrelated pages.

### CC-3: Replace Mock Sequence UI with Backend-Backed Management

Related prior slice:
- Story 2.2: Build Sequence Management API and UI

Problem:
- The backend sequence API exists, but the current Sequences page is still local-state/mock-data driven.

Story:
As a marketing admin,
I want the Sequences page to manage real sequences against the backend,
so that I can create, edit, preview, and enroll campaign sequences through the actual product flow.

Acceptance Criteria:
1. Given the Sequences page loads, when I view it, then the page reads real sequences from the backend instead of hardcoded sample data.
2. Given I create or edit a sequence, when I save it, then the page uses the real sequence CRUD and step upsert endpoints.
3. Given a sequence is attached to a campaign, when I activate or enroll contacts, then real `ContactSequenceState` rows are created through the backend flow.
4. Given I preview a sequence, when preview data is shown, then it reflects backend sequence content and supported personalization tokens.
5. Given sequence API validation fails, when the error returns, then the page surfaces a clear operator-facing error instead of silently mutating local state.

Notes:
- Preserve the existing page route where practical.
- Favor incremental integration over a full visual redesign.

### CC-4: Replace Demo Voice Setup UI with Backend-Backed Script and Campaign Setup

Related prior slice:
- Story 3.1: Script and Knowledge Base Management

Problem:
- The backend script capability exists, but the current Voice Agents page behaves like a demo/prototype rather than a real setup flow.

Story:
As a marketing admin,
I want the voice setup experience to manage real scripts and campaign voice readiness,
so that I can prepare AI calling campaigns through the product UI.

Acceptance Criteria:
1. Given the Voice Agents page loads, when I view it, then the page reads real script data from the backend instead of relying on demo-only state.
2. Given I create or edit a script, when I save it, then the UI uses the real script CRUD endpoints and preview flow.
3. Given a campaign needs a voice script, when I configure voice setup, then I can see and select the active script associated with the campaign.
4. Given provider readiness affects voice execution, when I view the page, then missing Twilio, Deepgram, or Groq prerequisites are surfaced clearly.
5. Given script parsing fails or backend validation rejects content, when that happens, then the UI surfaces the issue and prevents a misleading saved state.

Notes:
- This story is about production setup, not browser-side speech demo behavior.

### CC-5: Align Governance Controls and Release-Readiness Validation

Related prior slices:
- Story 1.3: Remove approval workflow and simplify governance
- Story 1.4: Remove legacy CRUD and out-of-scope UI
- Story 4.5: Sequence Monitor

Problem:
- The Controls page still posts some values to a stale `/api/v1/policies/` endpoint path, and the repaired flow lacks a focused release-readiness validation pass.

Story:
As an operator and release owner,
I want governance controls and release-readiness checks to reflect the actual backend,
so that the app can be validated honestly for end-to-end use.

Acceptance Criteria:
1. Given an operator updates daily caps or quiet hours, when they save, then the UI uses a supported backend path or the unsupported control is removed/replaced.
2. Given the governance simplification pivot remains in effect, when the controls page is reviewed, then it no longer suggests unsupported policy behavior.
3. Given the repaired signal and setup flows are in place, when focused validation runs, then there is a documented behavior-scoped test or validation pass for the end-to-end happy path.
4. Given release-readiness is reported, when the summary is produced, then it distinguishes implemented capability from environmental prerequisites and known operational caveats.

Notes:
- This story closes the mismatch between buildability and true release readiness.

## Recommended Execution Order

1. CC-1: Wire Signal Detection to Trigger Execution
2. CC-2: Build Provider and Operations Setup Console
3. CC-3: Replace Mock Sequence UI with Backend-Backed Management
4. CC-4: Replace Demo Voice Setup UI with Backend-Backed Script and Campaign Setup
5. CC-5: Align Governance Controls and Release-Readiness Validation

## Handoff

- Bob: own the corrective increment and queue these stories
- Winston: validate architecture boundaries before implementation starts
- John: adjust any acceptance wording that overstates current delivery
- Amelia: implement stories in order with focused validation after each slice