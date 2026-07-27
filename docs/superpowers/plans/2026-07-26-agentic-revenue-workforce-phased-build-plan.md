# Agentic Revenue Workforce Phased Build Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create an acquisition-worthy, partner-distributed Agent-to-Cash Outcome product first, then expand it into the complete human-and-AI Revenue Workforce without deleting any planned capability. Complete code, simulations, tests, controls, and runbooks while leaving vendor accounts, credentials, OAuth approval, DNS, telephone numbers, and tenant-specific mappings as configuration-only work.

**Architecture:** `eMailVoice` owns engagement execution, channels, ChatHub, campaigns, funnels, sequences, scheduling, and engagement intelligence. `eCRM` owns digital-worker identity, opportunities, proposals, orders, production, invoices, payments, incentives, targets, and commercial reporting. The applications communicate through shared-record APIs and durable workflow events; neither writes directly to the other application's database.

**Tech Stack:** FastAPI, SQLModel, Alembic, PostgreSQL, Redis, React/Vite, pytest, Playwright, Next.js, Prisma, Vitest, provider-neutral LLM/tool adapters, durable outboxes, and signed webhook contracts.

---

## Product decision

The immediate product is not another CRM, AI-SDR bundle, or all-in-one suite. It is an embeddable **Agent-to-Cash Outcome Ledger** for quoted-work businesses. It connects engagement, opportunity, proposal, order, invoice, payment, human work, and AI-agent work so a customer or platform partner can prove what produced collected revenue, at what cost, under which permissions, and with what evidence.

The long-term product remains the complete Revenue Workforce OS for agencies, custom manufacturers, and professional-services firms whose revenue path includes quoting, delivery or production, invoicing, and collection. Nothing in the existing feature vision is cancelled; features are sequenced by their ability to create customer proof, partner distribution, and strategic acquisition value.

The product promise is:

> From first conversation to paid invoice, human employees and autonomous AI agents work from one customer record with visible permissions, outcomes, costs, and audit history.

Build complete business loops rather than isolated agents. Each phase must be usable, testable, demonstrable with simulators, and commercially valuable before the next phase begins.

## Governing priority model

This priority model overrides the numeric order of older work packages when the two conflict.

### Two-document rule

- `2026-07-26-revenue-os-foundation-plan.md` is the only immediate execution checklist.
- This phased build plan is the retained product vision, deferred backlog, and source of later phases.
- Do not create a third overlapping completion plan. Move an item into the Foundation Plan only when it becomes part of the current execution slice.
- When the Foundation Plan exit gate passes, record its completion in git history, transfer any unfinished item back here, and then archive or remove the completed Foundation Plan.
- Keep this phased plan until the retained product vision is completed, intentionally cancelled, or replaced by one explicitly named successor.

| Priority | Business purpose | Included capability |
|---|---|---|
| **Now: acquisition wedge** | Produce one installable asset that a CRM partner can sell and a platform can buy rather than rebuild. | Stable cross-system identity; durable outcome events; Agent-to-Cash ledger; one CRM adapter; one QuickBooks or Stripe adapter; reconciliation; cost and revenue attribution; audit export; partner installability; security and readiness evidence. |
| **Next: paid proof** | Let a partner demonstrate a complete, measurable customer loop. | Scheduling-to-opportunity handoff; proposal approval; order/invoice/payment evidence; partner console; ROI baseline and report; one vertical template; limited manager controls; marketplace/OEM packaging. |
| **Later: product expansion** | Increase contract value after the wedge is retained. | Voice, ChatHub, lead scoring, funnels, sequences, meeting preparation, deal risk, proposal follow-up, collections, production exceptions, incentives, targets, unified analytics, OIDC, additional CRM/ERP adapters. |
| **Wishlist: platform vision** | Preserve long-term upside without delaying proof. | Demand generation, social listening, reputation, referrals, expansion agents, unrestricted agent builder, broad template marketplace, SAP and Salesforce depth, multilingual and broad channel expansion. |

## Verified starting capability inventory

This snapshot preserves the implementation reality that previously lived in the separate Capability Completion Plan.

| Capability | Current source status | Remaining production proof |
|---|---|---|
| Voice / Vapi | Vapi adapter, provider registry, credential UI, webhook normalization, call-worker path, and unit tests exist. | Configure credentials and public callbacks; verify webhook signature, real call, recording, transcript, retry, idempotency, and audit. |
| Scheduling / Calendly | Scheduling request model, page, manual updates, Calendly booking handler, and eCRM booking event emission exist. | Configure signing key, resolve shared identity, persist/retry delivery, and prove one live booking-to-task handoff. |
| Proposals | eCRM has products, versions, line totals, GST calculations, status actions, PDF/Canva metadata, order booking, and tests. | Add approval-first AI drafting, deterministic validation, source evidence, and margin guardrails. |
| Orders, payments, costs, incentives | eCRM has order lifecycle, invoice/payment/cost records, margin calculations, incentive splits, approvals, and reporting. | Add verified accounting/payment import, export outbox, reconciliation, and conflict handling. |
| Targets and analytics | eCRM has targets, performance, and reports; eMailVoice has channel and chatbot analytics. | Add the outcome read model, source freshness, unavailable-source state, and later unified analytics. |
| Shared workspace | Revenue OS home, shared-record API, workflow-event API, and Customer 360 timeline exist. | Prove tenant-safe context handoff now; add OIDC, suite role mapping, and full browser coverage later. |

### Solo-founder scope rules

- [ ] Do not build a second provider adapter until the first adapter has one production or design-partner user.
- [ ] Do not build a general agent builder before one packaged workflow is repeatedly installed.
- [ ] Do not require the founder to sell and support every tenant directly; make CRM consultants, agencies, and implementation partners first-class users.
- [ ] Treat “one CRM + one accounting/payment system + one quoted-work vertical” as the first commercial boundary.
- [ ] A feature may move earlier only when a named design partner requires it for an agreed acceptance test.
- [ ] Maintain a provider-neutral core so the first ecosystem creates distribution without making the product impossible to acquire by another platform.

## Phase 0: Agent-to-Cash acquisition wedge

**Outcome:** A CRM or implementation partner can install the product, connect one CRM and one accounting/payment provider, and trace a customer from engagement through collected payment with immutable evidence, cost, freshness, and reconciliation state.

**Commercial gate:** Begin partner-led paid pilots after this phase. The complete autonomous-agent roster is not a prerequisite.

### Work package 0.1: Canonical outcome ledger

- [ ] Define versioned events for engagement, meeting, opportunity, proposal, order, invoice, payment, refund, dispute, human action, agent action, approval, correction, and terminal outcome.
- [ ] Carry tenant, shared customer identity, source system, source event ID, causation/correlation IDs, actor type, agent/version, occurred time, received time, cost, currency, evidence references, and data-freshness state.
- [ ] Persist append-only evidence and derive read models separately; corrections append compensating facts rather than rewriting history.
- [ ] Distinguish collected revenue from influenced revenue and never present correlation as causal proof.
- [ ] Support a portable, signed outcome-evidence export that remains understandable outside eMailVoice and eCRM.

### Work package 0.2: First CRM and cash connectors

- [ ] Select one initial CRM from HubSpot or Pipedrive based on the first partner; keep the canonical contract provider-neutral.
- [ ] Select QuickBooks or Stripe as the first verified cash source.
- [ ] Implement OAuth, least-privilege scopes, webhook verification, backfill, incremental sync, pagination, rate-limit handling, deduplication, replay, and uninstall/data-deletion behavior.
- [ ] Provide success, timeout, duplicate, rejection, stale-data, and rate-limit simulators.
- [ ] Reconcile customer, deal, invoice, and payment identity; route conflicts to an operator queue and never silently overwrite finance facts.

### Work package 0.3: Outcome, cost, and ROI experience

- [ ] Show the path from first interaction to collected payment with source evidence and freshness.
- [ ] Attribute software, model, voice, messaging, enrichment, and human-review cost to the workflow and agent version.
- [ ] Capture the customer's pre-activation baseline and compare response time, cycle time, conversion, correction, collection, and human effort after activation.
- [ ] Provide an executive outcome report, partner-branded report, and machine-readable export.
- [ ] Add confidence and attribution-method labels; permit a customer to challenge or correct an attribution.

### Work package 0.4: Partner, marketplace, and OEM readiness

- [ ] Create a partner console for tenant provisioning, connection health, readiness, support bundles, and aggregate usage without cross-tenant data leakage.
- [ ] Make a standard installation complete in under one hour, excluding provider approval delays.
- [ ] Package marketplace listing assets, demo data, onboarding checklist, uninstall flow, privacy disclosures, support policy, and commercial terms.
- [ ] Support partner branding and OEM embedding without forking the core product.
- [ ] Add consent-controlled anonymized benchmarks so customers can compare outcome and cost without exposing identifiable data.
- [ ] Produce a build-versus-buy brief showing integration depth, retained customers, partner reach, evidence volume, and roadmap time saved.

### Work package 0.5: Acquisition and due-diligence readiness

- [ ] Maintain a software bill of materials, dependency-license inventory, contributor/IP assignments, architecture map, data-flow map, threat model, incident process, backup/restore evidence, and release history.
- [ ] Separate demo, simulated, configured, and production-verified capabilities in code, UI, documentation, and sales material.
- [ ] Instrument activation, time-to-value, weekly use, connector health, retention, support effort, gross margin, and partner-sourced revenue.
- [ ] Keep customer contracts assignable where legally appropriate and document data portability and deletion obligations.
- [ ] Maintain an acquisition data-room index and update it at each commercial gate.

### Phase 0 acceptance

- [ ] A simulator-backed and one sandbox-backed journey connects CRM engagement to an opportunity, invoice, and verified payment without duplicate business effects.
- [ ] A partner can provision a tenant and diagnose readiness without founder database access.
- [ ] The outcome report separates facts, inferred influence, cost, corrections, and unavailable data.
- [ ] Security, privacy, uninstall, support, and evidence-export requirements pass.
- [ ] At least two prospective implementation partners have reviewed the install and report flow; one agrees to a design-partner acceptance test before broad expansion.

## Code-complete versus configuration-complete

### Coding is complete only when

- [ ] Provider-neutral interfaces and concrete provider adapters exist.
- [ ] OAuth initiation/callback routes exist where a provider requires OAuth.
- [ ] Credentials are referenced through the existing credential resolver and are never committed.
- [ ] Incoming webhooks are verified, normalized, deduplicated, and replayable.
- [ ] Outbound actions are persisted before provider calls and use idempotency keys.
- [ ] Transient failures retry with bounded backoff; permanent failures enter a visible dead-letter queue.
- [ ] Missing configuration disables the capability safely and produces an actionable readiness message.
- [ ] A local simulator covers success, timeout, duplicate callback, rejection, and rate-limit behavior.
- [ ] Unit, contract, integration, and browser tests exercise the simulator-backed lifecycle.
- [ ] Admin readiness and manager observability surfaces expose state, cost, errors, and freshness.
- [ ] A runbook lists the remaining external configuration steps.

### Configuration-only work

The following may remain unfinished after coding:

- Creating or paying for Vapi, Twilio, SendGrid, Canva, QuickBooks, Salesforce, SAP, Zapier, Make, n8n, enrichment, calendar, or other vendor accounts.
- Purchasing telephone numbers, domains, inboxes, or sending infrastructure.
- Accepting vendor contracts and completing production-app review.
- Entering API keys, OAuth client IDs/secrets, webhook secrets, and callback URLs.
- Completing DNS, SPF, DKIM, DMARC, mailbox warming, or branded-domain verification.
- Selecting customer-specific Salesforce objects, SAP modules, ERP fields, tax rules, and chart-of-account mappings.
- Performing live certification calls, sends, payments, or ERP postings.

Configuration absence must never prevent simulator-backed acceptance tests.

## Shared automation model

Every automatic loop uses the same states:

```text
trigger received
  -> context loaded
  -> policy evaluated
  -> plan created
  -> permitted tool selected
  -> durable action intent written
  -> tool executed
  -> response normalized
  -> business record updated
  -> outcome evaluated
  -> next action scheduled, paused, completed, suppressed, or escalated
```

Every loop must carry:

- `workspaceId`
- `agentId` and `agentVersionId`
- `runId` and `sourceEventId`
- shared customer/contact/opportunity identity
- trigger and intended outcome
- tool grants and approval policy
- budget and deadline
- model/provider metadata
- action, evidence, and outcome
- retry, escalation, and termination reason

## Agent operating model

### Human and digital workers

Create a common `RevenueWorker` identity in eCRM:

- `HUMAN`
- `AI_AGENT`
- `SYSTEM_SERVICE`
- `HYBRID_TEAM`

AI agents may own work queues and contribute to customer history, but they do not receive incentives or human sales targets.

### Required agent records

- `AgentDefinition`: stable identity, role, scope, status, owner.
- `AgentVersion`: instructions, model policy, knowledge version, tool grants, release notes.
- `AgentAssignment`: workspace, territory, queue, account, campaign, or process assignment.
- `AgentTrigger`: event, schedule, eligibility filter, cooldown, concurrency.
- `AgentRun`: lifecycle, cost, latency, outcome, model and version.
- `AgentStep`: input evidence, reasoning summary, tool call, result, timing.
- `AgentApproval`: requested action, approver, SLA, decision, reason.
- `AgentEvaluation`: factuality, policy, quality, customer outcome, reviewer.
- `AgentMetricDaily`: volume, cost, conversion, correction, escalation, failure.

### AI-agent metrics

- Cost per qualified lead and booked meeting.
- Reply-to-meeting and meeting-to-opportunity conversion.
- Proposal acceptance and correction rate.
- Response latency and follow-up SLA compliance.
- Human correction and escalation rate.
- Unsupported-claim, duplicate-action, and policy-violation rate.
- Tool failure, retry, and dead-letter rate.
- Revenue influenced and human hours saved.
- Receivable days reduced and production exceptions detected.

## Phase 1: Sellable Revenue Agent MVP

**Outcome:** A lead moves automatically from capture to qualification, controlled outreach, conversation, meeting, and eCRM opportunity while a manager can inspect and stop every agent.

**Priority:** Next or later, selected by paid-pilot requirements. Phase 0 is independently sellable; Phase 1 expands the wedge into an autonomous engagement product.

**Commercial gate:** Expand paid pilots after this phase; do not postpone Phase 0 partner pilots while completing every Phase 1 work package.

### Work package 1.1: eCRM digital-worker foundation

**Files:**

- Modify: `C:\My Workspace\eCRM\prisma\schema.prisma`
- Create: `C:\My Workspace\eCRM\src\server\agents\types.ts`
- Create: `C:\My Workspace\eCRM\src\server\agents\validators.ts`
- Create: `C:\My Workspace\eCRM\src\server\agents\repository.ts`
- Create: `C:\My Workspace\eCRM\src\server\agents\service.ts`
- Create: `C:\My Workspace\eCRM\src\server\agents\service.test.ts`
- Create: `C:\My Workspace\eCRM\src\server\agents\permissions.ts`
- Create: `C:\My Workspace\eCRM\src\app\api\agents\route.ts`
- Create: `C:\My Workspace\eCRM\src\app\api\agents\[agentId]\route.ts`

- [ ] Add the agent records defined above with tenant/workspace ownership and immutable run evidence.
- [ ] Make `RevenueWorker` usable as an owner alongside existing users without changing human incentive calculations.
- [ ] Reject AI agents from human targets, commissions, approvals, and payout ownership.
- [ ] Add create, version, activate, pause, resume, and retire commands.
- [ ] Add tenant, role, state-transition, and idempotency tests.
- [ ] Run `npm run prisma:generate`, focused Vitest, typecheck, lint, and build.

### Work package 1.2: Agent execution kernel and policy engine

**Files:**

- Create: `C:\My Workspace\eCRM\src\server\agents\runtime\runner.ts`
- Create: `C:\My Workspace\eCRM\src\server\agents\runtime\tool-registry.ts`
- Create: `C:\My Workspace\eCRM\src\server\agents\runtime\policy-engine.ts`
- Create: `C:\My Workspace\eCRM\src\server\agents\runtime\approval-service.ts`
- Create: `C:\My Workspace\eCRM\src\server\agents\runtime\budget-service.ts`
- Create: `C:\My Workspace\eCRM\src\server\agents\runtime\simulator.ts`
- Create: `C:\My Workspace\eCRM\src\server\agents\runtime\runner.test.ts`
- Create: `C:\My Workspace\eCRM\src\server\agents\runtime\policy-engine.test.ts`

- [ ] Implement bounded runs with maximum steps, duration, cost, retries, and tool calls.
- [ ] Separate read tools, reversible write tools, customer-facing actions, commercial actions, and financial actions.
- [ ] Require approval based on workspace policy rather than hard-coded agent names.
- [ ] Persist action intent before writes and make run resumption idempotent.
- [ ] Add deterministic simulator responses and snapshot fixtures.
- [ ] Test cancellation, timeout, duplicate event, budget exhaustion, denied tool, approval expiry, and retry.

### Work package 1.3: Cross-application agent event contract

**Files:**

- Create: `packages/event-contracts/src/agent-events.ts`
- Modify: `packages/event-contracts/package.json`
- Create: `apps/api/app/domain/events/agent_events.py`
- Create: `apps/api/app/domain/workflow_outbox/service.py`
- Create: `apps/api/app/workers/workflow_event_worker.py`
- Modify: `apps/api/app/integrations/ecrm_workflow_events.py`
- Modify: `C:\My Workspace\eCRM\src\server\workflow-events\service.ts`
- Create: `apps/api/tests/integration/test_agent_event_delivery.py`
- Modify: `C:\My Workspace\eCRM\src\server\workflow-events\service.test.ts`

- [ ] Version events for lead captured, scored, enrolled, contacted, replied, qualified, meeting booked, opportunity updated, approval requested, and run failed.
- [ ] Persist outbound events in the source transaction.
- [ ] Deliver asynchronously with stable event IDs and bounded retry.
- [ ] Resolve shared identities before creating eCRM work.
- [ ] Test outage, replay, out-of-order delivery, schema rejection, and exactly-once business effects.

### Work package 1.4: Lead Scoring and Qualification Agent

**Files:**

- Create: `apps/api/app/domain/agents/lead_scoring.py`
- Create: `apps/api/app/domain/agents/qualification.py`
- Modify: `apps/api/app/domain/prospecting/service.py`
- Modify: `apps/api/app/domain/signals/`
- Create: `apps/api/tests/domain/test_lead_scoring_agent.py`
- Create: `apps/api/tests/domain/test_qualification_agent.py`

- [ ] Combine fit, engagement, recency, channel, conversation, and negative signals.
- [ ] Store score components and evidence, not only a final number.
- [ ] Support configurable ICP and qualification profiles by workspace.
- [ ] Re-score on material events and apply cooldowns to noisy signals.
- [ ] Route qualified leads, nurture uncertain leads, and suppress ineligible leads.
- [ ] Compare agent recommendations with deterministic fixtures and reviewer labels.

### Work package 1.5: Automatic funnels, rules, and sequences

**Files:**

- Modify: `apps/api/app/domain/sequences/models.py`
- Modify: `apps/api/app/domain/sequences/service.py`
- Modify: `apps/api/app/workers/sequence_worker.py`
- Create: `apps/api/app/domain/funnels/models.py`
- Create: `apps/api/app/domain/funnels/service.py`
- Create: `apps/api/app/domain/policies/action_rules.py`
- Create: `apps/api/tests/domain/test_funnel_service.py`
- Modify: `apps/api/tests/domain/test_sequences_service.py`
- Modify: `apps/api/tests/workers/test_sequence_worker.py`

- [ ] Add event-driven entry/exit criteria, branching, waits, goals, suppression, retries, and terminal states.
- [ ] Allow agents to recommend a funnel or next step while deterministic policy decides whether it may execute.
- [ ] Stop automatically on reply, opt-out, meeting, disqualification, opportunity conversion, budget, or manager pause.
- [ ] Prevent duplicate enrollment and duplicate sends.
- [ ] Add A/B allocation with fixed cohorts and statistically honest reporting.
- [ ] Test the full simulator-backed lead-to-meeting loop.

### Work package 1.6: ChatHub conversation plane

**Files:**

- Modify: `apps/api/app/domain/chatbot/engine.py`
- Create: `apps/api/app/domain/chatbot/tool_registry.py`
- Create: `apps/api/app/domain/chatbot/agent_handoff.py`
- Create: `apps/api/app/domain/chatbot/evaluation.py`
- Modify: `apps/api/app/domain/chatbot/escalation.py`
- Modify: `apps/web/src/features/chatbot/`
- Modify: `apps/web/tests/chatbot.spec.ts`

- [ ] Keep ChatHub responsible for web chat, WhatsApp, SMS/social, email conversations, voice handoff, knowledge, lead capture, and human takeover.
- [ ] Add approved tools for qualification, scheduling, shared-record lookup, task creation, and handoff.
- [ ] Preserve conversation context across channels through shared identity, with explicit retention rules.
- [ ] Add pre-deployment conversation simulation and regression suites.
- [ ] Score groundedness, helpfulness, conversion, escalation quality, and policy compliance.
- [ ] Keep back-office proposal, invoice, and production agents in AgentOps rather than forcing them through ChatHub.

### Work package 1.7: AgentOps manager control tower

**Files:**

- Create: `C:\My Workspace\eCRM\src\app\(app)\agents\page.tsx`
- Create: `C:\My Workspace\eCRM\src\app\(app)\agents\[agentId]\page.tsx`
- Create: `C:\My Workspace\eCRM\src\components\agents\agent-roster.tsx`
- Create: `C:\My Workspace\eCRM\src\components\agents\agent-run-timeline.tsx`
- Create: `C:\My Workspace\eCRM\src\components\agents\agent-efficiency-dashboard.tsx`
- Create: `C:\My Workspace\eCRM\src\components\agents\approval-queue.tsx`
- Create: `C:\My Workspace\eCRM\src\components\agents\dead-letter-queue.tsx`
- Modify: `C:\My Workspace\eCRM\src\components\app-shell.tsx`
- Create: `C:\My Workspace\eCRM\tests\e2e\agents.spec.ts`

- [ ] Show roster, assignment, active version, permissions, budget, status, last run, and health.
- [ ] Show step-level run evidence without exposing hidden model reasoning.
- [ ] Add pause, resume, kill switch, approval, rejection, retry, and rollback.
- [ ] Keep AI efficiency dashboards separate from human incentive and target dashboards.
- [ ] Add daily spend limits and tenant-level automatic shutdown.
- [ ] Verify permissions and manager actions in browser tests.

### Phase 1 acceptance

- [ ] A simulated inbound or imported lead is scored, assigned, enrolled, contacted, replied to, qualified, and converted into one eCRM opportunity and meeting task.
- [ ] Retries create no duplicate contact, message, meeting, opportunity, task, or timeline entry.
- [ ] A manager can inspect every run, approve controlled actions, pause an agent, and see cost and quality metrics.
- [ ] Missing live credentials produce readiness instructions, not crashes.
- [ ] Three vertical demo workspaces exist: agency, custom manufacturing, and professional services.

## Phase 2: Commercial conversion and cash

**Outcome:** A qualified opportunity becomes an approved proposal, order, invoice, and controlled payment-follow-up workflow.

**Priority:** Proposal approval and payment evidence are **Next** when required by the first partner. Autonomous follow-up and collections remain **Later**.

**Differentiation gate:** Market the broader product as agents that continue after the meeting only after the related acceptance evidence exists.

### Work package 2.1: Meeting Preparation and Deal Risk Agents

**Files:**

- Create: `C:\My Workspace\eCRM\src\server\agents\meeting-prep\`
- Create: `C:\My Workspace\eCRM\src\server\agents\deal-risk\`
- Modify: `C:\My Workspace\eCRM\src\server\opportunities\queries.ts`
- Modify: `C:\My Workspace\eCRM\src\components\opportunities\`

- [ ] Generate grounded briefs from account, contacts, communications, proposals, open work, and risks.
- [ ] Produce evidence-backed next actions and confidence.
- [ ] Detect missing stakeholders, stalled stages, objections, absent follow-ups, and incomplete commercial data.
- [ ] Never change forecast or opportunity stage without a permitted action and audit.

### Work package 2.2: Approval-first Proposal Agent

**Files:**

- Create: `C:\My Workspace\eCRM\src\server\agents\proposal\generator.ts`
- Create: `C:\My Workspace\eCRM\src\server\agents\proposal\generator.test.ts`
- Create: `C:\My Workspace\eCRM\src\components\proposals\proposal-draft-review.tsx`
- Modify: `C:\My Workspace\eCRM\src\server\proposals\actions.ts`
- Modify: `C:\My Workspace\eCRM\src\server\proposals\mutations.ts`
- Modify: `C:\My Workspace\eCRM\src\components\proposals\proposal-form.tsx`

- [ ] Build structured scope, assumptions, exclusions, line-item suggestions, rationale, and confidence.
- [ ] Validate products, quantities, currency, GST/tax, totals, approved costs, and margin deterministically.
- [ ] Require authorized override with reason below margin threshold.
- [ ] Save only approved drafts through existing versioned proposal mutations.
- [ ] Record model, prompt, source evidence, editor changes, and approver.

### Work package 2.3: Proposal Follow-up and Order Handoff Agents

- [ ] Monitor proposal state and approved follow-up cadence.
- [ ] Classify questions and objections; escalate pricing, legal, and scope changes.
- [ ] Stop on acceptance, rejection, expiry, opt-out, or human takeover.
- [ ] Convert only accepted, valid proposal versions into an order.
- [ ] Create production/operations handoff tasks with shared evidence.

### Work package 2.4: Invoice Generation and Payment Follow-up Agents

**Files:**

- Create: `C:\My Workspace\eCRM\src\server\agents\invoice\`
- Create: `C:\My Workspace\eCRM\src\server\agents\collections\`
- Modify: `C:\My Workspace\eCRM\src\server\finance\calculations.ts`
- Modify: `C:\My Workspace\eCRM\src\server\finance\mutations.ts`
- Modify: `C:\My Workspace\eCRM\src\components\finance\`

- [ ] Draft invoices from approved order milestones and deterministic tax/amount calculations.
- [ ] Require finance approval before first issuance unless an explicit policy permits automatic issuance.
- [ ] Prioritize receivables by age, value, promise-to-pay, dispute, and customer history.
- [ ] Draft and schedule respectful reminders with quiet hours, frequency caps, and escalation.
- [ ] Never mark an invoice paid from an unverified conversational claim.
- [ ] Test partial payments, split invoices, disputes, credits, duplicate callbacks, and stale balances.

### Phase 2 acceptance

- [ ] A simulator-backed opportunity produces a reviewable proposal, approved order, invoice draft, and payment-follow-up schedule.
- [ ] Commercial and financial calculations remain deterministic and match existing tests.
- [ ] No unapproved discount, low-margin quote, invoice issue, payment correction, or order conversion occurs.
- [ ] Management can attribute cycle time, acceptance, corrections, cost, and revenue influenced to an agent version.

## Phase 3: Quote-to-cash operations and finance

**Outcome:** Agents monitor production, reconcile finance events, audit incentives, and brief management.

**Priority:** The first accounting/payment connector and reconciliation boundary move into Phase 0. Production automation, broad ERP coverage, incentive audit, and management agents remain **Later**.

### Work package 3.1: Production Exception Agent

- [ ] Monitor planned versus actual production milestones.
- [ ] Detect missing prerequisites, overdue steps, blocked work, capacity risk, and delivery risk.
- [ ] Recommend recovery actions and create approved operational tasks.
- [ ] Keep humans responsible for irreversible schedule, inventory, and delivery commitments.

### Work package 3.2: ERP/accounting connector framework

**Files:**

- Create: `C:\My Workspace\eCRM\src\server\integrations\erp\contracts.ts`
- Create: `C:\My Workspace\eCRM\src\server\integrations\erp\outbox.ts`
- Create: `C:\My Workspace\eCRM\src\server\integrations\erp\reconciliation.ts`
- Create: `C:\My Workspace\eCRM\src\server\integrations\erp\simulator.ts`
- Create: `C:\My Workspace\eCRM\src\server\integrations\quickbooks\`
- Create: `C:\My Workspace\eCRM\src\server\integrations\sap\`
- Create: `C:\My Workspace\eCRM\src\server\integrations\salesforce\`
- Create: `C:\My Workspace\eCRM\src\server\integrations\automation-gateway\`

- [ ] Define canonical customer, contact, opportunity, order, invoice, payment, and status contracts.
- [ ] Complete OAuth routes, adapters, pagination, rate limits, webhooks, correlation IDs, retries, and simulators.
- [ ] Implement QuickBooks as the first accounting adapter.
- [ ] Implement Salesforce account/contact/lead/opportunity/activity synchronization.
- [ ] Implement an SAP-compatible contract and mapping layer without inventing a customer's SAP module or field mapping.
- [ ] Add signed inbound/outbound webhooks for Zapier, Make, and n8n.
- [ ] Put conflicts into a reconciliation queue; never silently overwrite finance records.

### Work package 3.3: Incentive Audit and Performance Analyst Agents

- [ ] Keep incentives deterministic and tied to approved order, cost, collection, and split rules.
- [ ] Detect missing data, unusual overrides, duplicate eligibility, and calculation anomalies.
- [ ] Exclude AI agents from incentives and human targets.
- [ ] Explain target variance, pipeline risk, collection risk, and operational bottlenecks.
- [ ] Produce scheduled manager briefs with source freshness and unavailable-data warnings.

### Phase 3 acceptance

- [ ] Simulated ERP export/import and reconciliation work end to end with duplicates and conflicts.
- [ ] Production exceptions create one visible recommendation and task.
- [ ] Incentive audit findings never change payouts without approval.
- [ ] Manager briefs cite current data and distinguish facts from recommendations.

## Phase 4: Demand generation and platform moat

**Outcome:** Revenue OS creates and measures demand, supports reusable agents, and expands through a connector/template ecosystem.

**Priority:** Wishlist. Preserve these capabilities, but do not let them delay partner adoption, outcome evidence, or retention.

### Work package 4.1: Demand Generation Agent

- [ ] Derive topics from ICPs, customer questions, calls, lost deals, successful proposals, and product capability.
- [ ] Generate evidence-grounded blog, landing-page, case-study, email, and social drafts.
- [ ] Enforce brand voice, source citation, claim policy, plagiarism checks, and approval.
- [ ] Repurpose approved content across formats.
- [ ] Add SEO/AEO metadata, internal links, calls to action, campaign IDs, and UTMs.
- [ ] Attribute content to engagement, leads, opportunities, proposals, and revenue.
- [ ] Use the first version internally before selling it as a product capability.

### Work package 4.2: Social Listening, Reputation, Referral, and Expansion Agents

- [ ] Normalize permitted social/buying signals into the shared signal model.
- [ ] Detect funding, hiring, leadership, expansion, event, review, and competitor signals.
- [ ] Require approval for public replies until quality thresholds are proven.
- [ ] Trigger review/referral requests only after verified successful outcomes.
- [ ] Identify reorder, renewal, cross-sell, and at-risk customer opportunities.

### Work package 4.3: Agent builder and template library

- [ ] Create visual configuration for identity, instructions, knowledge, tools, triggers, policies, approvals, budgets, and evaluation.
- [ ] Version and test every agent before activation.
- [ ] Provide approved vertical templates rather than an unrestricted public marketplace initially.
- [ ] Support import/export with schema validation and secret stripping.
- [ ] Add staged rollout, canary evaluation, rollback, and retirement.

### Phase 4 acceptance

- [ ] One approved content campaign can be traced to resulting customer and revenue events.
- [ ] Social and expansion agents respect consent, channel policy, and public-reply approval.
- [ ] A manager can create an agent from a template, simulate it, approve it, deploy it, monitor it, and roll it back.

## Delivery sequence

Execute in this order:

1. Choose one CRM ecosystem, one accounting/payment provider, one quoted-work vertical, and two prospective implementation partners.
2. Complete stable shared identity, durable outcome events, and the append-only Agent-to-Cash ledger.
3. Complete the first CRM and cash connectors, reconciliation queue, audit export, and simulator/sandbox proof.
4. Complete outcome reporting, customer baseline capture, partner console, marketplace/OEM package, security evidence, and due-diligence index.
5. Start a partner-led paid pilot and measure installation time, time-to-value, support effort, retention, cost, and collected-revenue evidence.
6. Add scheduling, proposal, order, invoice, or manager controls only as required to complete the first paid outcome loop.
7. Productize the repeatable workflow and recruit additional implementation partners.
8. Expand into the Phase 1 engagement agents: digital workers, runtime, lead scoring, funnels, sequences, ChatHub, and AgentOps.
9. Expand the Phase 2 proposal, follow-up, order, invoice, and payment agents.
10. Expand Phase 3 production, ERP, incentive audit, target, analytics, and management capabilities.
11. Build Phase 4 demand generation, social, reputation, referral, expansion, and general agent-builder capabilities.

Do not start a later expansion merely to avoid proving the current commercial gate. A named retained-customer dependency may move one bounded capability earlier, but must not pull its entire phase forward.

## Preserved provider-completion backlog

These requirements remain in the long-term plan and move into the Foundation Plan only when a paid loop requires them.

### Vapi production proof

- [ ] Reject unsigned callbacks before changing call state.
- [ ] Deduplicate provider events by workspace and Vapi event ID.
- [ ] Send transient failures through the operational outbox/dead-letter path.
- [ ] Configure one non-production assistant, phone number, API key, and public callback outside source control.
- [ ] Prove request, Vapi call ID, verified callback, recording, transcript, normalized outcome, retry, and audit entry without duplicate calls.

### Calendly production proof

- [ ] Verify webhook signatures and duplicate events.
- [ ] Resolve the eCRM related record from the shared-record crosswalk rather than a local eMailVoice UUID.
- [ ] Keep a booking locally confirmed during eCRM outage and deliver it later from the durable outbox.
- [ ] Prove one eCRM timeline event and one follow-up task after retry.

### OIDC and suite-access proof

- [ ] Introduce OpenID Connect adapters in both applications without sharing passwords, user databases, or JWT secrets.
- [ ] Map central subject, tenant/workspace, and the nine Revenue OS roles.
- [ ] Sign deep-link context containing shared-record ID and return URL; validate audience, expiry, tenant, and role.
- [ ] Prove role visibility and customer-context handoff in browser tests.

## Verification gates

### eMailVoice

```powershell
uv run pytest
uv run ruff check apps/api/app apps/api/tests
uv run mypy apps/api/app
npm run build
npm run test:e2e --workspace apps/web
```

Use the actual scripts in `package.json` and `pyproject.toml` if names change.

### eCRM

```powershell
npx prisma generate
npx prisma migrate deploy
npm run typecheck
npm run lint
npm test
npm run build
npm run test:e2e
```

### Cross-application

- [ ] Shared identity and tenant isolation.
- [ ] Durable event outage/retry/replay.
- [ ] Exactly-once business effects.
- [ ] Approval and authorization enforcement.
- [ ] Agent pause/kill during an active run.
- [ ] Budget shutdown and cost attribution.
- [ ] Simulator-backed lead-to-meeting.
- [ ] Simulator-backed opportunity-to-payment-follow-up.
- [ ] ERP conflict reconciliation.
- [ ] Complete audit export.

## Commercial phase gates

### Start paid pilots when

- Phase 0 acceptance passes.
- One vertical demo and one partner installation path are usable.
- Outcome evidence, connector health, tenant isolation, reconciliation, and cost caps work.
- Pilot contracts describe live versus configuration-only capabilities.

### Start partner-led expansion when

- At least three paid pilots have run.
- At least two pilots convert to subscriptions.
- One customer permits a measured case study.
- Standard installation, support, connector health, outcome coverage, and correction rates meet documented thresholds.
- At least half of new qualified opportunities are partner-sourced rather than founder-prospected.

### Begin strategic-buyer conversations when

- At least one platform or implementation partner repeatedly installs the product.
- Retention, outcome evidence, and pilot conversion are demonstrated.
- The onboarding playbook repeats without founder-only database or code intervention.
- Gross margin and provider costs are measurable.
- Product usage proves that customers value verified agent-to-cash outcomes.
- The data room, IP chain, security evidence, customer concentration, support burden, and assignable-contract position are documented.

### Keep fundraising optional

- Do not require institutional funding to validate the wedge.
- Consider funding only when it accelerates proven partner demand, security certification, or a connector requested by retained customers.
- Prefer revenue, implementation fees, OEM licenses, and partner distribution over adding a direct-sales organization before repeatability exists.
