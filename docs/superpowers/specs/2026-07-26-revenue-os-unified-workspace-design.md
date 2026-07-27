# Revenue OS Unified Workspace Design

## Decision

`eMailVoice` is the long-term Revenue OS platform host. `eCRM` remains the Sales Ops system during migration. The first release is a federated suite: one Revenue OS entry, one customer/workspace context, and one workflow-event contract; it is not a source-code merge or a shared-database write model.

## Release-one outcome

All actors enter through Revenue OS and are sent to their authorised specialist workspace with the active customer/workspace context preserved. eMailVoice owns engagement execution. eCRM owns the current lead-to-cash workflow. A completed engagement handoff creates durable CRM workflow state and is visible in the customer history.

## Product scope confirmed by the Revenue OS deck

The product serves agencies, custom manufacturers, and professional-services firms that quote before they invoice. The roster is twelve bounded agent responsibilities: Outreach, Campaign & Funnel, Chat & Bot, Lead Scoring, Pipeline, Proposal, Order Tracking, Payment, ERP Sync, Incentive, Target Tracking, and Analytics. The deck identifies Core CRM/shared contacts, EngageHub capture, ChatHub capture, quoting, and margin/payout calculations as the live core. ERP/accounting sync, order-tracking automation, target-versus-actual dashboards, and expanded language coverage remain explicitly roadmap work and must not be marketed as live autonomous capability.

## Identity and roles

Adopt a central OpenID Connect provider behind an adapter in each application. Do not share passwords, JWT secrets, or database tables between repositories. The implementation must carry `subject`, `tenant/workspace`, and role claims. Release-one roles are Marketing, Engagement/SDR, Sales Rep, Sales Leader/RevOps, Operations, Finance, Compensation Admin, Executive, and Platform Admin. High-impact external, commercial, and financial actions remain approval-gated and audited.

## Data and event ownership

The existing eCRM `shared_business_records` API remains the transitional shared-record contract. The eventual canonical shared model moves to eMailVoice as described in the Platform Foundation and Sales Ops Migration Design. Neither application may directly write the other application's tables. Workflow events use a separate authenticated endpoint; they must never be sent to the shared-record endpoint.

## First build slice

1. Correct the eMailVoice-to-eCRM workflow-event boundary.
2. Persist an idempotent `meeting_booked` event in eCRM and create one follow-up task.
3. Render the event in existing Customer 360 chronology.
4. Add a Revenue OS entry surface in eMailVoice that exposes authorised workspace destinations and explains the shared customer context.

## Acceptance criteria

- A booking in eMailVoice creates exactly one eCRM workflow event and one follow-up task, even when the delivery is retried.
- The related customer/lead chronology exposes the event source and summary.
- The Revenue OS entry surface is role-aware and links to EngageHub, ChatHub, Sales Ops, operations, finance, incentives, targets, and analytics without exposing unauthorised modules.
- Both local applications retain independent deployment and data ownership.

## Explicitly deferred

Production OIDC provider provisioning, ERP write access, payment collection, compensation changes, and autonomous outbound messaging require external credentials and governance decisions. The code will use an adapter/configuration boundary so those can be enabled without reworking the suite.
