# SignalLoop Autonomous B2B Sales Agent — Supervised-First Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a provider-independent, supervised B2B sales agent that turns existing workspace evidence into explainable proposals, approved simulated attempts, and reconciled outcomes.

**Architecture:** Add a dedicated `sales_agent` domain rather than extending Lead Preparation into an orchestration layer. It records immutable signals, runs, proposals, decisions, attempts, and outcomes; it reads existing shared contacts, prospecting snapshots, campaign/offer-pack data, and policies. The first release creates no external side effects. It is the first vertical slice of the longer enterprise plan in `2026-08-09-revenueos-enterprise-implementation-plan.md`, not a replacement for its tenancy, consent, knowledge, and production-hardening work.

**Tech Stack:** FastAPI, SQLModel, Alembic, PostgreSQL, pytest, Ruff, mypy; React 19, TypeScript, TanStack Router, Vite, Playwright.

---

## Scope and hard boundaries

- The agent may propose `EMAIL_DRAFT` and `FOLLOW_UP_TASK` only.
- `APPROVE` creates a `SIMULATED` attempt record and audit event. It does not call SendGrid, Twilio, Calendly, or eCRM.
- A contact with `do_not_contact`, `suppressed`, or explicit `consent=False` is `BLOCKED`; a contact without a company or usable email is `NEEDS_RESEARCH`.
- The run is deterministic from persisted inputs. There is no LLM call, model training, web scraping, or provider dependency in this slice.
- Every read and write has a workspace predicate.

## File and module map

| Responsibility | Files |
|---|---|
| State model and migration | `apps/api/app/domain/sales_agent/models.py`, `apps/api/app/alembic/versions/sales_agent_20260809_add_supervised_loop.py`, `apps/api/app/models.py` |
| Deterministic proposal engine | `apps/api/app/domain/sales_agent/service.py`, `apps/api/app/domain/sales_agent/schemas.py` |
| HTTP boundary | `apps/api/app/api/routes/sales_agent.py`, `apps/api/app/api/main.py` |
| API/domain tests | `apps/api/tests/domain/sales_agent/test_models.py`, `apps/api/tests/domain/sales_agent/test_service.py`, `apps/api/tests/api/routes/test_sales_agent.py` |
| UI and browser test | `apps/web/src/features/sales-agent/api.ts`, `apps/web/src/features/sales-agent/SalesAgentWorkspacePage.tsx`, `apps/web/src/routes/_layout/sales-agent.tsx`, `apps/web/tests/sales-agent.spec.ts` |

## Milestones and gates

~~~mermaid
flowchart LR
    M0[Baseline] --> M1[Supervised agent loop]
    M1 --> G1{Gate 1: no-key local loop}
    G1 --> M2[Approved email execution]
    M2 --> G2{Gate 2: email readiness}
    G2 --> M3[Cross-product outcomes]
    M3 --> G3{Gate 3: reconciliation}
    G3 --> M4[Consented voice callbacks]
    M4 --> G4{Gate 4: voice safety}
    G4 --> M5[Policy-granted autonomy]
    M5 --> G5{Gate 5: operational autonomy}
~~~

### Gate 0: baseline and working-tree protection

**Files:**

- Create: `docs/operations/sales-agent-baseline.md`

- [ ] **Step 1: Record the exact source and dirty-tree baseline.**

~~~powershell
git status --short
git rev-parse --short HEAD
uv run --project apps/api pytest apps/api/tests/domain/test_prospecting_service.py apps/api/tests/api/routes/test_prospecting.py -q
npm --workspace frontend run build
~~~

Record command, exit status, duration, commit SHA, and database availability. Do not stage pre-existing untracked files.

- [ ] **Step 2: Commit only the baseline note.**

~~~powershell
git add docs/operations/sales-agent-baseline.md
git commit -m "docs: record sales agent baseline"
~~~

**Exit condition:** baseline failures are named and reproducible; none is attributed to this work.

### Task 1: Define the supervised-agent persistence contract

**Files:**

- Create: `apps/api/tests/domain/sales_agent/test_models.py`
- Create: `apps/api/app/domain/sales_agent/models.py`
- Modify: `apps/api/app/models.py`
- Create: `apps/api/app/alembic/versions/sales_agent_20260809_add_supervised_loop.py`

- [ ] **Step 1: Write model contract tests before implementing models.**

~~~python
from app.domain.sales_agent.models import (
    AgentActionType,
    AgentAttemptStatus,
    AgentProposalStatus,
)


def test_supervised_agent_enums_do_not_include_external_dispatch() -> None:
    assert AgentActionType.email_draft.value == "EMAIL_DRAFT"
    assert AgentActionType.follow_up_task.value == "FOLLOW_UP_TASK"
    assert AgentAttemptStatus.simulated.value == "SIMULATED"
    assert "SENT" not in {item.value for item in AgentAttemptStatus}
    assert AgentProposalStatus.ready_for_review.value == "READY_FOR_REVIEW"
~~~

- [ ] **Step 2: Run the focused test and verify that imports fail.**

~~~powershell
uv run --project apps/api pytest apps/api/tests/domain/sales_agent/test_models.py -q
~~~

Expected: FAIL with `ModuleNotFoundError: No module named 'app.domain.sales_agent'`.

- [ ] **Step 3: Implement the exact state vocabulary.**

~~~python
class AgentActionType(str, Enum):
    email_draft = "EMAIL_DRAFT"
    follow_up_task = "FOLLOW_UP_TASK"


class AgentProposalStatus(str, Enum):
    ready_for_review = "READY_FOR_REVIEW"
    blocked = "BLOCKED"
    needs_research = "NEEDS_RESEARCH"
    approved = "APPROVED"
    rejected = "REJECTED"
    expired = "EXPIRED"
    executed = "EXECUTED"


class AgentAttemptStatus(str, Enum):
    simulated = "SIMULATED"
    cancelled = "CANCELLED"


class AgentOutcomeType(str, Enum):
    qualified = "QUALIFIED"
    disqualified = "DISQUALIFIED"
    meeting_booked = "MEETING_BOOKED"
    no_response = "NO_RESPONSE"
    expired = "EXPIRED"
~~~

Create SQLModel tables `AgentRun`, `AgentSignal`, `AgentProposal`, `AgentDecision`, `AgentAttempt`, and `AgentOutcome`. Every table has a UUID primary key and `workspace_id`. A proposal has `shared_contact_id`, action type, status, score, `reason_codes_json`, `evidence_json`, `draft_json`, expiry, and created time. An attempt and outcome are each unique by proposal ID.

- [ ] **Step 4: Add an additive migration and model import.**

The migration creates only new tables, indexes on `(workspace_id, created_at)` and `(workspace_id, shared_contact_id)`, and the two proposal-ID uniqueness constraints. It does not alter contacts, campaigns, sequences, or voice tables.

- [ ] **Step 5: Re-run focused tests, static checks, and commit.**

~~~powershell
uv run --project apps/api pytest apps/api/tests/domain/sales_agent/test_models.py -q
uv run --project apps/api ruff check apps/api/app/domain/sales_agent apps/api/tests/domain/sales_agent
uv run --project apps/api mypy apps/api/app/domain/sales_agent
git add apps/api/app/domain/sales_agent apps/api/app/models.py apps/api/app/alembic/versions/sales_agent_20260809_add_supervised_loop.py apps/api/tests/domain/sales_agent/test_models.py
git commit -m "feat: add supervised sales agent state model"
~~~

### Task 2: Implement deterministic evidence, ranking, and proposal generation

**Files:**

- Create: `apps/api/tests/domain/sales_agent/test_service.py`
- Create: `apps/api/app/domain/sales_agent/schemas.py`
- Create: `apps/api/app/domain/sales_agent/service.py`

- [ ] **Step 1: Write failing behavior tests for the decision table.**

~~~python
def test_propose_blocks_explicitly_suppressed_contact() -> None:
    proposal = build_proposal(contact={"email": "a@example.com", "suppressed": True})
    assert proposal.status == "BLOCKED"
    assert proposal.reason_codes == ["SUPPRESSED_CONTACT"]


def test_propose_requires_research_when_company_is_missing() -> None:
    proposal = build_proposal(contact={"email": "a@example.com", "company": None})
    assert proposal.status == "NEEDS_RESEARCH"
    assert proposal.reason_codes == ["COMPANY_MISSING"]


def test_propose_creates_reviewable_email_from_evidence() -> None:
    proposal = build_proposal(
        contact={"email": "a@example.com", "company": "Analytical", "intent": ["demo"]}
    )
    assert proposal.status == "READY_FOR_REVIEW"
    assert proposal.action_type == "EMAIL_DRAFT"
    assert proposal.score == 65
    assert "DECLARED_INTENT" in proposal.reason_codes
~~~

- [ ] **Step 2: Run tests and verify the service is absent.**

~~~powershell
uv run --project apps/api pytest apps/api/tests/domain/sales_agent/test_service.py -q
~~~

- [ ] **Step 3: Implement deterministic proposal rules.**

`build_proposal` uses current shared-contact fields and the most recent prospecting snapshot. Scores are company `+20`, email `+15`, declared buyer intent `+30`, recent activity `+15`, Messaging Hub handoff `+10`, and phone `+10`; cap at 100. Add only the reason codes responsible for awarded points. Suppression, do-not-contact, or explicit false consent override scoring. A missing company or email returns `NEEDS_RESEARCH` before draft generation. The email draft uses only the contact, company, declared intent, and persisted evidence; it must not claim an unverified fact.

- [ ] **Step 4: Persist one run and deduplicated signals.**

Implement `run_supervised_agent(session, workspace_id, actor_id, campaign_id)`. It reads only workspace contacts; writes a run; derives signals such as `contact:{id}:intent:{normalized_intent}`; and creates one current proposal per contact/action type. Re-running retains history but changes the preceding `READY_FOR_REVIEW` proposal to `EXPIRED`.

- [ ] **Step 5: Verify service correctness and commit.**

~~~powershell
uv run --project apps/api pytest apps/api/tests/domain/sales_agent/test_service.py -q
uv run --project apps/api ruff check apps/api/app/domain/sales_agent apps/api/tests/domain/sales_agent
uv run --project apps/api mypy apps/api/app/domain/sales_agent
git add apps/api/app/domain/sales_agent apps/api/tests/domain/sales_agent/test_service.py
git commit -m "feat: generate supervised sales agent proposals"
~~~

### Task 3: Expose review, simulated execution, and outcome APIs

**Files:**

- Create: `apps/api/tests/api/routes/test_sales_agent.py`
- Create: `apps/api/app/api/routes/sales_agent.py`
- Modify: `apps/api/app/api/main.py`

- [ ] **Step 1: Write failing route tests.**

~~~python
def test_approve_creates_one_simulated_attempt(client, admin_headers, proposal):
    response = client.post(
        f"/api/v1/sales-agent/proposals/{proposal.id}/approve",
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.json()["attempt"]["status"] == "SIMULATED"


def test_approve_is_idempotent(client, admin_headers, proposal):
    first = client.post(f"/api/v1/sales-agent/proposals/{proposal.id}/approve", headers=admin_headers)
    second = client.post(f"/api/v1/sales-agent/proposals/{proposal.id}/approve", headers=admin_headers)
    assert first.json()["attempt"]["id"] == second.json()["attempt"]["id"]


def test_workspace_cannot_view_another_workspaces_proposal(client, other_workspace_headers, proposal):
    response = client.get(f"/api/v1/sales-agent/proposals/{proposal.id}", headers=other_workspace_headers)
    assert response.status_code == 404
~~~

- [ ] **Step 2: Run the route test and verify it fails.**

~~~powershell
uv run --project apps/api pytest apps/api/tests/api/routes/test_sales_agent.py -q
~~~

- [ ] **Step 3: Add the REST surface.**

| Method | Path | Behavior |
|---|---|---|
| `POST` | `/sales-agent/runs` | Create a supervised run for a workspace campaign. |
| `GET` | `/sales-agent/proposals` | List proposals by status and campaign. |
| `GET` | `/sales-agent/proposals/{proposal_id}` | Return proposal, evidence, decisions, attempt, and outcome. |
| `POST` | `/sales-agent/proposals/{proposal_id}/approve` | Create or return one `SIMULATED` attempt. |
| `POST` | `/sales-agent/proposals/{proposal_id}/reject` | Persist rejection reason and status. |
| `POST` | `/sales-agent/proposals/{proposal_id}/outcome` | Record one outcome and mark proposal `EXECUTED`. |

All mutations require `require_admin`, an idempotency key, workspace ownership, and `append_audit_event_to_session`. Approval returns HTTP 409 for `BLOCKED`, `NEEDS_RESEARCH`, and `EXPIRED` proposals.

- [ ] **Step 4: Mount router, verify API behavior, and commit.**

~~~powershell
uv run --project apps/api pytest apps/api/tests/api/routes/test_sales_agent.py apps/api/tests/domain/sales_agent -q
uv run --project apps/api ruff check apps/api/app/api/routes/sales_agent.py apps/api/tests/api/routes/test_sales_agent.py
uv run --project apps/api mypy apps/api/app/api/routes/sales_agent.py
git add apps/api/app/api/main.py apps/api/app/api/routes/sales_agent.py apps/api/tests/api/routes/test_sales_agent.py
git commit -m "feat: add supervised sales agent review api"
~~~

### Task 4: Build the single agent workspace

**Files:**

- Create: `apps/web/src/features/sales-agent/api.ts`
- Create: `apps/web/src/features/sales-agent/SalesAgentWorkspacePage.tsx`
- Create: `apps/web/src/routes/_layout/sales-agent.tsx`
- Modify: `apps/web/src/components/Sidebar/AppSidebar.tsx`
- Modify: `apps/web/src/features/revenue-os/RevenueOsHomePage.tsx`
- Create: `apps/web/tests/sales-agent.spec.ts`

- [ ] **Step 1: Write the browser contract before the page.**

~~~ts
test("runs, reviews, simulates, and closes an agent proposal without provider setup", async ({ page }) => {
  await page.goto("/sales-agent")
  await page.getByRole("button", { name: "Run supervised agent" }).click()
  await expect(page.getByText("READY FOR REVIEW")).toBeVisible()
  await page.getByRole("button", { name: "Approve simulated email" }).click()
  await expect(page.getByText("SIMULATED — no provider action taken")).toBeVisible()
  await page.getByRole("button", { name: "Record qualified outcome" }).click()
  await expect(page.getByText("QUALIFIED")).toBeVisible()
})
~~~

- [ ] **Step 2: Run it and verify the route is absent.**

~~~powershell
npm --workspace frontend run test -- tests/sales-agent.spec.ts
~~~

Expected: FAIL because `/sales-agent` is not registered.

- [ ] **Step 3: Implement a single decision-first page.**

The page has a campaign selector; **Run supervised agent** button; counts for Ready, Needs research, Blocked, and Completed; a ranked queue; evidence/reason drawer; previewable email draft; approve/reject actions; a clear simulated-attempt state; and manual outcome buttons. Do not copy the existing Lead Preparation panel. Add **Sales Agent** under Revenue OS in the sidebar and replace Revenue OS's passive “Agent workforce” text with a link to this workspace.

- [ ] **Step 4: Run browser and build checks, then commit.**

~~~powershell
npm --workspace frontend run test -- tests/sales-agent.spec.ts
npm --workspace frontend run build
git add apps/web/src/features/sales-agent apps/web/src/routes/_layout/sales-agent.tsx apps/web/src/components/Sidebar/AppSidebar.tsx apps/web/src/features/revenue-os/RevenueOsHomePage.tsx apps/web/tests/sales-agent.spec.ts
git commit -m "feat: add supervised sales agent workspace"
~~~

### Gate 1: Demonstrate the no-key supervised loop

- [ ] **Step 1: Run focused verification.**

~~~powershell
uv run --project apps/api pytest apps/api/tests/domain/sales_agent apps/api/tests/api/routes/test_sales_agent.py -q
uv run --project apps/api ruff check apps/api/app/domain/sales_agent apps/api/app/api/routes/sales_agent.py apps/api/tests/domain/sales_agent apps/api/tests/api/routes/test_sales_agent.py
uv run --project apps/api mypy apps/api/app/domain/sales_agent apps/api/app/api/routes/sales_agent.py
npm --workspace frontend run test -- tests/sales-agent.spec.ts
npm --workspace frontend run build
~~~

- [ ] **Step 2: Walk through synthetic data as admin.**

Run one campaign with four contacts: ready, suppressed, missing-company, and recent-intent. Confirm statuses are `READY_FOR_REVIEW`, `BLOCKED`, `NEEDS_RESEARCH`, and `READY_FOR_REVIEW`; approve only one; confirm one `SIMULATED` attempt; record one outcome; and confirm no provider request occurred.

- [ ] **Step 3: Record evidence and stop for product review.**

Create `docs/operations/evidence/supervised-agent-gate-1.md` with command output, screenshots, proposal IDs, and the explicit statement that no external provider was called. Do not begin real email execution until the product owner approves the workflow.

## Subsequent implementation gates

### Gate 2: approved email execution

Create a separate plan to add sender identity, unsubscribe/suppression, daily caps, idempotency, retry, provider health, complaint thresholds, and kill switches before a reviewed attempt reaches the sequence worker. Prove with a fake adapter, then a sandbox/canary mailbox. Only reviewed email is enabled at this gate.

### Gate 3: cross-product outcomes

Create a tenant-scoped workflow-event mapping that sends one qualified, meeting, or disqualified outcome to eCRM and handles retry without duplicate CRM records or repeated outreach. Test a CRM outage after a completed SignalLoop attempt.

### Gate 4: consented voice callbacks

Implement immutable consent evidence and published knowledge releases before touching call-worker dispatch. Remove the non-disclosure instruction from the voice runtime. Test missing, expired, purpose-mismatched, seller-mismatched, and revoked consent; test disclosure and synchronous opt-out suppression. This gate enables inbound and requested/consented callbacks only.

### Gate 5: policy-granted autonomy

Use reconciled outcomes to evaluate ranking. Require a versioned decision policy, stale-signal expiry, provider health, campaign budget, emergency stop, operator override, and rollback before moving any action from review-required to unattended execution. Success is attributable qualified opportunity and revenue progression, never activity volume alone.

## Definition of done

- [ ] A local administrator completes the supervised loop with no external API keys.
- [ ] Every proposal exposes score components, reason codes, and evidence.
- [ ] Suppressed and incomplete contacts cannot be approved.
- [ ] Approval is idempotent and produces only a `SIMULATED` attempt.
- [ ] One manual/synthetic outcome is recorded and visible with proposal history.
- [ ] Focused API, static-analysis, browser, and build gates pass.
- [ ] Existing untracked files remain unmodified and unstaged.
