# Autonomous Lead Preparation and Scoring Agent Design

Date: 2026-08-15
Status: approved direction; ready for implementation planning after specification review

## Purpose

The Lead Preparation Agent continuously identifies eligible leads, calculates an
explainable score, gathers permitted evidence, creates an outreach-ready brief,
and routes the result to a human or a separately paid execution agent. Lead
scoring and preparation are one launch agent because they form one durable
decision loop; email and voice delivery remain independent agents.

## Current Baseline

SignalLoop already provides deterministic `score_prospecting_contact`, ranked
workspace contacts, CRM/timeline/website sources, `build_prospecting_brief`,
persisted prospecting snapshots, bulk research, campaign enrollment, an email
draft, and a voice opener.

The current path is manually invoked. Its scoring policy is embedded in code,
recent activity is not freshness bounded, work is not queued/leased, research is
not scheduled or event driven, and the score/brief does not run as a complete
autonomous recovery loop. The design preserves these useful foundations while
making the decision policy versioned and execution durable.

## Outcomes

For every eligible lead, the agent produces a versioned preparation package:

- score from 0 to 100 and band (`HOT`, `WARM`, `NURTURE`, `NOT_ELIGIBLE`);
- policy version, feature contributions, reasons, and negative factors;
- source references, retrieval timestamps, freshness, and confidence;
- account/contact summary, likely needs, objections, and personalization points;
- recommended next action and channel eligibility;
- governed draft inputs for separately licensed Email and Voice agents;
- routing decision, due time, and human-review flags.

The package is advisory. It cannot send an email, place a call, or change legal/
commercial commitments by itself.

## Autonomous Loop

The loop is event driven with a bounded scheduled reconciliation sweep:

1. **Discover** — receive contact/account created, intent detected, engagement,
   CRM projection, score-policy change, or freshness-expiry events.
2. **Eligibility gate** — verify tenant/product/agent state, workspace ownership,
   contact consent, suppression, purpose, data residency, and available capacity.
3. **Claim** — atomically claim one preparation job with a lease and stable
   idempotency key derived from tenant, contact, trigger, and policy version.
4. **Collect evidence** — load only permitted eCRM projection, SignalLoop
   timeline, campaign context, and approved public/company sources.
5. **Validate evidence** — normalize provenance, reject prompt injection/untrusted
   instructions, record freshness, and mark unavailable sources without invention.
6. **Score** — calculate deterministic features using an approved versioned policy.
7. **Prepare** — generate the brief and optional draft material grounded in the
   evidence package.
8. **Policy and quality gate** — check minimum evidence, score bounds, content
   safety, consent, channel eligibility, and required human review.
9. **Finalize** — atomically persist package version, score explanation, usage,
   routing event, and audit.
10. **Route** — place an approved work reference in the human queue, Campaign
    Manager, Email Agent, Voice Agent, or nurture queue. Downstream agents must
    independently recheck policy before side effects.
11. **Reconcile** — recover leases, resolve unknown source/provider outcomes,
    re-score stale packages, and dead-letter exhausted jobs.

## Scoring Policy

`LeadScoringPolicy` is tenant-scoped, versioned, approved, and immutable after
publication. It contains feature definitions, weights, caps, band thresholds,
freshness windows, exclusion rules, required evidence, and routing rules.

Initial explainable features may include:

- verified buyer intent;
- source/handoff quality;
- recent engagement within explicit freshness windows;
- account/product fit;
- role/seniority when lawfully sourced;
- complete reachable contact channels;
- campaign fit and prior response;
- negative consent/suppression/bounce signals;
- duplicate, competitor, employee, invalid, or stale-record exclusions.

Missing evidence scores as unknown, not false. Generative output never directly
sets the numeric score. A deterministic evaluator uses validated features, and
the model may only summarize the grounded explanation.

Policy publication requires a dry run against a tenant-owned evaluation set,
distribution/change report, approver, and rollback version. Re-scoring retains
prior score versions for audit and outcome analysis.

## Domain Model

- `LeadPreparationJob`: tenant/workspace/agent/contact, trigger, policy version,
  status, priority, lease, attempts, available time, idempotency key, and errors.
- `LeadEvidenceItem`: immutable source reference, type, fetched time, valid time,
  digest, sensitivity, freshness, confidence, and redacted excerpt.
- `LeadScoreVersion`: immutable score, band, policy version, feature vector,
  contribution explanation, exclusions, and created time.
- `LeadPreparationPackage`: immutable package version linked to score/evidence,
  structured brief, next action, draft references, review state, and content digest.
- `LeadRoutingDecision`: destination, decision reasons, dependency agent, due time,
  and acknowledgement.
- `LeadPreparationOutcome`: later conversion/reply/meeting/disqualification signal
  used for evaluation, never silent self-modification of the approved policy.

Unique constraints include tenant/workspace ownership and one job per stable
trigger/idempotency key. Versions are monotonically increasing per tenant/contact.

## Job State Machine

`PENDING -> CLAIMED -> EVIDENCE_COLLECTING -> SCORING -> PREPARING ->
POLICY_REVIEW -> COMPLETED -> ROUTED`

Terminal/exception states are `NOT_ELIGIBLE`, `SUPPRESSED`, `FAILED`,
`DEAD_LETTERED`, `CANCELLED`, and `UNKNOWN_EXTERNAL_OUTCOME`.

Retryable failures schedule bounded exponential backoff. A source request that may
have completed but lost its response is not blindly repeated when the provider
cannot guarantee idempotency; it enters unknown-outcome reconciliation. Expired
leases are reclaimed only when no ambiguous side effect exists.

## APIs

- scoring policy draft, validate, dry-run, publish, compare, and retire;
- create/recompute preparation job;
- bulk job creation with bounded size;
- list job/package/score history;
- approve/reject/route a package;
- dead-letter inspection/replay;
- unknown-outcome reconciliation;
- capacity and operational-health summaries.

All mutations require `Idempotency-Key`. Reads and writes require workspace
membership and role/capability checks. Contact, account, campaign, and downstream
agent IDs must be resolved inside the same workspace.

## Capacity and Commercial Counting

One active Lead Preparation deployment consumes one slot. Default capacity is
500 successfully finalized lead packages per billing day. Re-scoring the same
trigger/policy version is a replay and does not consume another unit. A new policy
version or materially new trigger may create a new billable package version.

Pre-validation failures do not consume capacity. Unknown outcomes reserve capacity
until reconciled. Human review and downstream channel delivery do not count as
Lead Preparation usage.

## Policy, Privacy, and Safety

- Consent and suppression are checked before preparation and again downstream.
- Public web research is allowlisted, rate limited, provenance tagged, and
  subject to tenant/data-residency policy.
- The agent never claims live news when it has only CRM or stale website context.
- Sensitive data is minimized and redacted from logs/audit.
- Generated statements must be traceable to evidence or explicitly labeled as a
  hypothesis requiring review.
- Cross-client training or retrieval is prohibited.
- Autonomous routing to external execution requires an enabled tenant policy and
  an active paid dependency agent.

## Operational Controls

Tenant/product/agent kill switches are rechecked before claim and routing. Health
reports queue depth, age bands, stale leases, dead letters, unknown outcomes,
policy version, source health, and capacity using fixed reason codes. Payloads and
source excerpts are excluded from operational summaries.

Reconciliation compares jobs, packages, score versions, routing acknowledgements,
usage records, and audit events. Missing terminal evidence prevents a false
`COMPLETED` state.

## Acceptance Criteria

- The existing deterministic scoring examples produce an explainable versioned
  result under a migrated default policy.
- Two workers cannot process the same claimed job concurrently.
- Every score contribution and generated assertion links to policy/evidence.
- Missing/stale sources do not become invented facts.
- Suppressed or cross-workspace contacts never produce routable drafts.
- Score policy publication is immutable, approved, dry-run tested, and reversible.
- Same-key replays are stable; changed payloads conflict.
- Retry, stale lease, provider timeout, unknown outcome, DLQ, replay, and
  reconciliation tests preserve once-only finalization.
- New evidence or policy versions produce new immutable package versions without
  overwriting earlier client history.
- Routing cannot use Email or Voice unless the required active agent dependency
  exists and its own policy gate passes.

## Implementation Boundary

First extract the current scoring rules into a versioned default policy and add
immutable score/package persistence. Then add durable job/worker recovery and
event triggers. Add generative preparation only after evidence grounding and
quality gates exist. CRM connector ingestion remains deferred; use the existing
eCRM projection seam and secure local authentication.
