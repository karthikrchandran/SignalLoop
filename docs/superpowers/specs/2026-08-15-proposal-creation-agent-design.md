# Proposal Creation Agent Design

Date: 2026-08-15
Status: approved direction; ready for implementation planning after specification review

## Purpose

The Proposal Creation Agent produces governed, client-specific proposal drafts in
two modes:

1. an approved template populated through a versioned questionnaire; or
2. a from-scratch draft created with generative AI and grounded in approved
   product, pricing, client, and commercial knowledge.

The agent creates and versions proposals. It does not send them, accept them,
create contracts, or alter approved price/legal terms without human approval.

## Current Baseline

eCRM already supports manual proposals for open opportunities, proposal line
snapshots, currency/tax calculation, PDF metadata, basic statuses, and proposal-
to-order flow. A proposal currently has a sequence number and optional version
label, but there is no immutable `ProposalVersion` aggregate, reusable
questionnaire/template schema, generative creation workflow, evidence manifest,
or durable approval/recovery loop.

eCRM remains the proposal system of record. SignalLoop hosts the commercial agent
deployment and worker. Integration uses a versioned projection/command seam so
the future CRM connector can replace the current eCRM integration without
rewriting the proposal agent.

## Client Isolation and Proposal Identity

Every proposal belongs to exactly one customer cell/client account and one
opportunity. Client isolation is enforced by the eCRM cell database/runtime and
revalidated in every SignalLoop workspace command. A proposal from ARA Global,
AI Consulting, HaloEHS, QGira, or a demo cell can never be searched, templated,
retrieved, or versioned from another cell.

`Proposal` is the stable client-scoped aggregate. `ProposalVersion` is immutable.
The uniqueness boundary is `(cell_id, client_account_id, proposal_id,
version_number)`. The version counter is locked and incremented transactionally.
Displayed labels such as `v1.2` are not the identity boundary.

Edits never mutate an approved, sent, accepted, rejected, or expired version.
They create a successor version with `supersedes_version_id`. Draft versions may
also be immutable snapshots so review history is reproducible; editing produces a
new draft version and retires the prior editable head.

## Creation Modes

### Mode A: Template and Questionnaire

An administrator publishes an approved `ProposalTemplateVersion` containing:

- document structure and section order;
- supported product/edition and locale;
- versioned questionnaire JSON Schema;
- field-to-section bindings and conditional sections;
- calculation, formatting, currency, tax, and rounding rules;
- required clauses, optional clauses, and approval rules;
- output renderer version, styles, and attachment slots;
- allowed knowledge/product catalog versions.

The questionnaire supports at least:

- client legal/display name, address, contacts, and signatory;
- opportunity, problem statement, objectives, and scope;
- product/service, edition, quantity, usage tier, and implementation items;
- price book/version, unit prices, discounts, taxes, currency, and totals;
- payment type, deposit, milestone schedule, billing frequency, and due terms;
- delivery milestones, dependencies, assumptions, inclusions, and exclusions;
- service levels, support, warranty, validity, renewal, and termination;
- data residency, security/compliance selections, and customer responsibilities;
- approved legal/commercial clauses, special terms, attachments, and approvers.

Server-side validation rejects missing required answers, incompatible product/
currency combinations, unapproved discounts, invalid totals, unknown clause IDs,
and stale price books. Rendering is deterministic from the template version,
validated answers, and approved source records. The generated document contains a
manifest of all source/version digests.

### Mode B: Generative From Scratch

The user supplies a structured brief and selects approved source collections.
The agent builds a proposal outline and draft using:

- client/opportunity facts from the current customer cell;
- approved product catalog and price-book versions;
- approved legal/commercial clause library;
- tenant brand/style guidance;
- prior approved templates explicitly permitted for the same client;
- user-provided, malware-scanned attachments.

The model may draft narrative, organize sections, and propose optional wording.
It must not invent prices, discounts, delivery promises, customer facts, legal
terms, compliance claims, references, or signatures. Unsupported content is
removed or marked `REVIEW_REQUIRED` with its reason. Every material assertion has
a source reference or an explicit unverified-draft flag.

From-scratch output is always `DRAFT_REVIEW_REQUIRED`. It cannot automatically
become approved or sent.

## Domain Model

### eCRM system-of-record records

- `Proposal`: client/account/opportunity aggregate, current version pointer,
  lifecycle status, owner, and cell identity.
- `ProposalVersion`: immutable version number, mode, template/questionnaire/model
  versions, normalized content, commercial snapshot, source manifest, digest,
  creator, timestamps, and predecessor.
- `ProposalVersionLine`: immutable product/price/tax/discount snapshots.
- `ProposalApproval`: version, approval type, decision, actor, reason, policy
  version, and time.
- `ProposalArtifact`: rendered PDF/DOCX/HTML metadata, object reference, digest,
  renderer version, malware status, and replacement lineage.
- `ProposalTemplate` and `ProposalTemplateVersion`: client-private or tenant-
  approved template family and immutable published versions.
- `ProposalQuestionnaireVersion`: schema, UI hints, defaults, validation rules,
  mappings, and digest.
- `ProposalClauseVersion`: approved clause text, jurisdiction, applicability,
  approver, and immutable version.

### SignalLoop execution records

- `ProposalGenerationJob`: tenant/workspace/cell/proposal/version request, agent,
  mode, status, lease, attempts, idempotency key, input/source digests, and errors.
- `ProposalGenerationEvidence`: source identity, version, sensitivity, retrieval
  time, digest, and permitted-use label; no raw secrets.
- `ProposalGenerationReceipt`: eCRM command/projection versions, artifact digests,
  audit correlation, and finalization status.

SignalLoop does not retain unrestricted client proposal content when eCRM can
hold it. Execution payloads use the minimum required encrypted data and retention
period, while durable receipts retain digests and references for reconciliation.

## Proposal Lifecycle

Aggregate lifecycle:

`DRAFT -> IN_REVIEW -> APPROVED -> SENT -> ACCEPTED`

Alternate terminal states are `REJECTED`, `EXPIRED`, `WITHDRAWN`, and
`SUPERSEDED`. An approved version may be superseded only by creating and approving
a new version; historical status remains unchanged.

Generation job lifecycle:

`PENDING -> CLAIMED -> VALIDATING -> GENERATING -> QUALITY_REVIEW -> RENDERING ->
PERSISTING -> COMPLETED`

Exception states are `INPUT_REQUIRED`, `POLICY_DENIED`, `FAILED`,
`DEAD_LETTERED`, and `UNKNOWN_EXTERNAL_OUTCOME`.

## Approval Gates

Approval policy is tenant configurable but must include:

- sales/commercial approval for pricing and discounts;
- finance approval above configured value/discount thresholds;
- legal approval for nonstandard or generative clauses;
- security/compliance approval for nonstandard claims;
- proposal owner approval before delivery.

The system records which exact version each actor approved. Any content or
commercial change invalidates affected approvals. No approval is inferred from a
role alone.

## API and Command Contract

eCRM APIs provide template/questionnaire administration, proposal creation,
answers validation, generative brief submission, version list/detail/diff,
approval decisions, rendering, artifact retrieval, and lifecycle transitions.

SignalLoop APIs provide agent job submission/status, capacity, DLQ, and
reconciliation. Commands crossing the product boundary contain cell ID, client
account ID, proposal/version IDs, schema version, correlation ID, idempotency key,
and payload digest. eCRM verifies all identifiers within its deployment-derived
cell; cell identity is never browser selectable.

All mutations require durable idempotency. Same-key/same-input replay returns the
original version/receipt; changed input conflicts. Concurrent requests cannot
allocate the same version number.

## Rendering and Artifacts

Rendering is isolated from application processes and uses an allowlisted renderer
and fonts. Template expressions cannot execute code, access the network, or read
filesystem secrets. Uploaded sources are scanned and type/size limited.

Artifacts are stored in a tenant/cell-separated object prefix or customer-owned
store. Database records retain provider-neutral object references, digest, MIME
type, size, renderer/template versions, and retention classification. Signed
download links are short lived. Logs and audit do not contain proposal bodies.

## Email and Delivery Boundary

The Proposal Agent consumes its own slot and stops at an approved artifact. An
Email Agent consumes a separate slot and may send only:

- the exact approved immutable proposal version;
- to a contact permitted by consent/policy;
- after rechecking tenant/product/agent kill switches;
- with a stable delivery idempotency key and durable provider receipt.

Campaign Manager may coordinate this only if both required deployments are paid
and active. Manual eCRM download/share remains available under eCRM permissions.

## Capacity and Commercial Counting

One active Proposal Agent deployment consumes one slot. Default capacity is 50
successfully finalized proposal versions per billing day. Template and
generative versions use the same unit. Preview renders, deterministic retries,
approvals, downloads, and delivery do not consume another Proposal unit.

A materially changed questionnaire, brief, commercial snapshot, or source set
creates a new version and consumes a unit when finalized. Failed validation does
not. Unknown outcomes reserve one unit until reconciled.

## Failure Recovery and Reconciliation

- Jobs use leases and conditional state transitions.
- Pre-side-effect failures retry with bounded backoff.
- eCRM writes and artifact publication use stable command/idempotency keys.
- A lost response after an eCRM or object-store write becomes
  `UNKNOWN_EXTERNAL_OUTCOME`; it is not blindly repeated.
- Reconciliation queries eCRM version/digest and artifact metadata before
  accepting or replaying work.
- Exhausted jobs enter tenant-scoped DLQ with authorized audited replay.
- A periodic reconciler verifies job, proposal version, artifact, approval,
  usage, projection, and audit consistency.
- Partial artifacts remain quarantined and cannot be approved or delivered.

## Security, Privacy, and Audit

Secure local authentication is used until OIDC. Authorization is checked in both
products. Retrieval is client/cell scoped and cross-client sources are forbidden,
including templates unless explicitly published by the same tenant for permitted
reuse.

Secrets are referenced, never embedded. Prompt and document inputs are protected
against injection and data exfiltration. Audit covers template/clause publication,
generation inputs/digests, model and prompt versions, version creation/diffs,
approvals, rendering, reconciliation, DLQ replay, download, and delivery handoff.

## Non-Goals

- The agent does not execute contracts, collect signatures, invoice, or recognize
  revenue.
- It does not autonomously change a price book or legal clause library.
- It does not send proposals without the separately paid Email Agent or a manual
  authorized eCRM action.
- OIDC and generic CRM connectors remain deferred.
- Prior client proposals are not a shared cross-client training corpus.

## Acceptance Criteria

- Template mode rejects incomplete or commercially invalid questionnaires and
  deterministically renders the approved template version.
- Generative mode produces a review-required draft with grounded claims and no
  invented price/legal commitments.
- Every client proposal and every version is isolated by cell/client scope.
- Concurrent creation produces distinct monotonic versions without collision.
- Editing an approved/sent version creates a successor; history is immutable.
- Version diff identifies content, price, clause, source, and artifact changes
  and invalidates affected approvals.
- Same-key retries return the original version; changed payloads conflict.
- Lost eCRM/object-store responses enter reconciliation and do not duplicate a
  version or artifact.
- Only an exact approved version can be handed to the Email Agent.
- Cross-client ID/source/template substitution fails at the server and database
  boundary.
- Retry, lease expiry, unknown outcome, DLQ, reconciliation, approval invalidation,
  and audit failure tests are present.

## Implementation Boundary

First add immutable proposal/version/template/questionnaire models and migrate the
existing manual proposal path in eCRM. Then implement deterministic template mode
and approval/diff/rendering. Add SignalLoop job/recovery and capacity enforcement.
Generative mode comes last, after approved source retrieval, clause/price guards,
and evaluation tests are operating. The future generic CRM connector must use the
same command/projection contract.
