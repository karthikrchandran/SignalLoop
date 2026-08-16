# Unified Commercial Agent Registry Design

Date: 2026-08-15
Status: approved direction; ready for implementation planning after specification review

## Purpose

The registry is the commercial and operational source of truth for independently
sellable SignalLoop agents. It answers four questions without relying on UI
labels or hard-coded plan logic:

1. Which agent types exist and what business task does each perform?
2. Which agent deployments has a tenant purchased and activated?
3. What type-specific capacity applies to each active deployment?
4. Which dependencies, policies, usage, failures, and lifecycle events govern it?

eCRM remains free and unlimited for a customer paying for SignalLoop. eCRM users
do not consume SignalLoop agent slots. An autonomous eCRM capability consumes a
slot only when it is deployed as a SignalLoop agent that independently performs
work.

## Approved Commercial Rule

One independently configured task-specific agent deployment consumes one agent
slot. Slots are equal commercially, while capacity is specific to the agent type.

Examples:

- Two Voice Agent deployments and three Email Agent deployments consume five
  slots.
- A Campaign Manager consumes its own slot. It may orchestrate email and voice
  only when the tenant also has active paid Email and Voice deployments.
- Retry, reconciliation, projection, post-call, audit, and delivery workers do
  not consume slots. They are supporting execution infrastructure.
- A manual My Day screen is included with eCRM. An autonomous My Day Agent that
  prioritizes and schedules work consumes a slot.

Capacity is measured per active deployment and reset at the tenant's configured
billing-day boundary. Capacity is configuration data, not application constants.

## Catalog

The initial catalog contains:

| Agent type | Independently sellable outcome | Default daily capacity |
| --- | --- | ---: |
| `LEAD_PREPARATION` | Score, research, prepare, and route leads | 500 prepared leads |
| `EMAIL_OUTREACH` | Governed outbound email execution | 1,000 accepted sends |
| `VOICE_CONVERSATION` | Governed outbound voice conversations | 100 attempts, 300 connected minutes, 1 concurrent call |
| `CHAT_LEAD_CAPTURE` | Qualify and capture website/chat leads | 500 completed conversations |
| `CAMPAIGN_MANAGER` | Plan and orchestrate paid channel agents | 25 active campaigns |
| `PROPOSAL_DRAFTING` | Create governed proposal drafts and versions | 50 generated versions |
| `CALENDAR_SCHEDULER` | Propose, confirm, book, and reconcile meetings | 100 scheduling workflows |
| `REVENUE_INTERVENTION` | Governed RevenueOS intervention decisions | 500 evaluated interventions |
| `SALES_DAY_ASSISTANT` | Autonomously prioritize and arrange a seller's day | 100 planned actions |

An approved high-volume Email profile may set 5,000 accepted sends per day after
deliverability review. It is a capacity override on a deployment, not a different
agent identity and not permission to bypass consent or provider limits.

## Domain Model

### `AgentCatalogDefinition`

Versioned product-owned definition:

- stable `agent_type`;
- display name and sellable outcome;
- catalog version and lifecycle status;
- default capacity metric, amount, period, and concurrency;
- required capabilities and policy profile;
- whether the type performs external side effects;
- configuration JSON Schema version;
- created, approved, deprecated, and superseded timestamps.

Published catalog versions are immutable. A changed definition creates a new
version; deployments retain the version against which they were activated until
explicit migration.

### `AgentPlanEntitlement`

Tenant-scoped commercial entitlement:

- tenant and SignalLoop product installation;
- plan code and contract version;
- purchased slot count;
- effective interval and status;
- allowed agent types, optional type ceilings, and overage policy;
- billing timezone and billing-day boundary;
- source contract/reference and approval audit identity.

This record controls commercial eligibility. It does not grant application roles.

### `AgentDeployment`

One independently configured agent consuming one slot:

- tenant, installation, and workspace binding;
- catalog definition/version;
- name, purpose, owner, status, and lifecycle version;
- configuration document and configuration digest;
- policy profile, locale, timezone, and deployment environment;
- activation, suspension, retirement, and last-health timestamps;
- optimistic version and creation/update audit identities.

Uniqueness is tenant scoped. A deployment cannot refer to a workspace unless the
durable tenant-to-workspace binding is active and matches the installation.

Lifecycle states are `DRAFT`, `VALIDATING`, `ACTIVE`, `SUSPENDED`, `DEGRADED`,
`RETIRING`, and `RETIRED`.

### Supporting records

- `AgentChannelBinding`: deployment-to-provider/channel configuration, using
  credential references rather than secrets.
- `AgentDependency`: required source and target deployments, dependency type,
  allowed versions, and health requirement.
- `AgentCapacityOverride`: approved type-specific capacity change with effective
  interval, reason, approver, and contract reference.
- `AgentDailyUsage`: append/aggregate ledger keyed by tenant, deployment, metric,
  and billing day; raw provider units and accepted billable units are separate.
- `AgentLifecycleEvent`: append-only activation, configuration, suspension,
  capacity, dependency, and health history.

## Activation and Slot Enforcement

Activation is a serializable, idempotent operation:

1. Authenticate the actor and require tenant-scoped agent administration.
2. Lock the tenant entitlement/control row.
3. Verify an active SignalLoop installation and active workspace binding.
4. Validate the catalog version, configuration schema, provider references,
   policies, and dependencies.
5. Count deployments in slot-consuming states (`VALIDATING`, `ACTIVE`,
   `SUSPENDED`, and `DEGRADED`). Suspension preserves the purchased slot;
   retirement releases it.
6. Reject activation when the slot count or an optional type ceiling is exceeded.
7. Persist activation and its audit event in one transaction.

The database must enforce tenant/installation/workspace ownership. UI filtering
is never an isolation boundary. Concurrent activation tests must prove that two
requests cannot consume the final slot.

## Dependency Rules

Dependencies are explicit and fail closed:

- Campaign Manager email actions require at least one active Email deployment.
- Campaign Manager voice actions require at least one active Voice deployment.
- Proposal delivery requires an approved proposal version and an active Email
  deployment; the Proposal Agent itself never sends.
- Calendar invitations require an active Scheduler deployment and a healthy,
  authorized calendar binding.
- RevenueOS may request work only from deployments explicitly bound to its
  intervention policy; it does not inherit all tenant agents.

A dependency becoming suspended prevents new claims. Work already claimed before
the serialized suspension boundary may finish, consistent with existing tenant
product controls.

## Capacity Accounting

Capacity is reserved when work is durably claimed and finalized against the
actual accepted unit. Failed pre-side-effect validation releases the reservation.
An unknown provider outcome holds the reservation until reconciliation. Automatic
retry cannot double charge the same idempotency key.

Each metric defines its billable event:

- email: provider-accepted unique send;
- voice: attempted call plus connected-minute telemetry;
- lead preparation: successfully finalized prepared lead version;
- proposal: successfully finalized proposal version;
- scheduler: one terminal scheduling workflow, not every slot proposal;
- campaign: active orchestrated campaign-day;
- chat: completed qualified conversation;
- RevenueOS: completed policy evaluation/intervention outcome.

Operators can view usage and remaining capacity without seeing another tenant's
counts, provider receipts, or payloads.

## API Contract

Tenant-admin APIs include catalog listing, entitlement read, deployment CRUD,
validate, activate, suspend, resume, retire, dependency read, capacity read, and
usage summary. Every mutation requires `Idempotency-Key`, a tenant-scoped role,
strict request schemas, and append-only audit.

Activation/configuration responses include deployment ID, lifecycle version,
catalog version, slot usage, capacity policy, dependency health, and fixed reason
codes. They never return secrets.

## Failure Recovery and Operations

- Activation failures before commit have no partial deployment.
- Worker claims use leases and conditional transitions.
- Retryable pre-side-effect failures use bounded exponential backoff.
- Ambiguous external outcomes enter `UNKNOWN_PROVIDER_OUTCOME` and require
  provider receipt/operator reconciliation before replay.
- Exhausted failures enter a tenant-scoped dead-letter queue with authorized,
  audited replay.
- Reconciliation compares entitlement, deployment, bindings, dependencies,
  usage reservations, terminal receipts, and audit events.
- Tenant/product kill switches are rechecked before every work claim.
- Operational health returns fixed redacted reason codes and aggregated counts.

## Security and Audit

The registry uses secure local authentication until OIDC is implemented. Tenant
roles and product capabilities are checked server-side. Credential material is
never stored in configuration JSON or audit payloads; only credential references
and provider identifiers are recorded.

Audit covers entitlement changes, activation, configuration versions, capacity
overrides, dependency changes, suspension, reconciliation, DLQ replay, and
retirement. Audit records are append-only and scoped to tenant/workspace.

## Non-Goals

- OIDC and CRM connectors remain deferred.
- The registry does not replace provider billing or cloud metering.
- It does not merge distinct task agents into a single artificial "super agent."
- It does not make internal workers commercially countable.
- It does not let a plan entitlement bypass consent, policy, quiet hours, or
  provider limits.

## Acceptance Criteria

- A five-slot entitlement cannot activate a sixth independently configured
  deployment, including under concurrent requests.
- Different agent types consume equal slots but enforce their own capacity metric.
- Campaign Manager cannot use an unpaid/missing channel deployment.
- Suspending a tenant/product/dependency prevents later claims without corrupting
  already committed work.
- Same-key mutation replay is stable; changed-payload reuse conflicts.
- Usage retry/reconciliation never double counts one external outcome.
- Cross-tenant IDs, bindings, usage, receipts, and audit events are inaccessible.
- Unknown outcomes, stale leases, DLQ replay, and reconciliation have failure-
  recovery tests.
- Catalog/configuration changes are versioned and deployed versions remain
  reproducible.

## Implementation Boundary

Implement the registry and enforcement seams first, then register existing Email,
Voice, Chat, Campaign, and RevenueOS capabilities without changing their provider
behavior. Register the new Lead Preparation, Proposal, and Scheduler agents only
when their specifications below are implemented and pass their production gates.
