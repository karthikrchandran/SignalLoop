# SignalLoop Autonomous B2B Sales Agent Design

**Status:** Approved for planning

## Purpose

Make SignalLoop an autonomous B2B sales agent progressively, without pretending that a draft, a provider queue, or a delivery event is a qualified business outcome. The first usable release is supervised: the agent makes evidence-backed proposals and an operator explicitly authorizes any external action.

## Product decision

The product is not a collection of Campaigns, Lead Preparation, Sequences, and Voice Agent screens. It is one agent loop:

```mermaid
flowchart LR
    Goal[ICP, offer, and policy] --> Signals[Signals and account evidence]
    Signals --> Decide[Agent decision and explanation]
    Decide --> Review[Human review when required]
    Review --> Action[Email, task, or callback action]
    Action --> Outcome[Reply, meeting, qualification, or rejection]
    Outcome --> Ledger[Auditable outcome ledger]
    Ledger --> Decide
```

The agent must show the evidence, policy decision, and expected next action before an action becomes external. Unknown data, missing consent, missing knowledge, or a failed policy check produce a blocked or review-required proposal; they never silently become a send or call.

## First release: supervised agent workspace

The first implementation is a local, provider-independent vertical slice.

1. An administrator supplies an ICP, a campaign goal, an approved offer-pack version, and allowed channels.
2. The agent evaluates existing workspace contacts and current CRM/timeline evidence.
3. It creates immutable `signal`, `proposal`, and `decision` records with a reason for each lead rank and suggested action.
4. The workspace presents one ordered work queue: ready, needs research, blocked, or review required.
5. An operator may approve an email draft or create a follow-up task. In this release, approval writes an outbox/attempt record only; it must not require an API key or send externally.
6. A synthetic or manually recorded outcome closes the loop and is visible in the account history.

This proves the agent workflow locally without making provider credentials a prerequisite.

## Progressive autonomy

| Stage | Agent authority | Required gate |
|---|---|---|
| 0. Supervised proposals | Read evidence and create reviewable proposals only | Deterministic decisions, tenant isolation, audit trail, no external side effects |
| 1. Approved email execution | Dispatch only operator-approved email attempts | Sender identity, unsubscribe/suppression, caps, idempotency, provider health |
| 2. Low-risk email autonomy | Dispatch pre-approved policy-compliant email actions | Measured deliverability, safe ramp, stop conditions, outcome reconciliation |
| 3. Consented voice callbacks | Queue only documented-consent callbacks | Immutable consent evidence, AI disclosure, opt-out, knowledge release, jurisdiction and provider checks |
| 4. Outcome optimization | Prioritize actions from measured outcomes | Sufficient outcome data, model evaluation, explainability, rollback, human override |

Cold autonomous AI sales calls are outside every stage. Voice is an inbound or requested/consented callback capability, not a lead-source shortcut.

## Core domains and boundaries

- **Signal:** a time-bounded, deduplicated fact from CRM, ChatHub, campaign history, or an approved research source.
- **Proposal:** the agent's recommended action for a contact/account, including evidence references, score components, drafted content, and expiry.
- **Decision:** the human or policy disposition of a proposal: `APPROVED`, `REJECTED`, `BLOCKED`, `EXPIRED`, or `EXECUTED`.
- **Attempt:** an idempotent execution record. Provider delivery is evidence of an attempt, not conversion.
- **Outcome:** a business-relevant result such as qualified, disqualified, meeting booked, no response, or expired.

SignalLoop remains the engagement executor. eCRM remains the lead-to-cash system of record. They exchange scoped shared-record and workflow-event messages rather than making direct cross-database writes.

## Safety and correctness requirements

- A policy decision is evaluated when a proposal is created and re-evaluated immediately before every external dispatch.
- Email and voice suppression are channel-specific. A contact record or phone number is not consent.
- Approved knowledge releases constrain product, pricing, tax, payment, contract, and capability claims.
- The voice runtime must disclose AI when the applicable policy requires it, offer/recognize opt-out, and stop on revocation. Its current non-disclosure instruction is removed before voice activation.
- Every user-visible ranking and action contains concise reason codes and evidence links.
- Provider absence is represented as `SIMULATED` or `BLOCKED_SETUP`, never as a failed autonomous action.

## Non-goals for the first release

- No external email, phone, LinkedIn, or calendar action.
- No predictive model trained from a small or unverified outcome set.
- No scraping or purchased-data dialing.
- No redesign of eCRM's sales, finance, production, or incentive ownership.

## Acceptance gates

1. **Supervised-loop gate:** a synthetic contact flows from signal to proposal, approval, simulated attempt, and outcome without an API key; every record is scoped and auditable.
2. **Email-readiness gate:** suppression, sender identity, approval, cap, retry, and stop-condition tests pass before real email can be enabled.
3. **Cross-product gate:** an approved SignalLoop outcome arrives at eCRM once, in the correct tenant/account context, and remains reconciled after retry.
4. **Voice-safety gate:** missing, expired, mismatched, or revoked consent denies queue creation and dispatch; disclosure and opt-out paths are tested end to end with synthetic destinations.
5. **Autonomy gate:** measured outcome reconciliation, provider health, kill switches, and a human override are demonstrated before any policy grants unattended execution.

## Success measure

The initial measure is not messages sent or calls queued. It is the proportion of high-priority proposals that have clear evidence, a permitted action, a recorded disposition, and a reconciled business outcome.
