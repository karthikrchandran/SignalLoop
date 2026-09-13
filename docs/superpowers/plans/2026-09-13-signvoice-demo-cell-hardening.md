# Demo-Ready SignalVoice Customer Cell Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Gate outbound SignalVoice dispatch behind isolated customer-cell identity, active consent, paid Voice Conversation deployment activation, and capacity evidence.

**Architecture:** Add a focused domain helper that resolves the active Voice Conversation deployment for a workspace through `TenantWorkspaceBinding`, then use the existing commercial-agent capacity ledger from `call_worker.py`. Keep provider behavior unchanged and record failures before any external side effect.

**Tech Stack:** Python, FastAPI domain models, SQLModel, pytest, existing worker tests.

---

### Task 1: Voice Deployment Resolver

**Files:**
- Create: `apps/api/app/domain/commercial_agents/voice_execution.py`
- Test: `apps/api/tests/domain/test_commercial_agent_voice_execution.py`

- [ ] Write failing tests for no binding, no active deployment, and exactly one active `VOICE_CONVERSATION` deployment.
- [ ] Run `uv run --project apps/api pytest apps/api/tests/domain/test_commercial_agent_voice_execution.py -q` and confirm resolver tests fail because the module does not exist.
- [ ] Implement `resolve_active_voice_deployment(session, workspace_id)` using existing tenant, installation, binding, and deployment models.
- [ ] Run the focused resolver tests and confirm they pass.

### Task 2: Worker Capacity Gate

**Files:**
- Modify: `apps/workers/worker_app/call_worker.py`
- Modify: `apps/workers/tests/unit/test_call_worker.py`

- [ ] Write a failing worker test proving a queued call without an active Voice deployment fails before provider resolution.
- [ ] Write a failing worker test proving a queued call with an active Voice deployment reserves and finalizes one `voice_attempt` ledger row.
- [ ] Run `uv run --project apps/workers pytest apps/workers/tests/unit/test_call_worker.py -q` and confirm the new tests fail for the expected missing gate.
- [ ] Import the resolver plus `reserve_capacity`, `finalize_capacity`, `mark_capacity_unknown`, and `release_capacity`.
- [ ] Reserve capacity after consent/quiet-hour validation and before provider invocation.
- [ ] Finalize capacity when a call SID is returned; release for pre-effect validation failures; mark unknown when provider outcome is ambiguous.
- [ ] Run the focused worker tests and confirm they pass.

### Task 3: Demo Runbook

**Files:**
- Modify: `docs/operations/ecrm-installation-projections.md`

- [ ] Add a SignalVoice customer-cell smoke checklist covering separate deployment/database, active workspace binding, provider readiness, Voice deployment activation, consented test call, post-call processing, eCRM delivery, and reconciliation.
- [ ] Keep AWS, pooled SaaS, and live legal approval out of this phase.

### Task 4: Verification

**Commands:**
- `uv run --project apps/api pytest apps/api/tests/domain/test_commercial_agent_voice_execution.py -q`
- `uv run --project apps/workers pytest apps/workers/tests/unit/test_call_worker.py -q`
- `uv run --project apps/api ruff check apps/api/app/domain/commercial_agents/voice_execution.py apps/api/tests/domain/test_commercial_agent_voice_execution.py apps/workers/worker_app/call_worker.py apps/workers/tests/unit/test_call_worker.py`

- [ ] Report exact pass/fail output and any pre-existing unrelated failures.
