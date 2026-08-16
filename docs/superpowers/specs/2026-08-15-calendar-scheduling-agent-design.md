# Calendar Scheduling Agent Design

Date: 2026-08-15
Status: approved direction; ready for implementation planning after specification review

## Purpose

The Calendar Scheduler Agent turns an eligible meeting intent into a confirmed,
audited booking. It reads only authorized availability, proposes policy-compliant
slots, obtains required confirmation, creates or updates the event, and reconciles
ambiguous provider outcomes.

It is an independent paid agent. Voice, Email, Chat, Lead Preparation, Campaign
Manager, or a human may create the scheduling intent, but none inherits booking
capacity or calendar authority without an active Scheduler deployment.

## Current Baseline

SignalLoop already detects scheduling interest in voice conversations, persists
workspace-scoped scheduling requests, supports manual updates, creates signed
Calendly state, verifies Calendly webhooks, records booked links/times, advances
contact state, and exposes scheduling events in timelines. Post-call processing
currently marks `scheduling_pending` for manual follow-up.

The current lifecycle is only `pending`, `link_sent`, `booked`, and `cancelled`.
There is no general availability provider contract, slot-hold/confirmation flow,
booking lease, unknown-provider-outcome recovery, conflict reconciliation, or
independently metered autonomous scheduler.

## Scheduling Workflow

1. **Intent intake** — accept an idempotent intent from Voice, Email, Chat, Lead
   Preparation, Campaign Manager, RevenueOS, or an authorized user.
2. **Eligibility** — verify tenant/workspace/agent state, contact purpose/consent,
   assigned host, allowed meeting type, timezone, duration, and capacity.
3. **Availability** — query only authorized calendar free/busy windows through a
   provider adapter; never expose unrelated event titles or attendees.
4. **Slot calculation** — apply host/contact timezone, working hours, holidays,
   notice, buffers, travel rules, round-robin ownership, and conflict policy.
5. **Proposal** — persist a versioned slot offer with expiry and communicate it
   through a separately authorized channel or manual UI.
6. **Confirmation** — require explicit contact/operator confirmation unless a
   tenant policy explicitly permits a pre-authorized booking path.
7. **Booking** — recheck availability and controls, atomically claim the booking
   command, invoke the provider with a stable idempotency key, and persist receipt.
8. **Notification** — emit a booking event and hand off invitation/follow-up to
   the provider or a paid Email Agent according to configuration.
9. **Reconciliation** — resolve webhooks, conflicts, cancellations, reschedules,
   stale holds, timeouts, and unknown provider outcomes.

## State Machine

`DETECTED -> ELIGIBILITY_CHECK -> AVAILABILITY_CHECK -> SLOT_PROPOSED ->
AWAITING_CONFIRMATION -> BOOKING -> BOOKED`

Rescheduling uses `BOOKED -> RESCHEDULE_REQUESTED -> SLOT_PROPOSED` and creates a
new provider command/version without erasing the prior event receipt.

Other states:

- `SUPPRESSED`: policy/consent permanently prevents action;
- `DEFERRED`: quiet hours, capacity, or transient dependency blocks work;
- `EXPIRED`: offer/confirmation window elapsed;
- `CANCELLED`: authorized cancellation completed;
- `FAILED`: safe pre-provider failure;
- `DEAD_LETTERED`: retry budget exhausted;
- `UNKNOWN_PROVIDER_OUTCOME`: provider may have booked but no trustworthy receipt
  was received;
- `RECONCILIATION_REQUIRED`: inconsistent provider/local state needs resolution.

Only allowed transitions are persisted. Terminal provider receipts and historical
slot offers are immutable.

## Domain Model

- `SchedulingWorkflow`: tenant/workspace/agent, contact/account/campaign context,
  source, meeting type, host policy, status, current offer, lifecycle version,
  idempotency key, timestamps, and correlation IDs.
- `MeetingTypeVersion`: duration, buffers, notice, horizon, locations, questions,
  host/routing policy, confirmation policy, and active interval.
- `CalendarBinding`: tenant/workspace/agent/host, provider, credential reference,
  provider calendar ID, scopes, timezone, status, and last health.
- `AvailabilityQuery`: bounded requested interval, adapter version, response
  digest, expiry, lease/attempt fields, and redacted error class.
- `SlotOfferVersion`: ranked candidate slots, timezone renderings, expiry,
  policy version, and digest.
- `SchedulingConfirmation`: actor/contact channel, offer version, selected slot,
  confirmation evidence, time, and revocation state.
- `CalendarCommand`: booking/update/cancel command, immutable request envelope,
  digest, lease, stable provider idempotency key, status, and attempts.
- `CalendarReceipt`: provider event ID, calendar ID, accepted state, event digest,
  meeting link reference, and provider/webhook timestamps.
- `SchedulingReconciliation`: provider receipt/evidence, decision, operator,
  reason, and resulting state.

All records carry tenant and workspace ownership. Composite foreign keys prevent a
workflow from referencing another workspace's contact, campaign, binding, host,
offer, or receipt.

## Provider Boundary

The provider interface exposes:

- validate binding and scopes;
- query free/busy;
- create tentative/confirmed event;
- update/reschedule event;
- cancel event;
- get event by provider ID/idempotency marker;
- normalize and verify signed webhooks.

Adapters receive an immutable command envelope and return a normalized receipt.
Calendly can be the first adapter. Microsoft and Google adapters use the same
contract later. OIDC is deferred; local deployments use encrypted, scoped service
credentials/references with rotation and health checks. The seam must preserve a
future OIDC consent flow without changing workflow identity.

Providers that cannot guarantee idempotent booking require receipt lookup before
any retry after invocation. A timeout after invocation is ambiguous, not a safe
automatic retry.

## Time and Conflict Rules

- Persist timestamps in UTC and retain the IANA timezone used for presentation.
- Reject unknown/ambiguous timezone values rather than assuming server local time.
- Compute daylight-saving transitions with timezone-aware libraries.
- Recheck free/busy immediately before create/update.
- Slot offers have short, configured expiry and do not guarantee availability.
- Concurrent confirmations use conditional claims; one workflow cannot book two
  slots for the same offer.
- Host double-booking, duplicate contact meeting, and provider event collision
  rules are tenant configurable and fail closed.

## Confirmation and Communication

An explicit confirmation records the exact offer version, slot, timezone,
meeting type, and participant identity. A free-text affirmative response is
accepted only after the source channel verifies contact identity and maps it to an
unexpired offer.

The Scheduler does not consume an Email or Voice slot merely to calculate/book.
If SignalLoop sends slot choices, reminders, or follow-ups, the tenant must have
the corresponding paid channel deployment. A provider-native invitation may be
sent as part of the booking receipt when allowed by policy.

## API Contract

- meeting type and calendar binding administration;
- intent/workflow create and read;
- availability request and slot-offer read;
- confirm, expire, cancel, and reschedule;
- provider webhook ingestion;
- unknown-outcome reconciliation and DLQ replay;
- capacity and operational-health summary.

All mutations require `Idempotency-Key`. Admin operations require tenant-scoped
calendar administration; sellers may act only on assigned/permitted workflows.
Webhook authentication resolves the binding first and verifies with only that
tenant's provider credentials.

Responses expose workflow state and safe booking metadata, not provider tokens,
private event details, or other participants' availability.

## Capacity and Commercial Counting

One active Scheduler deployment consumes one slot. Default capacity is 100
terminal scheduling workflows per billing day. One workflow includes its slot
queries, confirmation, booking, and bounded reschedule/cancel handling. Duplicate
intent replay and provider reconciliation do not consume additional units.

Invalid/suppressed intents do not consume capacity. Capacity is reserved when an
eligible workflow starts and finalized on terminal result. Unknown outcomes hold
the reservation until reconciled.

## Failure Recovery and Operations

- Workers use bounded polling, leases, conditional transitions, and fresh clocks.
- Safe failures use exponential backoff with jitter and maximum attempts.
- Post-provider timeouts enter `UNKNOWN_PROVIDER_OUTCOME` and leave polling.
- Authorized reconciliation requires provider receipt/evidence before marking
  booked or proving not-created before replay.
- Webhooks are signature verified, tenant bound, uniquely recorded, race safe,
  monotonic, and replay idempotent.
- Dead letters are tenant scoped and replay requires capability, reason, and audit.
- A periodic reconciler compares local workflows/commands/receipts with provider
  events and eCRM projections.
- Tenant/product/agent kill switches and binding health are checked before claims
  and immediately before provider calls.

## Security, Privacy, and Audit

Calendar access uses least-privilege free/busy and event scopes. Availability
stores only the minimum intervals/digests needed and follows short retention.
Event titles/descriptions from unrelated appointments are never ingested.

Audit records intent source, policy, offer/confirmation versions, command digest,
provider receipt reference, cancellation/reschedule, reconciliation, and operator
identity. It excludes tokens, raw calendar payloads, and private event content.

## Non-Goals

- The Scheduler does not replace full calendar clients or meeting-room systems.
- It does not infer consent to contact from calendar availability.
- It does not send independent outreach without a paid channel agent.
- OIDC and generic CRM connectors remain deferred.
- It does not guarantee a proposed slot until booking receipt reconciliation.

## Acceptance Criteria

- Voice scheduling interest creates one tenant/workspace-scoped workflow and no
  duplicate under replay.
- Slot calculation respects timezone, DST, working hours, holidays, buffers,
  notice, expiry, and conflict policy.
- Booking requires valid confirmation and a final availability recheck.
- Concurrent confirmations produce at most one provider booking command.
- Provider timeout after possible acceptance never automatically double books.
- Reconciliation can prove booked/not-created and safely finalize/replay with
  audited evidence.
- Cross-tenant binding, calendar, host, contact, webhook, and receipt substitution
  is rejected.
- Missing/suspended deployment or dependency blocks new claims.
- Webhook signature, duplicate race, stale status, cancellation, reschedule,
  lease recovery, DLQ, and audit-failure tests pass.
- Capacity retry/reconciliation does not double count one workflow.

## Implementation Boundary

First migrate the existing scheduling request into the richer workflow model while
preserving current APIs/timeline behavior. Add provider-neutral availability and
command/receipt contracts, durable worker recovery, then implement Calendly
through the adapter. Autonomous slot selection/confirmation follows after time,
conflict, policy, and reconciliation tests are green. Microsoft/Google OAuth
connectors remain future adapter work.
