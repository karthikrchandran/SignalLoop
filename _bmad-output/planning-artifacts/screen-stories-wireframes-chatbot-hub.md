---
workflowType: bmad-screen-stories-wireframes
date: "2026-06-05"
project: "SignalLoop - ChatBot Hub"
sourceDocuments:
  - _bmad-output/planning-artifacts/prd-chatbot-hub.md
  - _bmad-output/planning-artifacts/architecture-chatbot-hub.md
  - _bmad-output/planning-artifacts/ux-design-chatbot-hub.md
  - _bmad-output/planning-artifacts/epics.md
status: draft-ready-for-review
integrationModel: "Same SignalLoop portal; Chatbot section in existing sidebar"
designSystem: "shadcn/ui New York + Tailwind CSS + Lucide React"
---

# ChatBot Hub Screen-Level Stories and Wireframes

## Purpose

This artifact turns the approved ChatBot Hub UX specification into screen-level implementation stories and low-fidelity wireframes. It is intended to sit between the UX spec and implementation stories:

- Product can review user flows screen by screen.
- Engineering can derive frontend routes, components, API needs, and state handling.
- QA can build screen acceptance tests from visible states and transitions.

ChatBot Hub is not a separate portal. All screens below live inside the existing SignalLoop shell with the current auth, workspace, sidebar, role, and theme model.

## Screen Map

| Screen ID | Route | Primary user | Main outcome | Required role |
|---|---|---|---|---|
| CBH-S00 | Global shell | Admin, Agent | Access Chatbot navigation inside SignalLoop | Admin, Agent |
| CBH-S01 | /chatbot/channels | Admin | Connect and monitor official channels | Admin |
| CBH-S02 | Channel connection sheet | Admin | Save and verify channel credentials | Admin |
| CBH-S03 | /chatbot/knowledge-base | Admin | Add, index, and monitor knowledge sources | Admin |
| CBH-S04 | Test Bot sheet | Admin | Validate RAG answers before channels go live | Admin |
| CBH-S05 | /chatbot/inbox | Admin, Agent | Triage live conversation threads | Admin, Agent |
| CBH-S06 | /chatbot/inbox/$threadId | Admin, Agent | Read history, reply, resolve, or re-enable bot | Admin, Agent |
| CBH-S07 | /chatbot/analytics | Admin, Agent | Review chatbot performance | Admin, Agent read |
| CBH-S08 | /chatbot/settings | Admin | Configure bot behavior and compliance defaults | Admin |
| CBH-S09 | /settings, Opt-outs tab | Admin | Manage opted-out visitors after confirmed consent | Admin |
| CBH-S10 | /admin/chatbot/dead-letters | Operator | View and retry dead-lettered chatbot messages | Operator/Superuser |

## Repo-Conformant Route Notes

The current web app uses TanStack Router file routes under `apps/web/src/routes/_layout`. Existing nested settings use a flat dot route file such as `settings.providers.tsx`.

Recommended ChatBot Hub route files:

| Public route | Route file |
|---|---|
| /chatbot/channels | `apps/web/src/routes/_layout/chatbot.channels.tsx` |
| /chatbot/knowledge-base | `apps/web/src/routes/_layout/chatbot.knowledge-base.tsx` |
| /chatbot/inbox | `apps/web/src/routes/_layout/chatbot.inbox.tsx` |
| /chatbot/inbox/$threadId | `apps/web/src/routes/_layout/chatbot.inbox.$threadId.tsx` |
| /chatbot/analytics | `apps/web/src/routes/_layout/chatbot.analytics.tsx` |
| /chatbot/settings | `apps/web/src/routes/_layout/chatbot.settings.tsx` |
| /admin/chatbot/dead-letters | `apps/web/src/routes/_layout/admin.chatbot-dead-letters.tsx` or nested admin route if the router is refactored |

Recommended feature folder:

```text
apps/web/src/features/chatbot/
  api.ts
  ChannelsPage.tsx
  KnowledgeBasePage.tsx
  InboxPage.tsx
  ThreadDetailPage.tsx
  AnalyticsPage.tsx
  BotSettingsPage.tsx
  components/
    ChannelCard.tsx
    ChannelConnectionSheet.tsx
    KnowledgeSourceRow.tsx
    IndexingProgressBanner.tsx
    TestBotSheet.tsx
    ThreadRow.tsx
    MessageBubble.tsx
    ReplyComposer.tsx
    WhatsAppWindowBanner.tsx
    ChatbotStatusBadge.tsx
```

Do not hand-edit `routeTree.gen.ts` unless project routing codegen is unavailable; prefer the existing route generation workflow.

---

## CBH-S00: Global Chatbot Navigation

### Screen Story

As a workspace admin or support agent, I want a Chatbot section in the existing SignalLoop sidebar so that I can move between setup, inbox, analytics, and settings without leaving the portal.

### Requirements Trace

- UX-DR1
- PRD roles: Workspace Admin, Support/Ops Agent
- Architecture: React routes under existing shell; same JWT workspace scope

### Wireframe

```text
+---------------------------+-----------------------------------------------+
| SignalLoop                 | Existing route content                         |
|---------------------------|                                               |
| Dashboard                 |                                               |
| Campaigns                 |                                               |
| Sequences                 |                                               |
| Voice Agents              |                                               |
|                           |                                               |
| Chatbot                   |                                               |
|   Plug  Channels          |                                               |
|   Book  Knowledge Base    |                                               |
|   Inbox Inbox        [3]  |                                               |
|   Chart Analytics         |                                               |
|   Sliders Settings        |                                               |
|                           |                                               |
| Contacts                  |                                               |
| Analytics                 |                                               |
| Templates                 |                                               |
| Settings                  |                                               |
+---------------------------+-----------------------------------------------+
```

### States

| State | Behavior |
|---|---|
| Admin | Shows Channels, Knowledge Base, Inbox, Analytics, Settings |
| Agent | Shows Inbox and Analytics only unless role model later allows setup access |
| No open escalations | Inbox badge hidden |
| One or more open escalations | Inbox badge shown using destructive badge |
| Sidebar collapsed | Chatbot group remains discoverable through icons and tooltips |

### Acceptance Criteria

1. Given an admin signs in, when the sidebar renders, then the Chatbot group is visible with five child links.
2. Given an agent signs in, when the sidebar renders, then setup and settings links are hidden and inbox/analytics remain visible.
3. Given open escalation count is zero, when the sidebar renders, then no empty badge placeholder appears.
4. Given open escalation count is greater than zero, when the sidebar renders, then the Inbox item shows that count.
5. Given a user is on any `/chatbot/*` route, when the sidebar renders, then the matching route is visibly active.

---

## CBH-S01: Channels Page

### Screen Story

As a workspace admin, I want to see all supported channels and their health at a glance so that I can connect, disconnect, and diagnose Facebook, WhatsApp, and Telegram from one place.

### Requirements Trace

- CH1-CH6, CH8
- UX-DR2 ChannelCard
- Routes: `/chatbot/channels`
- API: `GET /api/v1/chatbot/channels`, `POST /api/v1/chatbot/channels`, `PATCH /api/v1/chatbot/channels/{id}/toggle`

### Wireframe

```text
+--------------------------------------------------------------------------------+
| Channels                                                        [Refresh]        |
| Connect official messaging channels to the shared chatbot brain.                |
|--------------------------------------------------------------------------------|
|                                                                                |
| +-------------------------+ +-------------------------+ +---------------------+ |
| | Facebook Messenger      | | WhatsApp Business       | | Telegram Bot        | |
| | Status: Connected       | | Status: Error           | | Status: Not set up  | |
| | Last webhook: 2m ago    | | Last error: 401 token   | | Last webhook: --    | |
| | Bot: Active             | | Bot: Inactive           | | Bot: Off            | |
| |                         | |                         | |                     | |
| | [Disconnect] [Edit]     | | [Reconnect] [Details]   | | [Connect]           | |
| +-------------------------+ +-------------------------+ +---------------------+ |
|                                                                                |
| Connection events                                                               |
| ------------------------------------------------------------------------------ |
| 10:42 Facebook webhook verified                                                |
| 10:40 WhatsApp send failed after 3 retries                                      |
+--------------------------------------------------------------------------------+
```

### States

| State | Visible UI |
|---|---|
| Disconnected | Gray status, Connect button |
| Connecting/verifying | Spinner in card, action disabled, inline progress copy |
| Connected active | Green status, last webhook timestamp, Disconnect/Edit actions |
| Connected inactive | Neutral status, Activate/Edit actions |
| Error | Red status, last error summary, Reconnect/Details actions |
| Pending provider approval | Amber status, Details action |

### Acceptance Criteria

1. Given channel data loads successfully, when the page renders, then three ChannelCard components are visible for Facebook, WhatsApp, and Telegram.
2. Given a channel is connected, when its card renders, then the card shows live/inactive/error status and last webhook timestamp.
3. Given a channel is disconnected, when its card renders, then the primary action is Connect.
4. Given a provider error exists, when the card renders, then the error is visible without opening a modal.
5. Given the admin toggles a channel inactive, when the API succeeds, then the card updates without deleting credentials.

---

## CBH-S02: Channel Connection Sheet

### Screen Story

As a workspace admin, I want a focused connection sheet per channel so that I can enter credentials, verify the webhook, and return to the Channels page with clear success or correction guidance.

### Requirements Trace

- CH2, CH3, CH5
- WS1
- UX journey: Admin connects a channel
- Component: `ChannelConnectionSheet`

### Wireframe

```text
+------------------------------------------------------+-------------------------+
| Channels page behind sheet                           | Connect WhatsApp        |
|                                                      |-------------------------|
|                                                      | Phone Number ID         |
|                                                      | [____________________]  |
|                                                      | Access Token            |
|                                                      | [____________________]  |
|                                                      | Webhook Verify Token    |
|                                                      | [____________________]  |
|                                                      | Bot display name        |
|                                                      | [Aria from Acme______]  |
|                                                      | Greeting message        |
|                                                      | [textarea___________]   |
|                                                      |                         |
|                                                      | [Cancel] [Save & Verify]|
+------------------------------------------------------+-------------------------+
```

### States

| State | Behavior |
|---|---|
| New channel | Empty credentials, defaults for bot name/messages |
| Existing channel | Credentials masked; editable non-secret settings visible |
| Save in progress | Save and Cancel disabled; button shows loading |
| Verification failed | Sheet remains open; field-level or page-level error shown |
| Verification succeeds | Sheet closes; Channels page card updates; success toast shown |

### Acceptance Criteria

1. Given the sheet opens, when rendered, then focus moves to the first field.
2. Given required fields are empty, when Save & Verify is clicked, then inline errors appear and no API request is sent.
3. Given verification fails, when the API returns error details, then the sheet stays open and the error is visible.
4. Given verification succeeds, when the API returns success, then the sheet closes and the relevant ChannelCard updates.
5. Given the sheet closes, when focus returns, then it returns to the triggering Connect/Edit button.

---

## CBH-S03: Knowledge Base Page

### Screen Story

As a workspace admin, I want one Knowledge Base page for URLs, documents, and FAQs so that I can build the shared bot brain without writing code.

### Requirements Trace

- KB1-KB9
- KB7-KB8 re-indexing
- UX-DR5 progress banner
- Components: `KnowledgeSourceRow`, `IndexingProgressBanner`
- API: `/api/v1/chatbot/knowledge-sources`

### Wireframe

```text
+--------------------------------------------------------------------------------+
| Knowledge Base                                             [Test Bot] [Re-index] |
| Add sources once. All channels answer from this shared workspace knowledge.     |
|--------------------------------------------------------------------------------|
| Indexing 12 pages... 38% | estimated 2 min remaining                    [x]    |
|--------------------------------------------------------------------------------|
| [Website URLs] [Documents] [FAQ / Q&A]                                          |
|                                                                                |
| Website URLs                                                                   |
| +--------------------------------------------------------------------------+   |
| | https://acme.com                                                          |   |
| | https://acme.com/pricing                                                  |   |
| +--------------------------------------------------------------------------+   |
| [Crawl & Index]                                                             |   |
|                                                                                |
| Sources                                                                        |
| ------------------------------------------------------------------------------ |
| Globe acme.com                 Indexed      247 chunks   Last indexed 5m ago   |
| File product-catalog.pdf       Indexing     62%          Started 1m ago        |
| FAQ  Refund policy             Stale        4 chunks     Edited today          |
| Error old-brochure.pdf         Failed       View details                       |
+--------------------------------------------------------------------------------+
```

### States

| State | Visible UI |
|---|---|
| Empty KB | Source empty state and disabled Test Bot prompt explaining no content |
| URL entry | Multiline URL textarea; Crawl & Index action |
| Document upload | Drag/drop upload area; 20 MB validation |
| FAQ/Q&A | Row editor with Add Entry and delete actions |
| Indexing | Progress banner below header; rows show progress/status |
| Stale source | Amber stale status; Re-index All enabled |
| Failed source | Error status and View Details action |

### Acceptance Criteria

1. Given no sources exist, when the page renders, then the empty state invites URL, document, or FAQ entry creation.
2. Given URLs are submitted, when the admin clicks Crawl & Index, then source creation is requested and the progress banner appears.
3. Given a document larger than 20 MB is dropped, when validation runs, then the file is rejected before upload with inline error.
4. Given a source is edited after indexing, when the source list renders, then the source is marked Stale and Re-index All is enabled.
5. Given indexing completes, when the page receives the update, then chunk counts and last indexed timestamps refresh.

---

## CBH-S04: Test Bot Sheet

### Screen Story

As a workspace admin, I want to test bot answers against the current knowledge base so that I can trust the bot before activating public channels.

### Requirements Trace

- KB12
- BOT5 grounding
- BOT11 AI disclosure
- UX-DR3
- API: `POST /api/v1/chatbot/test`

### Wireframe

```text
+------------------------------------------------------+-------------------------+
| Knowledge Base page behind sheet                     | Test Bot                |
|                                                      |-------------------------|
|                                                      | Empty/History area      |
|                                                      |                         |
|                                                      | Admin: refund policy?   |
|                                                      |                         |
|                                                      | Bot                     |
|                                                      | Badge: I'm an AI        |
|                                                      | We offer a full refund  |
|                                                      | within 14 days...       |
|                                                      |                         |
|                                                      | Based on                |
|                                                      | FileSearch Refund FAQ   |
|                                                      | Score 92%               |
|                                                      |                         |
|                                                      | [Ask your bot...] [Send]|
+------------------------------------------------------+-------------------------+
```

### States

| State | Behavior |
|---|---|
| No KB content | Input disabled or response explains content is required |
| Ready | Input enabled; answer appears within 5 seconds p95 target |
| Low confidence | Shows inability/escalation-style answer and low score |
| Error | Inline retry affordance; sheet remains open |
| Multiple questions | Scrollable history preserved within sheet session |

### Acceptance Criteria

1. Given the Test Bot button is clicked, when the sheet opens, then it displays a chat-style interface with input focused.
2. Given the KB has no indexed chunks, when the sheet opens, then it shows a no-content state.
3. Given the admin sends a question, when the test API responds, then the answer shows AI disclosure, response text, and retrieved source chunks with similarity score.
4. Given the test API fails, when the error is returned, then the sheet shows retry feedback without closing.
5. Given the sheet closes, when it closes, then focus returns to the Test Bot trigger.

---

## CBH-S05: Inbox Thread List

### Screen Story

As a support agent, I want a real-time inbox with clear status filters so that I can triage escalations without missing urgent conversations.

### Requirements Trace

- HH1, HH2, HH7, HH8
- UX-DR4
- Components: `ThreadRow`
- API: `GET /api/v1/chatbot/inbox/threads`, SSE `/api/v1/chatbot/inbox/events`

### Wireframe

```text
+--------------------------------------------------------------------------------+
| Inbox                                                                          |
| All conversations across connected chatbot channels.                           |
|--------------------------------------------------------------------------------|
| +--------------------------------------+ +-----------------------------------+ |
| | [All] [Escalated] [Bot] [Resolved]   | | Select a thread or open detail    | |
| | Channel: All      Date: Last 7 days  | |                                   | |
| |--------------------------------------| |                                   | |
| | amber WhatsApp  Maya Chen       1m   | |                                   | |
| |      "Can I talk to someone?"        | |                                   | |
| |      Escalated                       | |                                   | |
| |--------------------------------------| |                                   | |
| | blue Facebook  Alex P.          5m   | |                                   | |
| |      "Do you support teams?"         | |                                   | |
| |      Bot Active                      | |                                   | |
| |--------------------------------------| |                                   | |
| | gray Telegram @sam             22m   | |                                   | |
| |      "STOP"                         | |                                   | |
| |      Opted Out                       | |                                   | |
| +--------------------------------------+ +-----------------------------------+ |
+--------------------------------------------------------------------------------+
```

### States

| State | Behavior |
|---|---|
| Loading | Skeleton rows matching thread row shape |
| Empty | Empty state explains conversations appear after channels receive messages |
| New escalation | Insert at top, amber highlight, toast, sidebar badge increment |
| SSE disconnected | Shows subtle reconnecting state and falls back to polling |
| Tablet | Single-panel list; opening thread navigates to detail view |

### Acceptance Criteria

1. Given threads exist, when the inbox loads, then rows are sorted by last activity descending with escalated rows visually prominent.
2. Given filters are changed, when the user selects channel/status/date filters, then the list refetches with those query params.
3. Given an SSE escalation event arrives, when the inbox is open, then the new thread appears without page refresh.
4. Given SSE disconnects, when fallback starts, then the page polls every 30 seconds and remains usable.
5. Given there are no conversations, when the page renders, then the empty state is visible.

---

## CBH-S06: Thread Detail

### Screen Story

As a support agent, I want to open a conversation, see full bot and visitor context, reply as a human, and resolve the thread so that escalations are handled cleanly.

### Requirements Trace

- HH3-HH6
- NFR-CB15 WhatsApp 24-hour window
- OC2 opted-out state
- UX-DR2 MessageBubble, WhatsAppWindowBanner
- APIs: thread detail, reply, resolve, reopen

### Wireframe: Normal Reply State

```text
+--------------------------------------------------------------------------------+
| Inbox                                                                          |
|--------------------------------------------------------------------------------|
| Thread list                          | Maya Chen     WhatsApp     Escalated     |
|                                      |                           [Resolve] [..] |
|                                      |------------------------------------------|
|                                      | Visitor                                  |
|                                      | "Do you have a plan for 5 users?"        |
|                                      | 10:41                                    |
|                                      |                                          |
|                                      | Bot                                      |
|                                      | Badge: I'm an AI assistant.              |
|                                      | "Yes, the Team plan supports..."         |
|                                      | 10:41                                    |
|                                      |                                          |
|                                      | Visitor                                  |
|                                      | "Can I talk to someone?"                |
|                                      | 10:42                                    |
|                                      |------------------------------------------|
|                                      | [Reply as K.R....                    ]   |
|                                      |                                  [Send]  |
+--------------------------------------------------------------------------------+
```

### Wireframe: WhatsApp Window Expired

```text
+--------------------------------------+-----------------------------------------+
| Thread list                          | Maya Chen     WhatsApp     Escalated    |
|                                      |-----------------------------------------|
|                                      | Message history                         |
|                                      |-----------------------------------------|
|                                      | Warning                                 |
|                                      | WhatsApp 24-hour messaging window has   |
|                                      | expired. The visitor must send a        |
|                                      | message first to reopen the conversation.|
+--------------------------------------+-----------------------------------------+
```

### Wireframe: Opted-Out Visitor

```text
+--------------------------------------+-----------------------------------------+
| Thread list                          | @sam        Telegram       Opted Out     |
|                                      |-----------------------------------------|
|                                      | Message history                         |
|                                      |-----------------------------------------|
|                                      | Visitor has opted out. Bot engagement   |
|                                      | is disabled for this channel visitor.   |
|                                      | Human reply is available only if the    |
|                                      | visitor re-initiated contact.           |
+--------------------------------------+-----------------------------------------+
```

### States

| State | Behavior |
|---|---|
| Escalated | Reply composer enabled, Resolve primary action |
| Agent active | Reply composer enabled; status badge updates |
| Resolved | Read-only history; Re-open action visible |
| WhatsApp expired | Reply composer replaced by non-dismissable warning |
| Opted out | Bot controls disabled; opt-out notice visible |
| Bot active | Re-enable/disable bot action reflects current status |

### Acceptance Criteria

1. Given a thread is selected, when detail loads, then it shows metadata, full ordered message history, and status-specific actions.
2. Given messages render, when sender role differs, then MessageBubble variants distinguish bot, visitor, and agent.
3. Given a bot message renders, when visible, then the AI disclosure badge is included.
4. Given WhatsApp window is expired, when the detail renders, then the reply input is replaced by WhatsAppWindowBanner.
5. Given an agent sends a valid reply, when the API succeeds, then the message appears immediately and status becomes agent-active.
6. Given the agent resolves a thread, when the API succeeds, then the thread moves to resolved state.

---

## CBH-S07: Analytics Page

### Screen Story

As a workspace admin or agent, I want chatbot-specific analytics so that I can understand channel usage, containment, escalations, and lead capture outcomes.

### Requirements Trace

- AN1-AN4
- Architecture analytics snapshots
- Route: `/chatbot/analytics`
- API: `GET /api/v1/chatbot/analytics`

### Wireframe

```text
+--------------------------------------------------------------------------------+
| Analytics                                      Date: [Last 7 days] [Refresh]    |
| Chatbot performance for the current workspace.                    Updated 5m    |
|--------------------------------------------------------------------------------|
| +----------------+ +----------------+ +----------------+ +-------------------+ |
| | Conversations  | | Containment    | | Leads Captured | | Escalations       | |
| | 240            | | 87%            | | 31             | | 18                | |
| +----------------+ +----------------+ +----------------+ +-------------------+ |
|                                                                                |
| +--------------------------------------+ +-----------------------------------+ |
| | Conversations over time              | | Channel breakdown                 | |
| | line chart                           | | bar chart                         | |
| +--------------------------------------+ +-----------------------------------+ |
|                                                                                |
| Outcome breakdown                                                               |
| Channel      Bot-resolved   Escalated   Lead-captured   Opted-out              |
| WhatsApp     112            9           22              3                      |
| Facebook     77             7           8               2                      |
| Telegram     20             2           1               0                      |
+--------------------------------------------------------------------------------+
```

### States

| State | Behavior |
|---|---|
| Loading | Stat card and chart skeletons |
| No data | Zero values and explanatory empty state |
| Date range changed | Refetches analytics; does not reload page |
| Agent role | Read-only; export if added later remains admin-only |
| Admin role | Can use export action if implemented |

### Acceptance Criteria

1. Given analytics data exists, when the page renders, then it shows four stat cards, two charts, and outcome breakdown table.
2. Given the date range changes, when applied, then the API is called with matching date query params.
3. Given analytics data was updated recently, when the page renders, then an Updated X min ago badge is visible.
4. Given no data exists, when the page renders, then empty states avoid chart errors.
5. Given an agent views the page, when rendered, then the data is read-only.

---

## CBH-S08: Bot Settings Page

### Screen Story

As a workspace admin, I want one settings page for bot identity, disclosure, business hours, lead capture, and retention so that I can safely configure chatbot behavior.

### Requirements Trace

- CH5, CH7, CH9
- BOT11
- LC settings
- NFR-CB12, NFR-CB16
- Route: `/chatbot/settings`
- API: `GET /api/v1/chatbot/config`, `PUT /api/v1/chatbot/config`

### Wireframe

```text
+--------------------------------------------------------------------------------+
| Bot Settings                                                   [Save Changes]   |
| Configure workspace-level chatbot behavior and compliance defaults.             |
|--------------------------------------------------------------------------------|
| AI & Disclosure                                                                 |
| AI disclosure text                                                              |
| [I'm an AI assistant._____________________________________________________]     |
| Token cap per session [4000]                                                    |
|--------------------------------------------------------------------------------|
| Lead Capture                                                                    |
| Enable lead capture [on]                                                        |
| Minimum turns [3]     Intent keywords [demo, pricing, buy]                      |
| Privacy policy URL [https://acme.com/privacy______________________________]     |
|--------------------------------------------------------------------------------|
| Business Hours                                                                  |
| Enable out-of-hours mode [on] Timezone [Asia/Singapore]                         |
| Mon [09:00] - [18:00] Tue [09:00] - [18:00] ...                                 |
| Out-of-hours message [textarea____________________________________________]     |
|--------------------------------------------------------------------------------|
| Compliance                                                                      |
| Retention days [90]       Opt-outs [Open settings tab]                          |
|                                                                                |
| Sticky bar: You have unsaved changes.        [Discard] [Save Changes]           |
+--------------------------------------------------------------------------------+
```

### States

| State | Behavior |
|---|---|
| Clean | No sticky bar; fields match saved config |
| Dirty | Sticky bar visible with Save and Discard |
| Validation error | Field-level errors; save blocked or returns inline error |
| Saving | Save button loading; fields remain visible |
| Saved | Toast shown; sticky bar disappears |

### Acceptance Criteria

1. Given the page loads, when config API succeeds, then all settings sections are populated.
2. Given any field is edited, when value differs from saved config, then sticky unsaved-changes bar appears.
3. Given AI disclosure is blank, when saving is attempted, then save is blocked and inline error is shown.
4. Given retention is less than 30 days, when saving is attempted, then inline minimum retention error is shown.
5. Given save succeeds, when response returns, then the sticky bar disappears and saved values remain.

---

## CBH-S09: Opt-Out Management Tab

### Screen Story

As a workspace admin, I want to view opted-out visitors and manually re-enable bot engagement only after confirming re-consent so that compliance controls are auditable and deliberate.

### Requirements Trace

- OC1-OC4
- UX-DR6
- Existing route: `/settings`, new tab
- API: `GET /api/v1/chatbot/opt-outs`, `DELETE /api/v1/chatbot/opt-outs/{id}`

### Wireframe

```text
+--------------------------------------------------------------------------------+
| User Settings                                                                  |
| [Profile] [Workspace Setup] [Providers] [Opt-outs]                              |
|--------------------------------------------------------------------------------|
| Opt-outs                                                                       |
| Visitors who requested bot opt-out in this workspace.                           |
|                                                                                |
| Channel     Visitor           Opted out at       By        Action               |
| WhatsApp    +14155550100      Jun 4, 2026 10:21  Visitor   [Re-enable]         |
| Telegram    @sam              Jun 3, 2026 16:05  Visitor   [Re-enable]         |
|                                                                                |
| Confirm dialog:                                                                |
| Re-enabling bot engagement requires explicit visitor re-consent.                |
| [Cancel] [Confirm re-consent and re-enable]                                    |
+--------------------------------------------------------------------------------+
```

### States

| State | Behavior |
|---|---|
| No opt-outs | Empty table state |
| Rows exist | Paginated table, 25 per page |
| Re-enable clicked | Confirmation dialog; explicit confirm required |
| Re-enable success | Row removed or marked inactive; audit event written |
| Non-admin role | Tab hidden or route rejected |

### Acceptance Criteria

1. Given an admin opens Settings, when tabs render, then Opt-outs tab is available.
2. Given opted-out visitors exist, when the tab renders, then channel, visitor, timestamp, actor, and action are visible.
3. Given the admin clicks Re-enable, when dialog opens, then it explicitly requires confirmation of visitor re-consent.
4. Given confirmation succeeds, when API returns success, then the row is removed and an audit event is recorded.
5. Given a non-admin attempts access, when route guard runs, then access is denied.

---

## CBH-S10: Dead-Letter Operator Recovery

### Screen Story

As an operator, I want to view and retry dead-lettered chatbot messages so that verified inbound messages do not disappear silently after worker failures.

### Requirements Trace

- CH8 provider error visibility
- WS3 retry/dead-letter
- WS4 audit logging
- WS5 duplicate prevention
- Architecture: `GET /api/v1/chatbot/dead-letters`, `POST /api/v1/chatbot/dead-letters/{id}/retry`
- Implementation story: CBH-E2-S5

### Wireframe

```text
+--------------------------------------------------------------------------------+
| Operator / Chatbot Dead Letters                                  [Refresh]      |
| Verified messages that failed all worker retries.                               |
|--------------------------------------------------------------------------------|
| +----------------+ +----------------+ +----------------+ +-------------------+ |
| | Failed         | | Retries today  | | Top channel    | | Oldest failed     | |
| | 4              | | 11             | | WhatsApp       | | 2h ago            | |
| +----------------+ +----------------+ +----------------+ +-------------------+ |
|                                                                                |
| Dead-letter queue                                                              |
| Message ID      Channel     Last error        Attempts   Failed at    Action   |
| wamid.HBg...    WhatsApp    401 invalid token 3          10:40        Retry    |
| m_982341        Facebook    LLM timeout       3          10:18        Retry    |
| tg_7718         Telegram    Index unavailable 3          09:51        Retry    |
|                                                                                |
| Retry requeues the original payload. Deduplication still prevents duplicate     |
| bot responses.                                                                 |
+--------------------------------------------------------------------------------+
```

### States

| State | Behavior |
|---|---|
| Empty | Shows "No dead-lettered chatbot messages." |
| Failed records exist | Operator table lists channel, message ID, last error, attempts, failed timestamp, retry action |
| Retry clicked | Confirmation or inline loading state; message requeued on success |
| Retry success | Row marked retried or removed; audit event written |
| Retry failed | Inline error shows new failure reason |
| Unauthorized | Non-operator users cannot access the route |

### Acceptance Criteria

1. Given an operator opens the dead-letter route, when records exist, then the table shows message ID, channel, error, attempts, failed timestamp, and retry action.
2. Given a non-operator opens the route, when route guard runs, then access is denied.
3. Given the operator retries a record, when the API succeeds, then the original payload is requeued and the row state updates.
4. Given retry is attempted for a duplicate message, when deduplication applies, then no duplicate bot response is sent.
5. Given a retry action completes, when audit logs are reviewed, then the operator, workspace, dead-letter ID, and result are recorded.

---

## Cross-Screen Flow Stories

### Flow F1: First Setup to Trust Moment

```text
Channels -> Knowledge Base -> Test Bot -> Channels active
```

As an admin, I want to add a website, wait for indexing, test the bot, and then activate a channel so that I can safely go live.

Acceptance path:

1. Admin opens Channels and sees at least one disconnected channel.
2. Admin opens Knowledge Base, adds URLs, and sees indexing progress.
3. Admin opens Test Bot and gets a grounded response with source citation.
4. Admin returns to Channels and activates Facebook or WhatsApp.

### Flow F2: Escalation to Agent Resolution

```text
Visitor asks channel question -> Bot escalates -> Inbox updates -> Agent replies -> Resolve
```

As an agent, I want escalations to appear in real time with full context so that I can reply without asking the visitor to repeat themselves.

Acceptance path:

1. Escalation event arrives through SSE.
2. Thread row appears at top with highlighted status.
3. Agent opens detail and sees visitor, bot, and escalation reason.
4. Agent sends reply and status becomes agent-active.
5. Agent resolves thread and it moves to resolved state.

### Flow F3: Compliance Interruption

```text
Visitor sends STOP -> Bot stops -> Inbox shows opted-out -> Admin manages opt-out
```

As an admin, I want opt-out behavior to be visible and controlled so that the bot does not re-engage a visitor improperly.

Acceptance path:

1. STOP message is detected by channel adapter and worker.
2. Bot sends no further automated response.
3. Thread appears with opted-out status.
4. Opt-out row appears in Settings Opt-outs tab.
5. Admin can re-enable only through explicit re-consent confirmation.

## Open UX Implementation Decisions

| Decision | Recommendation |
|---|---|
| Channel connection form shape per provider | Use one shared sheet with provider-specific field schema |
| Inbox route model | Support both split-panel `/chatbot/inbox` and direct detail `/chatbot/inbox/$threadId` |
| Test Bot location | Keep as sheet from Knowledge Base for MVP |
| Opt-outs location | Add tab to existing Settings rather than duplicating under Chatbot Settings |
| Dead-letter operator UI | Add operator-only recovery mockup and story; keep it outside workspace admin navigation |

## Completion Checklist

- [ ] All route files exist and render inside existing SignalLoop layout.
- [ ] All screen components use shadcn/ui components and Lucide icons.
- [ ] Role guards match admin/agent access rules.
- [ ] Screens have loading, empty, success, and error states.
- [ ] Inbox has SSE and polling fallback.
- [ ] WhatsApp window and opt-out constraints are visible in the UI.
- [ ] Test Bot shows source citations and AI disclosure.
- [ ] Operator dead-letter view supports list, retry, and audit expectations.
- [ ] Screen tests cover role visibility, primary actions, and compliance states.
