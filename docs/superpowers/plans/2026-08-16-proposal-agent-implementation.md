# Proposal Creation Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add client-isolated immutable proposal versions, deterministic template/questionnaire creation, and governed generative drafting with SignalLoop job recovery.

**Architecture:** eCRM remains the system of record for proposal aggregates, templates, answers, approvals, and artifacts. SignalLoop owns the paid agent deployment, capacity, durable generation job, and provider-neutral eCRM command/receipt seam. Template mode is completed before generative mode.

**Tech Stack:** eCRM Next.js/TypeScript/Prisma/PostgreSQL/Vitest plus SignalLoop FastAPI/SQLModel/Alembic/pytest.

---

### Task 1: eCRM immutable proposal aggregate and version migration

**Files:**
- Modify: `C:/My Workspace/eCRM/prisma/schema.prisma`
- Create: `C:/My Workspace/eCRM/prisma/migrations/<timestamp>_proposal_versions/migration.sql`
- Modify: `C:/My Workspace/eCRM/src/server/proposals/mutations.ts`
- Test: `C:/My Workspace/eCRM/src/server/proposals/mutations.test.ts`

- [ ] Add RED tests for monotonic versions, immutable sent/approved history,
  client/cell scoping, concurrent allocation, and approval invalidation.
- [ ] Add `ProposalVersion`, version lines, approvals, artifacts, source manifest,
  template/questionnaire/clause versions, and current-version pointer.
- [ ] Migrate current proposals into version 1 without losing line/PDF metadata.
- [ ] Run Prisma validation, proposal tests, and migration test GREEN.
- [ ] Commit in the eCRM repository with `feat: version client proposals immutably`.

### Task 2: Template and questionnaire mode

**Files:**
- Create: `C:/My Workspace/eCRM/src/server/proposals/templates.ts`
- Create: `C:/My Workspace/eCRM/src/server/proposals/questionnaires.ts`
- Create: `C:/My Workspace/eCRM/src/server/proposals/rendering.ts`
- Test: `C:/My Workspace/eCRM/src/server/proposals/template-generation.test.ts`

- [ ] Add RED tests for schema validation, required commercial fields, stale price
  book, discount/tax/clause rejection, deterministic rendering, and cell isolation.
- [ ] Implement versioned publication and safe deterministic renderer input.
- [ ] Persist source/template/questionnaire/renderer digests on each version.
- [ ] Run proposal tests and TypeScript checks GREEN.
- [ ] Commit with `feat: generate proposals from approved templates`.

### Task 3: SignalLoop durable proposal job and eCRM seam

**Files:**
- Create: `apps/api/app/domain/proposal_agent/models.py`
- Create: `apps/api/app/domain/proposal_agent/service.py`
- Create: `apps/api/app/domain/proposal_agent/ecrm_adapter.py`
- Create: `apps/api/app/alembic/versions/p1_proposal_agent_20260816.py`
- Test: `apps/api/tests/domain/test_proposal_agent.py`

- [ ] Add RED tests for stable commands, client/cell binding, leases, retries,
  capacity, lost eCRM response, digest reconciliation, and DLQ replay.
- [ ] Implement minimum-content encrypted job records and durable receipts while
  keeping proposal bodies in eCRM.
- [ ] Make ambiguous eCRM/artifact outcomes leave polling until receipt lookup.
- [ ] Run domain, migration, and Ruff checks GREEN.
- [ ] Commit with `feat: orchestrate proposal creation durably`.

### Task 4: Governed generative mode and approvals

**Files:**
- Create: `apps/api/app/domain/proposal_agent/generation.py`
- Create: `apps/api/app/api/routes/proposal_agent.py`
- Modify: `apps/api/app/api/main.py`
- Test: `apps/api/tests/domain/test_proposal_generation.py`
- Test: `apps/api/tests/api/routes/test_proposal_agent.py`

- [ ] Add RED evaluation tests proving no invented price, legal clause, client
  fact, delivery promise, or compliance claim; ungrounded output is flagged.
- [ ] Implement allowlisted retrieval, prompt/model versioning, evidence mapping,
  draft-only state, approval requirements, and durable idempotent APIs.
- [ ] Prove only an exact approved version can be handed to an active Email Agent.
- [ ] Run SignalLoop and eCRM proposal gates GREEN.
- [ ] Commit with `feat: add governed generative proposal drafts`.
