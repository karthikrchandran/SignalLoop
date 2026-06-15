---
workflowType: sprint-change-proposal
date: "2026-05-28"
project: SignalLoop
module: bmm
trigger: "Post-sprint implementation gap review found missing setup UX and incomplete end-to-end automation wiring"
mode: batch
recommendedWorkflow: bmad-bmm-correct-course
recommendedAgent: Bob
---

# Sprint Change Proposal: SignalLoop Implementation Gaps

## 1. Issue Summary

The implementation phase is marked closed, but a post-sprint end-to-end review found a mismatch between planned MVP behavior and the currently operable product surface.

The main issue is not broad missing platform capability. The backend contains most of the core building blocks, but several operator-critical flows are incomplete at the integration and UI layers:

- Provider and system setup is backend-capable but not exposed through a usable admin setup surface.
- The current Sequences UI and Voice Agents UI do not reflect the backend capability expected by the MVP.
- The positive email reply automation path is not fully wired through to follow-up call scheduling.
- Governance controls still contain a stale API dependency.

This creates a release-risk gap between the sprint tracker's "done" state and the actual end-to-end operator experience.

### Evidence

- Provider credential APIs exist in `apps/api/app/api/routes/provider_credentials.py`, but no corresponding web UI was found.
- The Sequences page in `apps/web/src/features/sequences/SequencesPage.tsx` is local-state/mock-data driven rather than backend-backed.
- The Voice Agents page in `apps/web/src/features/voice/VoiceAgentsPage.tsx` behaves like a demo/prototype rather than a production setup console.
- `process_signal()` in `apps/api/app/domain/signals/trigger_service.py` is defined but not invoked from the signal creation path.
- Governance controls still save daily caps and quiet hours through `/api/v1/policies/`, which conflicts with the simplified backend direction.

## 2. Impact Analysis

### Epic Impact

- Epic 2: Email sequence engine
  - Story intent was delivered at the backend API/worker level, but operator-facing sequence management remains incomplete in the web app.
- Epic 3: AI voice pipeline
  - Script and provider-backed campaign setup exist in the backend, but the current frontend surface does not expose that operationally.
- Epic 4: Signal-driven actions and admin visibility
  - Automated follow-up triggers are not fully wired end to end.
  - Admin visibility is incomplete because setup, health, and operational dependencies are not surfaced in one place.
- Epic 5: Observability and KPIs
  - Release-readiness is weakened because operator troubleshooting still requires code-level knowledge and manual environment checks.

### PRD / Requirement Impact

The current gaps affect these MVP commitments in `_bmad-output/planning-artifacts/prd.md`:

- FR5: attach email sequences and voice scripts to a campaign
- FR9-FR13: governance settings and auditability
- FR-S1: positive email signals automatically trigger follow-up call plus demo email
- FR24-FR25: signal handling within the same operating cycle
- Release Gate 3: signal detection and follow-up automation
- Release Gate 4: governance controls working end to end

### Planning Artifact Conflict

- The active SignalLoop PRD, architecture, UX specification, and sprint tracker describe the email-sequence plus AI-voice MVP.
- The current `_bmad-output/planning-artifacts/epics.md` now describes the later ChatBot Hub track instead of the active SignalLoop MVP implementation slices.
- As a result, this corrective increment cannot safely rely on the current epic document as the authoritative source for reopening story work.
- For this change-control pass, the authoritative references are:
   - `_bmad-output/planning-artifacts/prd.md`
   - `_bmad-output/planning-artifacts/architecture.md`
   - `_bmad-output/planning-artifacts/ux-design-specification.md`
   - `_bmad-output/implementation-artifacts/sprint-status.yaml`
   - `_bmad-output/implementation-artifacts/final-sprint-summary.md`

This is a planning hygiene issue in addition to the implementation gaps.

### Architecture / UX Impact

- Architecture needs one more integration pass to ensure signal creation invokes follow-up actions deterministically.
- UX/design intent for non-technical admin operation is not currently met because setup is fragmented or missing.

### Technical Impact

- Additional API/UI integration work is required.
- At least one automation handoff requires backend code change.
- Focused regression and end-to-end tests are needed for the repaired orchestration path.

### Checklist Status Summary

#### Section 1 - Trigger and Context

- [x] 1.1 Trigger identified
   - Triggering completed slices: sequence management, script/voice management, automated follow-up triggers, admin visibility
- [x] 1.2 Core problem defined
   - Category: misunderstanding of delivered completeness plus technical integration gaps discovered during end-to-end review
- [x] 1.3 Evidence collected
   - Evidence includes missing provider setup UI, mock/local-state admin surfaces, stale governance endpoint usage, and missing trigger invocation wiring

#### Section 2 - Epic Impact

- [x] 2.1 Current epic viability assessed
   - The delivered MVP remains viable, but several claimed slices require correction before release-ready operation
- [x] 2.2 Epic-level changes identified
   - Recommended approach is a corrective increment rather than a full new epic structure
- [x] 2.3 Remaining epic dependency review completed
   - The gaps cut across formerly closed Epic 2 through Epic 5 capability areas
- [x] 2.4 Future-epic invalidation checked
   - No future SignalLoop MVP epic is invalidated; the issue is corrective completion, not direction change
- [x] 2.5 Order/priority checked
   - Priority should be: signal wiring, setup console, real sequence/voice UI, governance alignment, release-readiness validation

#### Section 3 - Artifact Conflict Analysis

- [x] 3.1 PRD conflict review completed
- [x] 3.2 Architecture conflict review completed
- [x] 3.3 UX conflict review completed
- [!] 3.4 Secondary artifact impact remains action-needed
   - The current `epics.md` does not match the active SignalLoop MVP track and should be reconciled as part of change tracking hygiene

#### Section 4 - Path Forward Evaluation

- [x] 4.1 Direct adjustment evaluated
   - Viable; effort medium; risk medium
- [x] 4.2 Rollback evaluated
   - Not viable; rollback would discard useful backend capability without solving operator-surface gaps efficiently
- [x] 4.3 PRD MVP review evaluated
   - Viable but unnecessary; MVP remains achievable without scope reduction
- [x] 4.4 Recommended path selected
   - Selected approach: Option 1, direct adjustment through Correct Course

#### Section 5 - Proposal Components

- [x] 5.1 Issue summary drafted
- [x] 5.2 Epic and artifact impact documented
- [x] 5.3 Path forward and rationale documented
- [x] 5.4 MVP impact and high-level action plan documented
- [x] 5.5 Agent handoff plan documented

#### Section 6 - Final Review and Handoff

- [x] 6.1 Checklist reviewed for completeness
- [x] 6.2 Proposal accuracy verified against inspected code and artifacts
- [ ] 6.3 User approval pending
- [ ] 6.4 Sprint status update pending approval
- [ ] 6.5 Final handoff confirmation pending approval

## 3. Recommended Approach

### Chosen Path

Direct adjustment through a change-control increment.

This should not be treated as a new product direction or a major replan. The product goals remain valid. The issue is that the current release surface does not fully satisfy the intended MVP workflow. The right response is a corrective increment that reopens a small number of implementation slices and updates the planning artifacts accordingly.

### Scope Classification

Moderate.

Reasoning:

- The change does not invalidate the PRD or architecture baseline.
- It does require backlog reorganization and explicit tracking because the sprint is already closed.
- The work spans product, frontend, backend integration, and release-readiness validation.

### Recommended BMAD Routing

- Primary workflow: `bmad-bmm-correct-course`
- Workflow code: `CC`
- Primary agent: Bob, Scrum Master
- Secondary handoff after approval:
  - John, Product Manager: update scope wording if stories or acceptance criteria are reopened
  - Winston, Architect: confirm the signal-trigger invocation and setup-surface boundaries
  - Amelia, Developer Agent: implement the approved corrective stories

## 4. Implementation Gap List

### P0 - Must close for real end-to-end operation

1. Signal trigger invocation is incomplete.
   - Gap: positive email reply signals are recorded, but automatic follow-up actions are not fully executed because the trigger service is not wired from the signal creation path.
   - Outcome needed: positive reply creates a call request and demo email action in the same operating cycle.

2. Provider and operations setup UI is missing.
   - Gap: there is no production admin screen for Twilio, SendGrid, Deepgram, Groq, sender identity, public callback/webhook status, or `TEAM_NOTIFICATION_EMAIL`.
   - Outcome needed: an operator can configure and verify the app without editing environment files manually.

3. Sequence management UI is not backend-backed.
   - Gap: the current Sequences page is mock/local-state driven.
   - Outcome needed: sequence CRUD, step editing, and campaign enrollment run against the real API.

4. Voice setup UI is not backend-backed.
   - Gap: the current Voice Agents page is a demo/prototype and does not expose real script management or operational setup.
   - Outcome needed: script CRUD, campaign linkage, and provider readiness are visible and actionable in the web app.

5. Governance controls contain a stale API dependency.
   - Gap: daily caps and quiet hours still save through `/api/v1/policies/`.
   - Outcome needed: either restore a supported persistence API or replace/remove the stale UI controls.

### P1 - Needed for operator confidence and supportability

6. Worker and webhook readiness is not surfaced operationally.
   - Gap: the app lacks a clear admin health surface showing API, workers, Redis/Postgres, webhook reachability, and callback base URL readiness.
   - Outcome needed: an operator can verify whether the system is actually runnable end to end.

7. Workspace-scoped provider credential strategy is inconsistent.
   - Gap: credential resolver support is stronger for Twilio and SendGrid than for Deepgram and Groq.
   - Outcome needed: either standardize env-only operation explicitly or add consistent workspace-scoped provider support.

8. End-to-end automated validation is incomplete.
   - Gap: there is no focused validation proving positive reply -> trigger -> call request -> post-call workflow.
   - Outcome needed: add narrow tests around the repaired orchestration path and fix the currently stale governance flow assertions.

### P2 - Tracking hygiene and release clarity

9. Story and status artifacts are inconsistent.
   - Gap: `sprint-status.yaml` is authoritative, but some story files still carry stale headers.
   - Outcome needed: normalize change tracking so implementation status is readable without forensic review.

10. Runtime prerequisites are under-documented in-product.
   - Gap: operational dependencies exist in docs, but not in the portal where operators expect them.
   - Outcome needed: surface setup prerequisites and verification checks inside the admin experience.

## 5. Detailed Change Proposals

### Proposed Corrective Story CC-1: Provider and Operations Setup Console

Add a real admin setup surface for provider credentials, sender/number configuration, team notification email, webhook URLs, callback base URL, and health/readiness checks.

Rationale: this closes the largest operator usability gap and aligns the product with the PRD expectation that non-technical admins can operate the system.

### Proposed Corrective Story CC-2: Sequence UI Integration

Replace the local-state Sequences page with a backend-backed sequence builder and campaign enrollment flow.

Rationale: sequence execution exists, but the operator path to manage it is incomplete.

### Proposed Corrective Story CC-3: Voice Script and Campaign Setup Integration

Replace the Voice Agents demo surface with backend-backed script management and campaign-level operational setup.

Rationale: voice capability exists in the backend, but the current UI does not provide the setup experience implied by the MVP.

### Proposed Corrective Story CC-4: Signal Automation Wiring

Wire signal creation to trigger execution so positive email replies automatically queue follow-up actions and record audit/timeline evidence.

Rationale: this is the main backend orchestration gap blocking the core automation claim.

### Proposed Corrective Story CC-5: Governance and Release-Readiness Alignment

Resolve the stale governance controls path, add focused end-to-end tests, and publish a release-readiness pass for the repaired flow.

Rationale: the current mismatch leaves the app buildable but not honestly release-ready.

## 6. Implementation Handoff

### Handoff Classification

Moderate change requiring Scrum Master coordination.

### Handoff Recipients

- Bob, Scrum Master
  - Open and track the corrective increment under `Correct Course (CC)`.
  - Decide whether to reopen affected stories or create a small corrective story set.

- John, Product Manager
  - Update PRD/epic wording only where current acceptance language overstates delivered operator completeness.

- Winston, Architect
  - Confirm the minimal architecture-safe path for signal invocation, provider configuration boundaries, and operations setup ownership.

- Amelia, Developer Agent
  - Implement the approved corrective stories and add focused validation.

### Success Criteria For The Corrective Increment

- A workspace admin can configure providers and verify operational readiness from the product UI.
- Sequence and voice setup pages use the real backend APIs.
- Positive email replies deterministically create the intended follow-up actions.
- Governance controls no longer depend on stale endpoints.
- Release-readiness can be demonstrated without relying on hidden manual knowledge.

## 7. Decision

Proceed with `Correct Course (CC)` using Bob as the primary agent.

This is the correct BMAD path because the sprint is closed, the change spans multiple delivered stories, and the work now needs formal change tracking rather than an ad hoc implementation patch list.

## 8. Approval and Final Handoff

### Approval Status

- User approval received on 2026-05-28
- Proposal status: approved

### Sprint Tracking Decision

- `sprint-status.yaml` is not being edited in this pass.
- Reason: no new epic structure is being introduced here; this approval authorizes a corrective increment and corrective story set rather than a new epic renumbering.
- Follow-up tracking should occur when Bob formalizes the corrective slice set for execution.

### Final Handoff

- Bob, Scrum Master
   - Own the approved Correct Course record.
   - Convert the corrective story set into the next execution queue.

- Winston, Architect
   - Validate the final implementation boundary for signal invocation, provider setup ownership, and health/status surface design.

- John, Product Manager
   - Reconcile any acceptance wording that currently overstates operator completeness.

- Amelia, Developer Agent
   - Implement corrective stories in priority order with focused regression coverage.

### Execution Order

1. Signal automation wiring
2. Provider and operations setup console
3. Backend-backed sequence management UI
4. Backend-backed voice script/setup UI
5. Governance endpoint alignment and release-readiness validation

Correct Course workflow complete.