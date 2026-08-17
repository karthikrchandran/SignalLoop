# SignalLoop User Guide

Version: August 16, 2026
Audience: outreach operators, Messaging Hub users, tenant administrators, and platform administrators

SignalLoop is the governed operating workspace for campaigns, voice, messaging, and account work. This guide reflects the routes and controls verified in the current local application. It distinguishes available workflows from screens that require connected providers, workers, or business data. Every screen below is shown once, in the order you would reach it by clicking through the left navigation.

## Start here

1. Open the SignalLoop URL supplied by your administrator.
2. Sign in with your work account. Use **Sign up** or **Forgot your password?** only when those actions are enabled for your deployment.
3. Confirm the workspace in the header and use the left navigation to open the needed area.
4. Start at **Dashboard** for operational status, or **Home** to choose a workspace area.

![Log in](screenshots/01-login.png)

If self-service accounts are enabled for your deployment, **Sign up** collects the details needed to request workspace access.

![Sign up](screenshots/02-sign-up.png)

**Forgot your password?** starts email-based recovery without involving an administrator.

![Password recovery](screenshots/03-password-recovery.png)

## Access and roles

- **Operator or standard user** works with the outreach and Messaging Hub surfaces granted to their workspace.
- **Tenant administrator / superuser** manages tenant people, products, branding, security, messaging, provider setup, and workspace configuration.
- **Platform administrator** manages tenant lifecycle, product policy, identity, support access, and audit from the control plane. Selecting a tenant there never grants access to its business data.

The application hides or redirects restricted screens. If an area is missing, ask a tenant administrator to review your membership and role; do not work around workspace access checks.

## Left-navigation modes

The three controls at the top of the left navigation switch the menu between product areas: **Outreach**, **Messaging**, and, for superusers, **Admin**. The inactive controls may appear as icons until selected; select one to expose its menu. The walkthroughs below follow each mode in left-to-right nav order, the way an operator would click through it.

### Outreach

Switching to Outreach exposes Home, Dashboard, Campaigns, SignalLoop AI, Customer 360, Sequences, Voice Agents, Meetings, Contacts, Lead Preparation, Analytics, Templates, Controls, and Settings.

#### Home

**Home** provides product and workflow shortcuts for choosing where to work next.

![Home](screenshots/04-home.png)

#### Dashboard

**Dashboard** is the operational view for campaign activity, contacts processed, Messaging Hub traffic, leads, meetings, escalations, channel health, agent operations, and calendar handoffs. Use its period selector and **Refresh** when reviewing current activity. Empty-state cards are normal in a new or unconnected workspace; they do not prove that a provider or worker is ready.

![Dashboard](screenshots/05-dashboard.png)

#### Campaigns

**Campaigns** has campaign work plus **Draft**, **Running**, and **Paused** lifecycle views. Start with a draft, review audience and channel strategy, then monitor its status.

![Campaigns](screenshots/06-campaigns.png)

![Draft campaigns](screenshots/07-campaigns-draft.png)

![Running campaigns](screenshots/08-campaigns-running.png)

![Paused campaigns](screenshots/09-campaigns-paused.png)

#### SignalLoop AI

**SignalLoop AI** groups next best actions, a unified work queue, journey signals, and knowledge gaps.

![SignalLoop AI](screenshots/10-signalloop-ai.png)

#### Customer 360

**Customer 360** is the account workspace for contacts, channel activity, and next action.

![Customer 360](screenshots/11-customer-360.png)

#### Sequences

**Sequences** is the multi-step outreach surface. Create or select a sequence, inspect its steps, then review enrollments and performance.

![Sequences](screenshots/12-sequences.png)

#### Voice Agents

**Voice Agents** lets you choose a voice profile, maintain campaign scripts, and check calling-provider readiness. Browser preview is a script check, not proof of a live outbound call.

![Voice Agents](screenshots/13-voice-agents.png)

#### Meetings

**Meetings** lists contacts that expressed booking interest and supports booking-link or booked-state follow-up.

![Meetings](screenshots/14-meetings.png)

#### Contacts

**Contacts** is the active-workspace lead pool. Download the CSV template when importing; filter and review contacts before using them in campaigns or sequences.

![Contacts](screenshots/15-contacts.png)

#### Lead Preparation

**Lead Preparation** selects contacts, builds lead briefs, and hands prepared contacts to campaigns or sequences.

![Lead Preparation](screenshots/16-lead-preparation.png)

#### Analytics

**Analytics** presents campaign, email, and voice performance; use the correct workspace and time range for decisions. The current **Reporting** route renders an error screen in the verified build — treat it as unavailable until repaired.

![Analytics](screenshots/17-analytics.png)

![Reporting error state](screenshots/18-reporting.png)

#### Templates

**Templates** provides starter templates and an editor. Preview tokens and publish only after unresolved tokens and policy issues are addressed.

![Templates](screenshots/19-templates.png)

#### Controls

**Controls** is the safety surface. **Pause all outreach** stops outbound activity across campaigns and sequences; record a reason and verify the pause before communicating that sends stopped.

![Controls](screenshots/20-controls.png)

#### Settings

**Settings** contains profile and password controls. Role-dependent tabs include opt-outs, workspace setup, and provider setup.

![User Settings](screenshots/21-settings.png)

**Provider Setup** is superuser-only and reports API, PostgreSQL, Redis, and worker readiness. Keep provider keys private. Worker cards can be stale or missing in a local build; do not treat the web UI alone as proof that a delivery worker processed a campaign, use the relevant operational health and delivery/audit evidence instead.

![Provider Setup](screenshots/22-provider-settings.png)

### Messaging

Switching to Messaging exposes Messaging Hub Channels, Knowledge Base, Inbox, Analytics, and Settings. Channel and knowledge-base administration requires the appropriate elevated role.

#### Channels

An authorized administrator connects a channel here. Live channels require provider credentials, provider IDs, webhook verification, and activation. No demo or empty-state card means that a provider is live — confirm credentials, webhook verification, and activation first.

![Messaging Hub Channels](screenshots/23-messaging-channels.png)

#### Knowledge Base

An administrator adds Website URLs, documents, or FAQ/Q&A entries here, then re-indexes and tests the bot as appropriate.

![Messaging Hub Knowledge Base](screenshots/24-messaging-knowledge-base.png)

#### Inbox

Operators work conversations here after connected channels receive messages. Use filters and select a thread for its detail.

![Messaging Hub Inbox](screenshots/25-messaging-inbox.png)

#### Analytics

Review conversations, containment, captured leads, escalations, conversion funnel, and channel outcomes.

![Messaging Hub Analytics](screenshots/26-messaging-analytics.png)

#### Settings

Authorized administrators maintain behavior here and review failed messages in **Admin > Dead Letters**.

![Messaging Hub Settings](screenshots/27-messaging-settings.png)

### Admin

Superusers use Admin for tenant people and roles, products, branding, security, messaging, audit, and dead letters. Standard users will not see this control. Admin is tenant-scoped; it is not a cross-tenant data browser.

#### Tenant administration

The landing screen for tenant people and roles, products, branding, security, messaging, and audit.

![Tenant administration](screenshots/28-admin.png)

#### People and roles

Manage tenant membership and role assignment.

![People and roles](screenshots/29-admin-members.png)

#### Tenant products

Manage which products — CommitArc, RevenueOS, SignalLoop — are entitled to the tenant.

![Tenant products](screenshots/30-admin-products.png)

#### Tenant security

Manage tenant-level security controls.

![Tenant security](screenshots/31-admin-security.png)

#### Tenant messaging

Manage tenant messaging configuration; this is separate from Messaging Hub's own Settings tab.

![Tenant messaging](screenshots/32-admin-messaging.png)

#### Tenant audit

Review the tenant audit trail.

![Tenant audit](screenshots/33-admin-audit.png)

#### Tenant branding

Manage tenant branding assets and versioning.

![Tenant branding](screenshots/34-admin-branding.png)

#### Messaging dead letters

Review Messaging Hub messages that failed delivery.

![Messaging dead letters](screenshots/35-admin-dead-letters.png)

#### CommitArc administration

Tenant-scoped administration for the CommitArc product.

![CommitArc administration](screenshots/36-admin-commit-arc.png)

#### RevenueOS administration

Tenant-scoped administration for the RevenueOS product.

![RevenueOS administration](screenshots/37-admin-revenue-os.png)

#### SignalLoop administration

Tenant-scoped administration for the SignalLoop product.

![SignalLoop administration](screenshots/38-admin-signalloop.png)

## Platform administration

**Platform** is the suite control plane for tenant lifecycle, products, identity, messaging defaults, provider policies, usage and health, support access, and audit. It sits outside the three tenant-scoped nav modes above and is reserved for platform administrators. Selecting a tenant here never grants access to its business data, and support access should be approved, time-bound, revocable, and audited.

#### Platform administration

Landing screen for platform-wide administration.

![Platform administration](screenshots/39-platform.png)

#### Platform tenants

Manage tenant lifecycle across the platform.

![Platform tenants](screenshots/40-platform-tenants.png)

#### Platform identity

Manage platform identity configuration.

![Platform identity](screenshots/41-platform-identity.png)

#### Platform products

Manage product policy across the platform.

![Platform products](screenshots/42-platform-products.png)

#### Provider policies

Manage provider policy defaults.

![Provider policies](screenshots/43-platform-provider-policies.png)

#### Support access

Grant and review time-bound, auditable support access to a tenant.

![Support access](screenshots/44-platform-support-access.png)

#### Messaging defaults

Manage platform-wide messaging defaults.

![Messaging defaults](screenshots/45-platform-messaging.png)

#### Platform audit

Review the platform-wide audit trail.

![Platform audit](screenshots/46-platform-audit.png)

#### Usage and health

Review platform usage and health metrics.

![Usage and health](screenshots/47-platform-usage-health.png)

## Revenue OS

**Revenue OS** provides the cross-product operating view for EngageHub, ChatHub, Sales Ops, Operations, Finance, Performance, and Platform administration. Each linked product continues to enforce its own authorization controls.

![Revenue OS](screenshots/48-revenue-os.png)

## Troubleshooting

### Expected workspace or menu is missing

Verify that you signed into the correct work account, then ask a tenant administrator to verify membership and role. A browser-stored workspace selection is never a substitute for server-side access checks.

### A channel, campaign, or dashboard is empty

Check whether the workspace has business data, a connected provider, and running workers. For live delivery, verify provider activation, worker health, and delivery/audit evidence.

### A page shows “Failed to fetch” or an error screen

Refresh once and confirm application health. If it persists, record the route, timestamp, and visible error for support. A browser shell loading is not proof that the screen data loaded.

## Screenshot reference

Playwright captured 48 authenticated, 1440 × 1080 route screenshots in [`screenshots/`](screenshots/), each shown once above in its place in the left-navigation walkthrough.

| Area | Captures |
| --- | --- |
| Public access | `01-login` through `03-password-recovery` |
| Outreach workspace | `04-home` through `22-provider-settings` |
| Messaging Hub | `23-messaging-channels` through `27-messaging-settings` |
| Tenant administration | `28-admin` through `38-admin-signalloop` |
| Platform administration | `39-platform` through `47-platform-usage-health` |
| Revenue OS | `48-revenue-os` |

Dynamic account and conversation-detail routes are not in the set because the verified workspace contained no account or conversation records.
