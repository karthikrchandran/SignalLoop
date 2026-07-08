# Platform Foundation and Sales Ops Migration Design

## Goal

Define the target architecture and phased migration path to make `eMailVoice` the long-term core platform, fold `eCRM` into it as a Sales Ops application area, and move from the current API-bridge model to a shared platform data model with clear ownership.

## Decision Summary

- `eMailVoice` becomes the long-term platform host.
- `eCRM` is a migration-source repo, not a permanent standalone system.
- The user experience should be a suite with shared login and shared data, not one giant merged application surface.
- Delivery priority is:
  1. Shared data foundation
  2. Sales Ops migration
  3. Shared shell and login consolidation

## Current State

### `eCRM` strengths

`eCRM` already contains the richer Sales Ops domain:

- leads and customers
- contacts and branches
- activities
- pipeline and opportunities
- proposals and proposal versioning
- orders
- invoices
- incentives and targets
- rep workflow such as My Day, tasks, and voice-note capture

### `eMailVoice` strengths

`eMailVoice` already contains the stronger platform and engagement runtime:

- FastAPI-based API and React/Vite frontend
- campaign orchestration
- outbound email and voice flows
- chatbot and channel integrations
- provider configuration
- worker processes and async runtime
- audit and operational infrastructure
- account/contact-oriented customer views

### Current integration weakness

The two systems are not operating as one platform yet. The current connection is transitional and API-based through `eCRM` shared-record endpoints. That is useful for a staged integration, but it is not the right end-state for a unified product suite with shared business entities.

## Product Vision Translation

The target product is not "two connected apps." It is a platform suite with shared business data and specialized app areas.

### Target app areas

- `Sales Ops`
  - lead discovery
  - daily task planning
  - pipeline management
  - proposal management
  - order tracking
  - incentive and payout reporting
  - manager analytics
- `EngageHub`
  - outbound campaigns
  - nurture sequences
  - email and voice execution
- `ChatHub`
  - inbound bots
  - web chat
  - WhatsApp
  - Facebook Messenger and similar channels
- `Marketing Ops Automation`
  - AI email automation
  - multilingual voice automation
  - content personalization
- `Manager Settings`
  - order definitions
  - cost definitions
  - target setting

## Target Architecture

### Core principle

Shared business entities should live in the platform data layer owned by `eMailVoice`. App-specific workflow tables should remain modular. The goal is shared business truth with bounded operational domains.

### Platform ownership

`eMailVoice` should own:

- primary application hosting direction
- authentication and session model
- workspace and tenancy model
- provider integration model
- async workers and orchestration runtime
- shared operational database
- suite navigation and app discovery

### Sales Ops ownership

Sales-domain capabilities from `eCRM` should be migrated into `eMailVoice` as a distinct app area rather than reimplemented from scratch in a new shape. Existing `eCRM` behavior is the reference implementation for business rules unless a specific redesign is approved.

### Transitional rule

The current `/api/shared-records` contract remains valid only during migration. It should not be treated as the long-term system boundary once the shared platform data model exists inside `eMailVoice`.

## Data Model Strategy

### Shared platform entities

These are the first entities that should become canonical in the platform:

- accounts or customers
- contacts
- lead or prospect identity
- account-contact relationships
- shared business activity timeline
- order commercial identity

These entities are shared because multiple app areas need them directly:

- Sales Ops needs them for ownership, pipeline, proposals, and orders.
- EngageHub needs them for campaign audience and nurturing.
- ChatHub needs them for inbound identity, conversation context, and escalation.
- Marketing Ops needs them for segmentation and personalization.

### Sales Ops domain entities

These stay logically under the Sales Ops area even after migration:

- pipeline stages
- opportunities
- proposals
- proposal versions and line items
- sales tasks
- sales voice notes and suggested actions
- sales targets
- incentives and payout records
- sales performance comparisons

Some of these may reference shared entities, but they are not themselves global platform records.

### Engagement domain entities

These stay under the engagement platform areas:

- campaigns
- campaign segments
- sequence steps
- send requests
- call requests and call sessions
- routing decisions
- provider event logs
- worker heartbeats
- chatbot knowledge and conversation records

### Order and proposal boundary

Orders are shared enough to belong to the platform data model, but their lifecycle should still be primarily owned by Sales Ops in the first migration phases. Proposals should remain Sales Ops-owned initially, with downstream platform consumers reading proposal-derived data rather than co-owning the raw proposal tables.

## Recommended Repo Evolution

### `eMailVoice`

Evolve into:

- platform host repo
- home of canonical shared data
- home of engagement runtimes
- home of migrated Sales Ops application slices

### `eCRM`

Evolve into:

- migration-source repo
- reference for business rules and UI patterns during migration
- eventually a sunset or archive candidate after core Sales Ops slices are absorbed

## Phased Delivery

## Phase 1: Shared Data Foundation

### Objective

Make `eMailVoice` the system of record for shared business entities before major UI migration begins.

### Required outputs

- canonical platform entity definitions for account, contact, lead identity, and order identity
- crosswalk from `eCRM` tables to target platform entities
- crosswalk from `eMailVoice` account/contact records to target platform entities
- migration IDs and legacy IDs for traceability
- a cutover model for retiring the current shared-record API bridge

### Scope boundaries

This phase should not attempt to migrate the whole Sales Ops UI. It should establish the data contract, persistence model, and migration-safe IDs first.

### Success criteria

- a single source of truth exists for shared business entities
- both future Sales Ops and existing engagement features can read from that model
- no new shared business entity is added independently to both repos after this phase starts

## Phase 2: Sales Ops Migration

### Objective

Move `eCRM` value into `eMailVoice` in bounded slices.

### Migration order

1. lead and customer management
2. contact management
3. pipeline and opportunities
4. proposals and versioning
5. orders
6. incentives and sales performance
7. My Day, tasking, and sales voice-note flows
8. manager settings, target setting, and payout reporting

### Delivery approach

Each slice should follow this pattern:

1. map source behavior in `eCRM`
2. define target data ownership in `eMailVoice`
3. build the target API and persistence
4. build the target UI
5. run data backfill or synchronization
6. verify parity on the slice
7. stop writing that slice in `eCRM`

### Success criteria

- each migrated slice is operational inside `eMailVoice`
- users do not need to switch back to `eCRM` for that slice
- source-of-truth ambiguity is removed slice by slice

## Phase 3: Shared Shell and Login Consolidation

### Objective

Make the suite feel cohesive after data and Sales Ops have stabilized.

### Scope

- shared login and session handling
- shared workspace context
- role and permission alignment
- app switcher or suite navigation
- cross-app shared timeline and context views

### Rationale

This phase is intentionally last because UI consolidation before data consolidation creates a polished shell over unstable internals.

## Non-Goals

These are explicitly out of scope for the first platform-foundation effort:

- one big merged navigation tree for all features immediately
- full UI redesign of every current screen
- replacing all current engagement runtimes
- deleting `eCRM` early in the migration
- forcing every table into one undifferentiated global schema without ownership boundaries

## Risks

### Risk 1: Premature UI unification

If the team merges shells before resolving shared data ownership, the result will look unified while remaining operationally fragmented.

### Risk 2: Dual-write ambiguity

If both repos continue to write overlapping customer/contact/order data during migration without explicit ownership rules, reconciliation complexity will grow quickly.

### Risk 3: Oversized migration blast radius

Trying to absorb all of `eCRM` in one wave will increase delivery risk, regressions, and data migration complexity.

### Risk 4: Platform bloat

If `eMailVoice` becomes the host but loses modular boundaries, it will turn into a hard-to-manage monolith. App-area boundaries must remain visible in code, data ownership, and navigation.

## Testing and Validation Strategy

### Architecture validation

- verify entity ownership for each shared business concept
- verify that new slice APIs in `eMailVoice` are not bypassing the canonical platform model
- verify migration identifiers and referential integrity

### Data migration validation

- row counts by entity
- spot-check parity for high-value accounts, contacts, opportunities, proposals, and orders
- legacy ID traceability
- read parity before write cutover

### Functional validation

- slice-by-slice parity tests against current `eCRM` behavior
- end-to-end flows for sales ownership, proposal booking, order progression, and campaign audience usage
- permissions validation for manager versus rep surfaces

## Recommended Next Deliverables

This design should be followed by a plan focused on the first implementation program only:

- platform shared-data foundation

That implementation plan should avoid mixing in the full Sales Ops UI migration. The first plan should establish the data model, migration-safe IDs, ownership rules, and a staged cutover path. Subsequent plans should cover each major Sales Ops slice.

## Approval Check

This design is correct if the product direction is:

- `eMailVoice` as the core platform
- `eCRM` folded in over time
- suite-style user experience
- shared data first
- Sales Ops migration second
- shell consolidation third

If any of those assumptions change, the migration strategy should be revised before implementation planning begins.
