# Phase 1 Client Suite, Administration, and Tenant Experience Design

**Status:** Draft for written-spec review
**Date:** 2026-08-09
**Scope:** ARA Global and AI Consulting Inc across CommitArc, SignalLoop, and RevenueOS

## 1. Decision summary

Phase 1 presents CommitArc, SignalLoop, and RevenueOS as three independently governed products inside one tenant-aware revenue workspace.

- ARA Global and AI Consulting receive active entitlements for all three products.
- Every employee with CommitArc access automatically receives RevenueOS Essentials.
- SignalLoop execution features remain hidden unless the employee has an engagement role.
- A role-based unified home presents assigned work and intelligence instead of repository or product boundaries.
- Platform administration uses a separate cross-tenant control plane.
- Each client uses one tenant-scoped Admin Center with role-filtered product administration sections.
- ARA receives a branded suite landing that repurposes the former ARA visual treatment.
- AI Consulting uses the neutral configurable suite landing.
- The existing generic CommitArc landing remains unchanged for direct product access.
- Central OpenID Connect provides one identity and seamless sign-on across both repositories without sharing password tables, JWT secrets, or databases.
- External CRM and campaign-management connectors, HaloEHS provisioning, SAML, SCIM, enterprise directory sync, and a third repository are deferred.

## 2. Goals

Phase 1 must:

1. Give ARA and AI Consulting administrators one seamless way to manage all three products.
2. Make RevenueOS intelligence part of every CommitArc employee's normal workday.
3. Keep product licensing, authorization, metering, navigation, and audit independently enforceable.
4. Let client administrators manage people, role bundles, branding, knowledge, messaging, and product settings without source changes.
5. Preserve tenant isolation and prevent a platform administrator from becoming an invisible cross-tenant data reader.
6. Provision and activate a tenant repeatably with idempotent recovery and an auditable evidence bundle.
7. Explain product combinations honestly while recommending RevenueOS with at least one native system of action or record.

## 3. Non-goals

Phase 1 does not include:

- external CRM connectors;
- external campaign-management connectors;
- HaloEHS tenant provisioning;
- RevenueOS extraction into a third repository;
- SAML, SCIM, social login, directory synchronization, or per-client identity-provider federation;
- a drag-and-drop or arbitrary-code landing-page builder;
- arbitrary HTML, CSS, JavaScript, remote tracking pixels, or unvalidated external assets;
- public self-signup for customer tenants;
- platform-admin access to tenant business records by default;
- production activation of cold autonomous AI voice outreach without recorded consent;
- automated tests that send real email, SMS, chat, or voice traffic.

## 4. Product boundaries and packaging

### 4.1 Product responsibilities

| Product | Phase 1 responsibility | Independent entitlement |
|---|---|---|
| CommitArc | Customer records, daily work, pipeline, proposals, orders, delivery, finance, incentives, and performance | `commitarc` |
| SignalLoop | Campaigns, sequences, email, SMS, chat, voice, scheduling, providers, consent operations, and execution evidence | `signalloop` |
| RevenueOS | Signals, next-best actions, explanations, interventions, orchestration, AI governance, and outcome attribution | `revenueos` |

The first implementation remains a modular monolith across two repositories:

- `eCRM` hosts CommitArc.
- `eMailVoice` hosts SignalLoop and bounded RevenueOS modules.

RevenueOS has its own domain models, APIs, UI routes, workers, queues, entitlement checks, usage metering, and audit records even though it shares the SignalLoop repository and deployment foundation.

### 4.2 Client packaging guidance

The client-facing guidance is:

1. **Complete Revenue Workspace — recommended:** RevenueOS + CommitArc + SignalLoop.
2. **RevenueOS + CommitArc:** for a client retaining outside engagement tools.
3. **RevenueOS + SignalLoop:** for a client retaining an outside CRM.
4. **Standalone CommitArc or SignalLoop:** independently available when that is the client's immediate need.

RevenueOS-only is not recommended in Phase 1 because external CRM and campaign-management connectors are deferred. ARA and AI Consulting receive the Complete Revenue Workspace.

## 5. Identity and seamless sign-on

### 5.1 Minimal Phase 1 OIDC profile

Phase 1 uses one configurable standards-compliant OIDC issuer with Authorization Code flow and PKCE.

- CommitArc and the SignalLoop/RevenueOS suite use separate OIDC client registrations and redirect allowlists.
- Both applications identify a person by immutable `(issuer, subject)` rather than mutable email.
- The issuer handles password establishment, password recovery, and MFA.
- Application databases never copy the user's OIDC password or password hash.
- Production uses `AUTH_MODE=oidc`; local and automated test environments may use an explicit `AUTH_MODE=local-test` adapter.
- The local-test adapter is unavailable when the environment is marked production.
- OIDC access and ID tokens are short lived. Applications establish their own secure, HTTP-only sessions after token validation.
- Session creation rechecks current tenant membership, product entitlement, account state, and session version.

The OIDC abstraction is configured through issuer URL, client ID, redirect URI, scopes, signing-key discovery, and expected audience. Phase 1 deliberately excludes SAML, SCIM, social login, custom identity-provider branding, and customer-specific federation.

### 5.2 Authorization remains application-owned

OIDC proves identity; it does not replace tenant authorization.

- The platform control plane is authoritative for suite tenant membership, role-bundle assignments, tenant lifecycle, and product-entitlement records.
- CommitArc enforces a derived organization-membership projection and CommitArc-specific permissions.
- SignalLoop enforces a derived workspace-membership projection and SignalLoop-specific permissions.
- RevenueOS enforces derived RevenueOS capability and governance assignments.
- Idempotent provisioning APIs project the same OIDC subject and authoritative suite grants into each entitled product without direct cross-database writes.
- Reconciliation detects projection drift and blocks affected access until the projection is repaired; a product-local grant cannot silently create a suite membership.
- Each application performs a live local membership and entitlement check when establishing or refreshing its session.

The shared issuer session provides seamless sign-on: moving from one product to another may perform an OIDC redirect, but the user is not asked for credentials again.

### 5.3 Invitation and credential administration

Administrators may:

- invite or reinvite a named user by email;
- assign or remove role bundles;
- suspend or reactivate the application account;
- revoke active application sessions;
- require password recovery or MFA recovery through the issuer;
- review invitation, login, recovery, and role-change audit events.

Administrators may not:

- read an existing password;
- export password hashes;
- set a permanent password for another person;
- reuse a shared generic administrator credential;
- bypass MFA or tenant authorization silently.

## 6. Tenant entry and branding

### 6.1 Entry resolution

The tenant is known before authentication through a verified tenant hostname or signed invitation context.

- ARA uses an ARA-specific suite hostname and suite landing.
- AI Consulting uses its tenant hostname with the neutral suite template.
- Generic CommitArc direct access continues to render the existing neutral CommitArc landing.
- Unknown or inactive tenant hosts render a neutral not-available response and never disclose membership or user existence.
- Submitted form fields, query parameters, and ordinary headers are not tenant authority.

Production hostnames are configuration, not hardcoded source assumptions. Local development uses an equivalent host or route adapter mapped to the same tenant-domain records.

### 6.2 ARA Global suite landing

The ARA landing is titled **ARA Global Revenue Workspace**. It reuses the former ARA visual direction while changing the product story from CommitArc-only to the complete suite.

Required content:

- ARA Global tenant identity;
- headline: **Turn every customer commitment into coordinated action.**;
- a concise suite explanation covering intelligence, engagement, customer operations, delivery, and collections;
- product cards for RevenueOS, CommitArc, and SignalLoop;
- one OIDC sign-in action;
- approved ARA graphic stored in the controlled asset system rather than loaded from a fragile third-party URL;
- support, privacy, and legal links from published tenant configuration.

### 6.3 AI Consulting suite landing

AI Consulting uses the neutral configurable suite template:

- title: **AI Consulting Revenue Workspace**;
- neutral abstract graphics;
- tenant-configured name, product cards, support, privacy, and legal links;
- no customer-specific photograph in Phase 1;
- one OIDC sign-in action.

### 6.4 Branding administration

Structured branding fields include:

- display and product names;
- logo and hero asset IDs;
- primary and secondary colors;
- headline and supporting text;
- enabled product-card copy;
- support, privacy, and legal links;
- email and document identity.

The workflow is `DRAFT -> PREVIEWED -> VALIDATED -> PUBLISHED -> SUPERSEDED`.

- Preview covers desktop and narrow viewports.
- Validation checks asset type and size, contrast, required legal links, prohibited markup, and referenced product entitlements.
- Publishing creates an immutable version and audit record.
- Rollback republishes a known prior version; it does not mutate history.
- Raw HTML, CSS, JavaScript, remote tracking pixels, and unvalidated external URLs are rejected.

## 7. End-user experience

### 7.1 Role-based unified home

The selected layout is a role-based unified home. Employees see assigned work and intelligence, not repository boundaries.

The shell provides:

- active tenant identity;
- current role context;
- role-filtered navigation;
- RevenueOS next-best actions embedded with ordinary work;
- a product switcher for areas the user is entitled to open;
- one session across product transitions;
- consistent notification, explanation, audit, and error behavior.

### 7.2 Universal differentiator

Every CommitArc employee automatically receives **RevenueOS Essentials**. It is not an optional per-user add-on.

RevenueOS Essentials includes:

- personal next-best actions;
- evidence and explanations;
- alerts for assigned customers, commitments, risks, and deadlines;
- permitted AI questions over records the employee can already access;
- personal goals, interventions, and measured outcomes.

RevenueOS Essentials does not grant team-wide data, AI policy editing, knowledge publishing, intervention approval, campaign execution, or provider administration.

### 7.3 SignalLoop visibility

SignalLoop features are hidden unless the user has an assigned engagement role. A hidden feature is also denied at API, queue, worker, and data boundaries; hiding navigation is never the authorization mechanism.

## 8. Role bundles

Roles compose. A person may hold several role bundles, but each product action checks its specific permission.

| Role bundle | CommitArc | RevenueOS | SignalLoop | Administration |
|---|---|---|---|---|
| Employee | Assigned customer and operational scope | Essentials | Hidden | None |
| Manager | Team pipeline, delivery, and performance | Team Intelligence, reassignment, and permitted approvals | Optional read or approve access | Team membership and work routing |
| Engagement Operator | Customer context and handoffs | Essentials and prioritized engagement work | Assigned campaigns, inbox, sequences, and calls | No provider or policy administration |
| Tenant Owner | Tenant-wide according to licensed products | Tenant-wide visibility | According to explicit product role | People, bundles, branding, security, products, and tenant audit |
| RevenueOS Admin | Context read as required | Knowledge, autonomy, policies, budgets, outcomes, and kill switches | Execution evidence | RevenueOS configuration only |
| CommitArc Admin | Commercial, delivery, finance, catalog, and numbering administration | Essentials and configuration evidence | Not implied | CommitArc configuration only |
| Engagement Admin | Customer context as required | Essentials and engagement governance | Campaigns, channels, providers, consent, templates, and agents | SignalLoop configuration only |

The primary ARA and AI Consulting administrators receive:

- Tenant Owner;
- RevenueOS Admin;
- CommitArc Admin;
- Engagement Admin.

One login reveals every permitted Admin Center section, but no role silently grants another product's privileges.

## 9. Administration layouts

### 9.1 Platform Admin control plane

The Platform Admin has a separate cross-tenant control plane with:

- tenant lifecycle and readiness;
- product editions and entitlements;
- tenant domains and branding-template defaults;
- initial Tenant Owner invitation;
- OIDC client and issuer configuration references;
- deployment region, locale, currency, and compliance-pack selection;
- provider allowlists and global safety ceilings;
- usage, metering, health, and audit summaries;
- time-limited support-session requests;
- suspension and offboarding controls.

Platform Admin does not have implicit access to tenant customer, conversation, campaign, pipeline, financial, or knowledge-base content.

### 9.2 Tenant Admin Center

The tenant-scoped Admin Center includes:

- Overview;
- People and Roles;
- Products;
- Branding;
- Security;
- Tenant Audit;
- RevenueOS Administration when permitted;
- CommitArc Administration when permitted;
- SignalLoop Administration when permitted.

### 9.3 Product administration

RevenueOS Administration contains:

- AI Control Center;
- Knowledge Releases;
- Policies and Autonomy;
- Intervention Queue;
- Budgets and Limits;
- Outcomes;
- RevenueOS Audit.

CommitArc Administration contains:

- business settings;
- pipeline and catalog;
- proposals and numbering;
- delivery and production configuration;
- finance and incentive configuration;
- CommitArc Audit.

SignalLoop Administration contains:

- engagement overview;
- campaigns and sequences;
- channels and providers;
- consent and suppression;
- templates;
- messaging and voice agents;
- SignalLoop Audit.

## 10. AI, knowledge, and messaging governance

### 10.1 AI-first operating rule

Routine RevenueOS interventions execute automatically when all required checks pass:

- active tenant and product entitlement;
- current role and capability grant;
- published tenant knowledge release;
- channel consent and suppression state;
- jurisdiction and quiet-hours policy;
- action-specific autonomy policy;
- budget and frequency caps;
- registered provider readiness;
- idempotency and kill-switch state.

Humans handle exceptions, not every ordinary action. The AI must refuse unsupported product capability, pricing, tax, payment-cycle, and contract-term answers rather than improvise outside the published tenant knowledge release.

### 10.2 Platform messaging controls

Platform Admin controls:

- supported provider types;
- regional compliance-pack availability;
- provider and model allowlists;
- hard cost and volume ceilings;
- platform incident and emergency kill switches;
- minimum audit and retention requirements.

### 10.3 Tenant messaging controls

Authorized tenant administrators control:

- sender identities and channel activation;
- provider secret references and connection tests;
- approved message templates;
- knowledge releases;
- consent, suppression, quiet hours, and frequency caps;
- escalation and handoff policies;
- action-specific autonomy and approval thresholds;
- tenant kill switches and operational budgets.

Provider credentials are secret references. Plaintext credentials do not appear in public models, ordinary logs, browser storage, or audit payloads.

## 11. Tenant onboarding state machine

The Platform Admin starts one persisted, idempotent provisioning operation.

| Stage | Required result |
|---|---|
| `TENANT_DRAFTED` | Stable tenant key, legal/display name, region, locale, timezone, and lifecycle record |
| `PRODUCTS_ASSIGNED` | CommitArc, RevenueOS, and SignalLoop entitlements with edition and status |
| `ENTRY_CONFIGURED` | Tenant domain, safe public branding draft, product cards, support, privacy, and legal links |
| `OWNER_INVITED` | Named OIDC invitation and pending local membership projections |
| `ROLES_ASSIGNED` | Tenant Owner and all three product-admin roles for the primary administrator |
| `POLICIES_PUBLISHED` | Knowledge, autonomy, consent, quiet hours, budgets, limits, and kill-switch versions |
| `NATIVE_INTEGRATION_VERIFIED` | Scoped CommitArc, RevenueOS, and SignalLoop canary operations and reconciliation |
| `READY_FOR_ACCEPTANCE` | Isolation, entitlement, branding, identity, policy, audit, and rollback evidence complete |
| `ACTIVE` | Owner accepted invitation, established MFA, and passed acceptance checks |

Each stage persists:

- input hash;
- idempotency key;
- start and end time;
- attempt count;
- safe result code;
- evidence references;
- actor and approver;
- rollback or compensation status.

Repeating the same request and idempotency key returns the same operation. A partial failure resumes from the failed stage and never creates duplicate tenants, workspaces, users, invitations, or entitlements.

Compensation disables incomplete tenant access and revokes incomplete credentials. It does not broadly delete customer data.

## 12. Native cross-product flow

Phase 1 integrates the three native products without direct cross-database writes.

1. RevenueOS consumes tenant-scoped signals and business projections through authenticated contracts.
2. RevenueOS evaluates knowledge, consent, policy, entitlement, budget, and idempotency.
3. An approved automatic intervention is dispatched to SignalLoop or written as scoped CommitArc workflow state.
4. SignalLoop records provider attempt and delivery evidence.
5. CommitArc records lead-to-cash state and customer commitments.
6. RevenueOS attributes outcomes back to the signal, decision, intervention, cost, and revenue milestone.

All calls use tenant-scoped installation credentials or workload identity. Neither application writes the other application's tables.

## 13. Support access and cross-tenant safety

Support access is a separate workflow, not an ordinary global role.

- A request names tenant, reason, requested capabilities, duration, and ticket/reference.
- Tenant approval is required unless a documented emergency policy applies.
- The system issues a short-lived, tenant-scoped support grant.
- Every page, query, mutation, export, AI tool call, and administrative action records the support context.
- Expiry revokes the grant automatically.
- Platform Admin cannot use support access to change passwords or conceal audit history.

Opaque resources from another tenant return uniform not-found behavior. Tenant isolation is enforced in application lookups, foreign-ID validation, queues, storage keys, integration credentials, and database row-level security where supported.

## 14. Error handling and recovery

| Failure | Required behavior |
|---|---|
| Unknown tenant hostname | Neutral unavailable response; no tenant or membership disclosure |
| Suspended/offboarding tenant | Deny new sessions and product work; preserve auditable state |
| OIDC unavailable | Fail closed; show retry/support guidance; do not fall back to production local passwords |
| Invalid or stale membership | Revoke application session and require reauthorization |
| Product entitlement removed | Hide navigation and deny API, queue, worker, and metering operations immediately |
| Branding validation failure | Keep prior published version active and return field/asset errors to the draft |
| Provisioning partial failure | Persist the failed stage and resume idempotently after correction |
| Native integration canary failure | Keep tenant out of `ACTIVE`; preserve evidence and safe retry controls |
| AI knowledge or consent unavailable | Suppress the intervention rather than guess or send |
| Provider failure | Record evidence, apply bounded retry policy, and preserve idempotency |

## 15. Audit and observability

Audit records contain:

- actor OIDC subject and local user ID;
- tenant ID;
- product code;
- role/capability used;
- action and target type with safe identifier;
- before/after version references where applicable;
- support-session context when present;
- request, correlation, and idempotency IDs;
- outcome, denial reason, and timestamp.

Logs and metrics use tenant ID as controlled metadata without message bodies, passwords, tokens, provider secrets, or raw high-cardinality personal data.

## 16. Phase 1 client fixtures

### 16.1 ARA Global

- all three product entitlements active;
- ARA Global Revenue Workspace landing;
- controlled ARA hero asset;
- primary administrator with all four approved admin bundles;
- CommitArc Core and RevenueOS Essentials for every employee;
- SignalLoop access only for assigned engagement roles;
- ARA-specific locale, currency, tax, payment, contract, and knowledge configuration stored as tenant data.

### 16.2 AI Consulting Inc

- all three product entitlements active;
- neutral AI Consulting Revenue Workspace landing;
- primary administrator with all four approved admin bundles;
- CommitArc Core and RevenueOS Essentials for every employee;
- SignalLoop access only for assigned engagement roles;
- United States-focused locale, consent, channel, knowledge, and operating policies stored as tenant data.

### 16.3 HaloEHS

HaloEHS is not provisioned in Phase 1. Its future configuration must use the same onboarding schema and cannot require source changes.

## 17. Acceptance criteria

### 17.1 Identity and navigation

- An ARA administrator authenticates once and opens RevenueOS, CommitArc, SignalLoop, and the tenant Admin Center without entering credentials again.
- An AI Consulting administrator receives the same seamless behavior through the neutral suite entry.
- An employee sees CommitArc and RevenueOS Essentials but cannot discover or invoke unassigned SignalLoop operations.
- An Engagement Operator sees assigned SignalLoop work but cannot administer providers, users, or AI policies.
- Removing a role or entitlement invalidates the corresponding session capability and queued work path.

### 17.2 Administration

- Platform Admin can create, configure, suspend, and inspect readiness for ARA and AI Consulting without reading their business records.
- Tenant Owner can invite users, assign bundles, publish branding, and review tenant audit.
- Product administrators see only their assigned configuration sections.
- The primary administrators for both tenants see all approved sections through one Admin Center.
- No administrator screen or API returns an existing password, password hash, provider secret, or bearer token.

### 17.3 Branding

- ARA's tenant entry renders the approved ARA suite design and all three product cards.
- AI Consulting renders the neutral configurable suite design.
- Direct generic CommitArc login remains unchanged.
- Branding preview passes desktop and narrow viewport checks without horizontal overflow.
- An unpublished or invalid draft cannot replace the current published version.

### 17.4 Tenant isolation

- ARA cannot list, search, fetch, update, delete, export, attach to, aggregate, infer, or operate on AI Consulting resources, and vice versa.
- Duplicate business identifiers may exist independently in both tenants.
- Platform Admin has no implicit data-plane bypass.
- Support access is tenant-scoped, expiring, and fully auditable.

### 17.5 Onboarding and failure recovery

- Repeating the same provisioning request produces the same tenant, product, membership, and invitation identities.
- A failure after CommitArc provisioning resumes SignalLoop or RevenueOS stages without duplicating CommitArc state.
- Activation is impossible until OIDC, isolation, entitlement, branding, policy, and native-integration evidence passes.
- Automated tests use synthetic addresses, non-routable contact data, fake providers, and no real outbound communications.

## 18. Delivery decomposition

The implementation must be split into separately reviewable plans and work packages:

1. Central OIDC adapter and cross-product subject mapping.
2. Platform control-plane tenant, entitlement, role-bundle, and support-access domains.
3. Tenant Admin Center and product-admin navigation.
4. Unified employee home with universal RevenueOS Essentials.
5. Tenant-domain resolution and branding publication.
6. ARA suite landing and AI Consulting neutral tenant entry.
7. Idempotent onboarding state machine and evidence bundle.
8. ARA and AI Consulting synthetic acceptance fixtures.

Each work package requires failing tests before implementation, specification review, quality review, tenant-adversarial verification, and a scoped commit in the owning repository.
