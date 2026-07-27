# Revenue OS Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the smallest acquisition-worthy foundation: a partner-installable Agent-to-Cash Outcome Ledger that can connect one CRM to one accounting/payment source, preserve trustworthy evidence, and prove the business result. The existing eMailVoice booking-to-eCRM task flow remains the first internal workflow proving the event boundary.

**Architecture:** A provider-neutral outcome contract sits above the current eMailVoice/eCRM boundary. Sources emit authenticated, idempotent facts; the outcome ledger validates, persists, deduplicates, correlates, and exposes evidence without rewriting source history. eMailVoice emits booking and engagement facts, eCRM applies Sales Ops work and emits commercial facts, and the first external CRM and accounting/payment adapters use the same contract. Existing shared-record APIs remain for shared entities only. This slice does not merge repos or databases.

**Tech Stack:** FastAPI, SQLModel, pytest, React/Vite; Next.js App Router, Prisma, Vitest.

**Product scope:** The long-term product remains the complete 12-agent Revenue OS for quoted-work businesses. The first delivery is deliberately narrower: shared identity, outcome evidence, one CRM connector, one verified cash source, reconciliation, outcome/cost reporting, and partner installation. Voice, ChatHub, autonomous engagement, proposal generation, operations, incentives, demand generation, social agents, broad ERP coverage, and the general agent builder remain preserved in the phased plan and do not block this foundation.

## Foundation decisions

- **Document role:** this is the only immediate execution plan. The phased build plan retains later work and the full feature vision.
- **Primary user:** a CRM implementation partner proving value for a quoted-work customer.
- **First commercial loop:** CRM engagement -> opportunity -> proposal/order reference -> invoice -> verified payment.
- **First ecosystem:** HubSpot or Pipedrive, selected only after a named partner agrees to test the installation.
- **First cash source:** QuickBooks or Stripe, selected with the same partner.
- **Source of truth:** provider facts remain authoritative; the ledger stores evidence and attribution, not invented financial state.
- **Installation target:** under one hour excluding provider app approval.
- **Acquisition target:** a portable, supportable product and evidence base that a CRM, revenue-workflow platform, or PE-backed software company can integrate faster by buying than rebuilding.

---

## Context Map

### Files to modify

| File | Purpose | Change |
|---|---|---|
| `C:\My Workspace\eCRM\src\app\api\workflow-events\route.ts` | eCRM event boundary | Create authenticated POST route. |
| `C:\My Workspace\eCRM\src\server\workflow-events\service.ts` | event persistence | Add idempotency key handling and task deduplication. |
| `C:\My Workspace\eCRM\src\server\crm\queries.ts` | Customer 360 timeline | Include workflow events in the existing chronology DTO. |
| `apps/api/app/integrations/ecrm_workflow_events.py` | eMailVoice emitter | POST only to `/api/workflow-events`, with an idempotency header. |
| `apps/api/app/domain/scheduling/service.py` | booking handoff | Emit a stable booking event after the local booking commits. |
| `apps/web/src/features/revenue-os/RevenueOsHomePage.tsx` | suite entry | Create role-aware workspace cards and shared-context explanation. |
| `apps/web/src/routes/_layout/revenue-os.tsx` | suite route | Create `/revenue-os`. |
| `apps/web/src/components/Sidebar/AppSidebar.tsx` | navigation | Add Revenue OS entry ahead of specialist sections. |
| `packages/event-contracts/src/outcome-events.ts` | canonical outcome contract | Add versioned engagement, commercial, financial, actor, cost, evidence, and correction facts. |
| `apps/api/app/domain/outcomes/` | outcome ledger | Add append-only ingestion, correlation, read model, attribution labels, corrections, and export. |
| `apps/api/app/api/routes/outcomes.py` | product API | Add tenant-scoped timeline, report, correction, and evidence-export endpoints. |
| `apps/web/src/features/outcomes/` | outcome experience | Add timeline, source freshness, cost, attribution, correction, and executive report. |
| `apps/api/app/integrations/crm/` | first external CRM adapter | Add HubSpot or Pipedrive only after partner selection. |
| `C:\My Workspace\eCRM\src\server\integrations\accounting\` | first verified cash adapter | Add QuickBooks or Stripe adapter, outbox, import, and reconciliation. |
| `apps/web/src/features/partners/` | partner operations | Add provisioning, readiness, connection health, support bundle, and OEM configuration. |

### Dependencies

| File | Relationship |
|---|---|
| `src/server/workflow-events/service.ts` | Existing event persistence and task creation pattern. |
| `src/server/shared-records/api-auth.ts` | Existing bearer-token validation pattern to reuse without coupling endpoints. |
| `apps/api/app/core/config.py` | Existing eCRM base URL and token configuration. |
| `apps/api/app/api/deps.py` | eMailVoice role and workspace request context. |

### Tests

| Test | Coverage |
|---|---|
| `src/server/workflow-events/service.test.ts` | event persistence and generated CRM task. |
| `src/app/api/workflow-events/route.test.ts` | authentication, validation, and idempotency. |
| `apps/api/app/integrations/test_ecrm_workflow_events.py` | endpoint, method, headers, and failure mapping. |
| `apps/api/tests/domain/test_scheduling_service.py` | booking creates a correctly-linked event. |
| `apps/web/tests/revenue-os.spec.ts` | role-aware Revenue OS landing navigation. |
| `apps/api/tests/domain/test_outcome_ledger.py` | append-only evidence, duplicate/replay, corrections, freshness, and attribution separation. |
| `apps/api/tests/integration/test_crm_to_payment_outcome.py` | simulator and sandbox-backed CRM-to-payment lifecycle. |
| `apps/web/tests/outcomes.spec.ts` | outcome timeline, evidence, cost, unknown state, correction, and export. |
| `apps/web/tests/partner-install.spec.ts` | partner provisioning, readiness, tenant isolation, and uninstall. |

### Risks

- [x] Public cross-app API change: version and test the event payload.
- [x] Data migration: workflow-event schema must gain a unique source idempotency key.
- [x] Configuration: both apps require a matching dedicated workflow token.
- [x] External identity provider: deferred behind an adapter because no provider is configured locally.
- [x] Scope expansion: all original features remain in the phased plan but cannot be pulled into the foundation without a named pilot dependency.
- [x] False attribution: collected revenue, deterministic linkage, inferred influence, and unknown attribution must be presented separately.
- [x] Founder bottleneck: provisioning, readiness, support collection, and uninstall must work without direct database access.
- [x] Acquisition diligence: licenses, IP ownership, security, data portability, and live-versus-simulated status are delivery artifacts, not end-of-project cleanup.

## Delivery tasks

### Task 1: partner commitment and boundary lock

- [ ] Interview at least two CRM implementation partners using the install flow and outcome-report prototype.
- [ ] Obtain one written, conditional design-partner acceptance test before selecting HubSpot/Pipedrive and QuickBooks/Stripe.
- [ ] Lock one quoted-work vertical and document its event vocabulary, baseline metrics, systems, permissions, and success threshold.
- [ ] Record excluded integrations and features for the first installation.

### Task 2: canonical outcome contract and append-only ledger

- [ ] Write failing contract tests for every required event, schema version, tenant, source event, causation/correlation, actor, amount, cost, currency, evidence, occurred/received time, and freshness field.
- [ ] Implement append-only ingestion with stable deduplication and replay.
- [ ] Add compensating corrections; never mutate or delete the original event through a correction.
- [ ] Build derived customer, deal, invoice, payment, agent-version, and partner read models.
- [ ] Keep verified collected revenue, deterministic linkage, inferred influence, and unknown attribution separate.
- [ ] Add signed JSON and CSV evidence export.

### Task 3: first CRM and accounting/payment adapters

- [ ] Implement OAuth and least-privilege scopes for the selected CRM and cash provider.
- [ ] Add verified webhooks, historical backfill, incremental sync, pagination, rate-limit handling, retries, replay, and disconnect/delete flows.
- [ ] Correlate external identities through the shared-record crosswalk and place uncertain matches in reconciliation.
- [ ] Provide deterministic simulators for success, timeout, duplicate, rejection, stale source, conflict, correction, and rate limit.
- [ ] Complete one sandbox-backed engagement-to-payment lifecycle.

### Task 4: outcome, cost, and partner product surfaces

- [ ] Render an evidence-linked timeline from interaction to payment.
- [ ] Capture pre-activation baselines and report time-to-response, cycle time, conversion, acceptance, collection, review effort, provider cost, and cost per outcome.
- [ ] Show source freshness, unavailable sources, corrections, and attribution method prominently.
- [ ] Add partner provisioning, readiness, connection health, support bundle, aggregate usage, branding, and OEM configuration.
- [ ] Produce marketplace assets, install/uninstall guides, privacy/security inputs, demo tenant, and partner-branded executive report.
- [ ] Prove normal installation in under one hour excluding provider approval.

### Task 5: eCRM event API and idempotency

- [ ] Write failing route tests for missing bearer token, invalid payload, accepted booking, and duplicated `sourceEventId`.
- [ ] Add `sourceEventId` to `WorkflowEvent`, with a unique index on `(sourceApp, sourceEventId)`; generate migration and Prisma client.
- [ ] Add `POST /api/workflow-events`; authenticate with the dedicated workflow token and call `ingestWorkflowEvent`.
- [ ] Change `ingestWorkflowEvent` to return the previously stored event when the source event repeats and avoid duplicate SalesTask creation.
- [ ] Run `npm test -- src/server/workflow-events src/app/api/workflow-events` and `npm run typecheck`.

### Task 6: eMailVoice emitter and scheduling handoff

- [ ] Write failing client tests that require `POST /api/workflow-events` and `Idempotency-Key`.
- [ ] Change the event client path and method; map 409/idempotent responses as success.
- [ ] Give booking emission a deterministic `sourceEventId` based on the scheduling-request ID.
- [ ] Record failed handoffs for retry rather than reversing the local booking.
- [ ] Also write the booking fact to the outcome ledger with shared identity, causation, actor, cost, and evidence references.
- [ ] Run `uv run pytest apps/api/app/integrations/test_ecrm_workflow_events.py apps/api/tests/domain/test_scheduling_service.py -q`.

### Task 7: unified visibility and suite entry

- [ ] Add workflow events to the existing eCRM Customer 360 timeline query and component DTO.
- [ ] Add the eMailVoice `/revenue-os` route and role-aware module cards; only expose a destination when the current role permits it.
- [ ] Add a sidebar entry and browser test.
- [ ] Make the outcome report the primary Revenue OS entry; present specialist workspaces as supporting modules.
- [ ] Run eMailVoice web type/build gate and the focused eCRM timeline tests.

### Task 8: commercial, security, and cross-repository acceptance

- [ ] Start both local applications with matching workflow token values.
- [ ] Create one eMailVoice scheduling request and mark it booked.
- [ ] Assert one eCRM event, one CRM follow-up task, and one timeline entry.
- [ ] Repeat the handoff and assert counts remain unchanged.
- [ ] Run one sandbox CRM-to-payment journey and assert the report distinguishes verified, inferred, corrected, stale, and unavailable facts.
- [ ] Have a partner provision and diagnose a tenant without database or source-code access.
- [ ] Verify tenant isolation, OAuth revocation, uninstall, data export, and deletion behavior.
- [ ] Produce a software bill of materials, dependency-license inventory, IP/contributor record, architecture/data-flow diagrams, threat model, backup/restore evidence, live-versus-simulated register, and acquisition data-room index.
- [ ] Record exact startup, verification, and rollback steps in the suite runbook.

## Foundation exit gate

Do not begin broad autonomous-agent expansion until:

- [ ] One partner-led installation reaches a verified outcome.
- [ ] The customer can explain the value from the outcome report without founder interpretation.
- [ ] Installation, support, correction, and connector-health effort are measured.
- [ ] The first workflow has a paid continuation, renewal, or documented rejection reason.
- [ ] The next feature is selected from retained-customer evidence rather than product completeness anxiety.

### Retire this plan after completion

When every exit-gate item is complete:

1. Record the final verification evidence and completion commit.
2. Move any intentionally unfinished or newly discovered work into `2026-07-26-agentic-revenue-workforce-phased-build-plan.md`.
3. Archive or remove this completed Foundation Plan so it does not remain a competing source of truth.
4. Create a new immediate plan only for the next approved phase.
