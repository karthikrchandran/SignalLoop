# Outreach Hub Cleanup Design

Date: 2026-06-16
Status: Approved design

## Goal

Clean up the current SignalLoop Outreach and Messaging Hub screens without a broad navigation rebuild. The work should make the product easier to understand, remove confusing wording, fix poor alignment, and add missing operator tools where the current screens do not scale.

The approved direction is Option A: keep the current routes and improve the existing surfaces.

## Scope

This design covers:

- Rename Prospecting to Lead Preparation.
- Reword Lead Preparation so operators understand the workflow.
- Add Contacts tabs for Contacts, Lead Groups, and Import.
- Add paginated Contacts browsing with filters.
- Add Lead Groups as saved lead sets with a detail screen.
- Simplify Controls around the supported pause and resume behavior.
- Add filtering and pagination to Templates.
- Make Sequences clearer by separating list, builder, enrollments, and performance concerns.
- Change Campaigns so it shows real campaigns first, while keeping the current intake wizard as Create Campaign.
- Fix the Analytics issue specifically under Messaging Hub > Analytics.
- Keep Dashboard links to Campaigns and Customer 360, but ensure they land on useful working screens.

This design does not include a replacement for the whole application shell, a new campaign backend, or a rewrite of main Outreach Analytics.

## Terminology

Use plain operator language.

| Current wording | New wording | Reason |
| --- | --- | --- |
| Prospecting | Lead Preparation | The page prepares selected leads for outreach instead of explaining what prospecting means. |
| Handoff queue | Leads needing follow-up | Handoff is unclear outside support/chat operations. |
| Run research | Build lead brief | Research sounds abstract; the output is a usable brief. |
| Research brief | Lead brief | Ties the output to the lead-preparation workflow. |
| Outreach handoff | Add to outreach | Directly names the action. |

Messaging Hub can still use handoff where the concept is specifically about a bot conversation escalated to a human.

## Navigation

Keep the existing Outreach and Messaging Hub sections. Update the Outreach item currently labeled Prospecting to Lead Preparation.

The expected Outreach navigation is:

- Dashboard
- Campaigns
- SignalLoop AI
- Customer 360
- Sequences
- Voice Agents
- Contacts
- Lead Preparation
- Analytics
- Templates
- Controls
- Settings

Messaging Hub remains separate:

- Channels
- Knowledge Base
- Inbox
- Analytics
- Settings

## Screen Designs

### Contacts

Contacts becomes a tabbed workspace:

- Contacts: paginated table of leads and contacts.
- Lead Groups: saved groups that can be reused by campaigns and lead preparation.
- Import: CSV template, upload, field mapping, validation, and import commit.

The Contacts tab should support:

- Search by name, email, company, or phone.
- Filters for company, industry, title, product interest, source, and contactability where data exists.
- Pagination controls with page size.
- Stable table layout that does not shift when loading or filtering.
- Clear empty state when there are no matching contacts.

The Import tab should keep the current import workflow but move it out of the top of the Contacts page so daily browsing is not buried under import controls.

### Lead Groups

Lead Groups are saved sets of leads. A group can be built from rules and can optionally include manually selected leads.

Supported grouping criteria for the first implementation:

- Industry
- Title or role
- Product interest
- Company
- Source
- Contactability, such as email-ready or voice-ready

The Lead Groups tab shows a paginated list of groups with name, match count, criteria summary, last updated date, and actions.

Clicking a group opens a Lead Group detail screen. The detail screen shows:

- Group name and description.
- Criteria editor.
- Matching leads table.
- Manual inclusions and exclusions if supported by current backend data.
- Actions to use the group in a campaign or lead-preparation workflow.

If backend support is not complete, the UI must show supported behavior only. Unsupported actions should be hidden or clearly disabled.

### Lead Preparation

The current Prospecting page becomes Lead Preparation.

The page should answer three questions:

1. Which leads need attention?
2. What do we know about the selected lead or account?
3. What is the next outreach action?

The left rail should be simplified:

- Leads needing follow-up list.
- Search and filters.
- Selected count.
- Select all and clear selection.

The main content should be:

- Selected lead summary.
- Build Lead Brief action for one lead.
- Build Briefs for Selected action for multiple leads.
- Lead brief output with account summary, likely needs, likely objections, personalization points, sources, and next action.
- Add to Outreach panel with campaign and sequence selectors.

The page should avoid unexplained labels such as handoff queue. If a lead came from Messaging Hub, show that as a source badge, not as the name of the whole queue.

### Campaigns

Campaigns should show actual campaigns before intake.

Use tabs:

- Campaign List
- Create Campaign

Campaign List should show:

- Campaign name
- Status
- Audience or lead group
- Sequence or channel strategy
- Created date
- Next action

Create Campaign uses the current intake wizard but improves wording:

- Campaign basics
- Audience selection
- Offer and channel strategy

The existing intake route can remain the implementation base, but the visible page should not make users think Campaigns only means intake.

### Templates

Templates can grow large, so the library needs browsing controls.

Add:

- Search by template name, subject, or content.
- Filters for channel, status, tag, and guardrail compliance.
- Pagination.
- A selected-template preview panel.
- Clear distinction between starter templates, drafts, published templates, and archived templates.

Starter templates should not dominate the page once the workspace has real templates.

### Sequences

Sequences should be distinct from Campaigns and Templates.

Use clear sections or tabs:

- Sequence List: existing sequences with status, campaign, steps, and enrollment count.
- Builder: create or edit ordered steps.
- Enrollments: contacts currently enrolled and status breakdown.
- Performance: delivery and response metrics when data is available.

The builder should keep explicit controls for delay, subject, body, and personalization tokens. Enrollment actions should be visually separate from editing actions so users do not confuse building a sequence with launching it.

### Controls

Controls should be simple and operational.

Prioritize:

- Current outreach state: active or paused.
- Optional pause reason.
- Pause all outreach.
- Resume outreach.

Remove or de-emphasize long explanatory blocks about unsupported policy editing from the main flow. If unsupported daily limits or quiet-hour editing must remain visible, place it in a compact "Not editable in this build" section below the supported emergency controls.

### Messaging Hub Analytics

The analytics bug is in Messaging Hub > Analytics, not the main Outreach Analytics page.

The Messaging Hub Analytics page should be verified and corrected for:

- Loading state.
- Error state.
- Empty state.
- Date range behavior.
- Conversation totals.
- Conversion funnel.
- Conversations over time chart.
- Channel breakdown chart.
- Outcome breakdown table.

If there is no data for the selected range, the page should show a clear no-data state instead of appearing broken. If the API fails, it should show a clear error with a retry action.

### Dashboard

Dashboard links to Campaigns and Customer 360 can remain.

Required behavior:

- Campaigns link opens the useful Campaign List view, not only the intake step.
- Customer 360 link opens the account list/profile workflow.
- Any dashboard card that is not wired to live data should either be removed, shown as an empty state, or clearly labeled as waiting for data.

## Data Flow

Use existing backend APIs where available:

- Contacts list and import APIs for Contacts and Import.
- Campaign APIs for Campaign List and Create Campaign.
- Sequence APIs for Sequence List, Builder, Enrollments, and progress.
- Template APIs for Templates.
- Existing prospecting APIs for Lead Preparation.
- Existing chatbot analytics API for Messaging Hub Analytics.

Where the UI needs filters or pagination that the backend does not yet support, prefer a small backend/API enhancement over large client-side filtering for production-sized data. Client-side filtering is acceptable only for starter/demo data or small response sets.

## Error Handling

Each affected screen must have:

- Loading state that preserves layout.
- Empty state with plain next-step copy.
- Error state with retry where retry is meaningful.
- Disabled buttons for unsupported or invalid actions.
- No decorative buttons that look clickable but do nothing.

## Testing

Implementation should include focused checks for:

- Sidebar label changes and route access.
- Contacts tabs, pagination, filtering, and import separation.
- Lead Groups list and detail navigation.
- Lead Preparation wording and primary actions.
- Campaigns defaulting to Campaign List.
- Templates filters and pagination.
- Sequences section separation and editor behavior.
- Controls pause and resume behavior.
- Messaging Hub Analytics loading, error, no-data, and chart rendering states.
- Dashboard links to Campaigns and Customer 360.

Run the frontend build and targeted Playwright coverage for changed routes before claiming the implementation is complete.

## Acceptance Criteria

- Users no longer see Prospecting in the sidebar; they see Lead Preparation.
- Lead Preparation avoids handoff and research jargon except where Messaging Hub escalation is specifically being described.
- Contacts has separate Contacts, Lead Groups, and Import tabs.
- Contacts browsing supports pagination and useful filters.
- Lead Groups can be opened into a detail screen.
- Campaigns opens to a campaign list and preserves campaign creation as a separate flow.
- Templates can be searched, filtered, paginated, and previewed.
- Sequences presents list, builder, enrollment, and performance concerns distinctly.
- Controls focuses on supported pause and resume behavior.
- Messaging Hub Analytics handles loading, error, empty, and populated states correctly.
- Dashboard links for Campaigns and Customer 360 land on useful working screens.
- The implementation does not introduce fake metrics, dead CTAs, or unsupported editable controls.
