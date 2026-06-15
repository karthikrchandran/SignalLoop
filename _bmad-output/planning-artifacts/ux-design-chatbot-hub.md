---
stepsCompleted: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]
inputDocuments:
  - _bmad-output/planning-artifacts/prd-chatbot-hub.md
  - _bmad-output/planning-artifacts/architecture-chatbot-hub.md
  - _bmad-output/planning-artifacts/validation-report-chatbot-hub.md
designSystem: shadcn/ui (New York style) + Tailwind CSS + Lucide Icons
platform: Web (desktop-primary, tablet-responsive)
integrationModel: Chatbot section added to existing SignalLoop sidebar — no new portal
status: complete
---

# UX Design Specification SignalLoop — ChatBot Hub

**Author:** K.Ramachandran
**Date:** 2026-05-13

---

## Executive Summary

### Project Vision

ChatBot Hub extends the existing SignalLoop workspace with a unified AI chatbot engine. It is not a new product — it is a new section inside the existing admin portal, sharing the same login, sidebar shell, design system, and role model. Admins configure channels and a knowledge base; agents monitor and reply to escalated conversations in the inbox; the bot handles routine visitor Q&A autonomously.

### Target Users

| User | Primary Goal | Daily Screen |
|---|---|---|
| Workspace Admin | Connect channels, build knowledge base, configure bot | Channels + Knowledge Base (setup phase); Analytics (steady state) |
| Agent | Respond to escalated conversations, close threads | Inbox |
| Visitor (end customer) | Chat on WhatsApp / Facebook / Telegram | Does not use admin UI |

### Key Design Challenges

1. **Inbox urgency with six thread states** — `bot-active`, `escalated`, `agent-active`, `resolved`, `out-of-hours`, `opted-out` — agents must triage at a glance without reading every row.
2. **Async KB pipeline visibility** — crawling 50 URLs is a background job that takes minutes; admins need clear progress signals without polling anxiety.
3. **WhatsApp 24-hour window enforcement** — the reply input must visibly block with a legal-compliant explanation; this is not optional UI.
4. **Bot Config density** — 10+ configurable settings that need sensible defaults and clear grouping to avoid overwhelming first-time admins.
5. **Test Bot confidence gate** — admins must feel confident before going live; the Test Bot panel is the primary trust-builder.

### Design Opportunities

1. **Channel status cards as onboarding dashboard** — clear health indicators reduce support escalation.
2. **Real-time inbox without page refresh** — SSE-powered updates create a "live" feel agents will prefer over competitors.
3. **Test Bot as the "aha moment"** — an instant Q&A response against the admin's own knowledge base is the moment they believe the product works.

---

## Core User Experience

### Defining Experience

> **"An admin pastes their website URL, waits two minutes, then asks the bot a question and gets a correct answer about their own business."**

This is the make-or-break moment. If this succeeds, everything else (channels, inbox, lead capture) feels like natural extensions. Every UX decision should protect and accelerate this flow.

### Platform Strategy

- **Primary platform:** Web, desktop-first (1280px+ viewport assumed for inbox and analytics)
- **Tablet responsive:** 768–1024px — sidebar collapses to icons, inbox and knowledge base remain usable
- **Mobile:** Not an admin use case; graceful degradation only (no mobile-optimised layout planned for MVP)
- **Device capabilities:** No camera/GPS/push notification dependencies; SSE for real-time updates
- **Offline:** Not required — all admin actions require live API connection

### Effortless Interactions

- **Channel connection** — OAuth flows open in the same tab; success/error is surfaced on the Channels page immediately. Admin never leaves the Channels page.
- **Knowledge base URL input** — single text area, comma- or newline-separated URLs, one "Index Now" button. No per-URL configuration at MVP.
- **Test Bot** — triggers as a slide-over sheet; no page navigation needed. Admin stays on Knowledge Base page.
- **Thread reply** — agent types in the reply box at the bottom of Thread Detail; no compose modal, no intermediate step.
- **Resolve thread** — single "Resolve" button in Thread Detail header; no confirmation dialog needed (reversible via re-open).

### Critical Success Moments

1. **First bot response in Test Bot panel** — within 5 seconds of pressing "Ask"
2. **First escalated thread appearing in Inbox** — real-time, no manual refresh
3. **First lead appearing in `/contacts`** after a captured conversation
4. **Channel connected** — status card turns green with "Connected · Active" label

### Experience Principles

1. **Status is always visible** — every async operation (indexing, channel health, thread state) exposes its current state without the user having to ask.
2. **Defaults are production-ready** — bot config default values (5s timeout, 90-day retention, 4000 token cap, "I'm an AI assistant." disclosure) are immediately safe to ship.
3. **Escalation must never be missed** — visual + in-app notification on every new escalation; badge count on Inbox nav item.
4. **Platform rules are enforced in UI, not just API** — WhatsApp window, opt-out status, and workspace isolation are surfaced visually before an error occurs.
5. **Extend, don't replace** — every ChatBot Hub screen uses the same layout shell, same component library, and same interaction patterns as existing SignalLoop screens.

---

## Desired Emotional Response

### Primary Emotional Goals

- **Admin (setup phase):** *Confident* — "I understand what this does and I trust it before I go live."
- **Agent (daily use):** *In control* — "I can see everything I need to act, and I won't miss an escalation."
- **Both, on first use:** *Impressed* — "This is smoother than I expected."

### Emotional Journey Mapping

| Moment | Desired feeling | Design mechanism |
|---|---|---|
| Landing on Channels page for first time | Orientated, not overwhelmed | Empty state card per channel with clear "Connect" CTA |
| Waiting for URL indexing to complete | Patient, not anxious | Progress indicator with estimated time; background dismissal |
| First Test Bot answer | Delighted, convinced | Fast response (<5s); confidence score badge; highlight which source chunk answered |
| New escalation arrives in Inbox | Alert but calm | Red badge on nav item; toast notification; thread row highlighted in amber |
| Agent WhatsApp window expires | Informed, not frustrated | Greyed reply box + yellow warning banner with clear explanation — not a hard error modal |
| Resolved thread | Accomplished | Thread moves to Resolved tab with a brief success micro-animation |

### Emotions to Avoid

- **Anxiety** from invisible async jobs (loading spinners with no ETA)
- **Frustration** from confusing thread state transitions
- **Alarm** from error modals for expected platform constraints (WhatsApp window, opt-out)
- **Distrust** from bot responses with no source attribution

### Design Implications

- Async jobs → `<Progress>` bar + estimated minutes remaining, dismissable
- Thread states → colour-coded left border (amber = escalated, blue = bot-active, green = resolved, grey = opted-out)
- WhatsApp expiry → inline warning, not toast, not modal
- Test Bot → show source chunk reference under each bot answer

---

## UX Pattern Analysis & Inspiration

### Reference Products

| Product | Pattern to adopt | Adaptation needed |
|---|---|---|
| **Intercom** | Split-panel inbox (thread list left, detail right) | Use existing SignalLoop layout constraints; no new shell |
| **Crisp** | Colour-coded status dots per conversation | Extend with left-border accent rather than dot-only |
| **Linear** | Keyboard-navigable lists with shortcut hints | Add `J/K` arrow nav on inbox thread list |
| **Notion** | Inline progress for background jobs | Surface as a dismissable banner below page header |
| **Slack** | Unread badge on navigation item | Existing SignalLoop sidebar `<Badge>` component already supports this |

### Anti-Patterns to Avoid

- **Intercom's modal-heavy config** — every setting should be inline-editable on the Bot Settings page, not a modal per field
- **Freshchat's multi-tab noise** — keep all ChatBot Hub surfaces under one sidebar group; no new top-level sections per channel
- **Tidio's separate "bot builder" app** — bot configuration stays inside the admin portal; no redirect to external tools

---

## Design System

### Foundation: shadcn/ui New York + Tailwind CSS

The design system is **already established** by the existing SignalLoop web app:

- **Component library:** shadcn/ui (New York style, `components.json` confirmed)
- **CSS framework:** Tailwind CSS with CSS variables (`--background`, `--foreground`, `--primary`, etc.)
- **Icon library:** Lucide React (imported already in `AppSidebar.tsx`)
- **Base colour:** Neutral (slate/zinc scale)
- **Dark mode:** Supported via `SidebarAppearance` toggle already in the sidebar footer

**No new design system choices are needed.** All ChatBot Hub screens use the same token set and component catalogue.

### Colour Semantics for ChatBot Hub

These map to existing Tailwind semantic classes:

| Purpose | Tailwind class | Usage |
|---|---|---|
| Escalated thread | `bg-amber-50 border-l-4 border-amber-500` | Inbox thread row |
| Bot-active thread | `border-l-4 border-blue-400` | Inbox thread row |
| Resolved thread | `border-l-4 border-green-400` | Inbox thread row |
| Opted-out / blocked | `border-l-4 border-slate-300 opacity-60` | Inbox thread row |
| Out-of-hours | `border-l-4 border-violet-400` | Inbox thread row |
| Connected channel | `text-green-600` dot + label | Channel card status |
| Error / disconnected | `text-red-500` dot + label | Channel card status |
| WhatsApp window warning | `bg-yellow-50 text-yellow-800 border border-yellow-200` | Reply area banner |

### New Icons Required (Lucide)

All available in Lucide React:

| Feature | Icon | Usage |
|---|---|---|
| ChatBot Hub nav group | `Bot` | Sidebar group header |
| Channels | `Plug` | Channels page + nav item |
| Knowledge Base | `BookOpen` | KB page + nav item |
| Inbox | `Inbox` | Inbox page + nav item |
| Thread / Message | `MessageSquare` | Thread list rows |
| Bot Analytics | `BarChart2` | Analytics page + nav item |
| Bot Settings | `SlidersHorizontal` | Settings page + nav item |
| Test Bot | `FlaskConical` | Test Bot trigger button |
| Escalated | `AlertCircle` | Thread status badge |
| Resolved | `CheckCircle2` | Thread status badge |
| Opted-out | `Ban` | Thread status badge |
| Source chunk | `FileSearch` | Test Bot answer citation |
| WhatsApp | `(custom SVG or `MessageCircle`)` | Channel card |
| Facebook | `(custom SVG or `Facebook`)` | Channel card |
| Telegram | `Send` | Channel card |

---

## Sidebar Navigation Extension

### Updated Sidebar Structure

The new "Chatbot" group is inserted **between Voice Agents and Contacts** — logically grouped with engagement channels, before the contact pool that receives leads.

```
Dashboard
Campaigns
Sequences
Voice Agents
──────────────── (new group)
Chatbot
  ├─ Channels
  ├─ Knowledge Base
  ├─ Inbox           [badge: unread escalations]
  ├─ Analytics
  └─ Settings
──────────────────
Contacts            ← leads from LC4 appear here
Analytics
Templates
Controls
Settings
Admin (superuser only)
```

### AppSidebar Implementation Notes

- Add a `SidebarGroup` with `SidebarGroupLabel` "Chatbot" wrapping 5 `SidebarMenuItem` entries
- Inbox item uses `<Badge variant="destructive">` on the right side showing count of open escalated threads; hidden when count = 0
- Group collapses to Bot icon in icon-mode (`collapsible="icon"`)
- Role gate: all 5 items visible to admin and agent roles; Settings item hidden for viewer role

---

## Visual Foundation

### Layout Shell

All 5 ChatBot Hub routes use the existing `_layout.tsx` shell unchanged:
- `<AppSidebar>` left
- `<SidebarInset>` right with sticky 64px header + scrollable main content area
- `max-w-7xl mx-auto` content container (matches all existing pages)

### Page Header Pattern

Every ChatBot Hub page follows the existing pattern from `campaigns.tsx` and `analytics.tsx`:

```
[Page Title]           [Primary Action Button]
[Page description — one line]
───────────────────────────────────────────────
[Page content]
```

### Card Grid vs. Full-Width

| Page | Layout |
|---|---|
| Channels | 3-column card grid (channel per card); collapses to 1-col on tablet |
| Knowledge Base | 2-column (source list left, stats/config right) + full-width Test Bot sheet |
| Inbox | 2-panel split: thread list (380px fixed) + thread detail (flex-1) |
| Analytics | 4-stat summary row + 2-column charts below |
| Bot Settings | Single-column form, grouped by section with `<Separator>` |

---

## Design Directions

### Direction: "Operational Admin" — Quiet Efficiency

The aesthetic continues SignalLoop's existing neutral tone:
- White/light grey surfaces (`bg-background`, `bg-card`)
- Slate text scale for hierarchy
- Accent colour (existing primary) used sparingly — only for primary CTAs and active nav state
- Status colours (amber, green, red, blue) carry meaning — not decoration
- No illustrations, no gradients, no hero imagery — this is an operator tool
- Compact information density — agents scan lists, not read prose

This matches the existing SignalLoop aesthetic and requires zero new design tokens.

---

## User Journey Flows

### Journey 1: Admin Connects a Channel

```
Channels page (empty state)
  └─ Click "Connect" on WhatsApp card
       └─ Slide-over sheet: "Connect WhatsApp Business"
            ├─ Enter Phone Number ID + Access Token + Webhook Verify Token
            ├─ "Save & Verify" → POST /api/v1/chatbot/channels
            │    ├─ SUCCESS → Sheet closes; card status: "Connected · Active" (green)
            │    └─ ERROR → Inline field error on failed credential; sheet stays open
            └─ Cancel → sheet closes, no change
```

**Key UX rules:**
- OAuth channels (Facebook): open Meta OAuth in same tab; redirect back to Channels page with `?connected=facebook` query param; success toast shown
- Never close the sheet on API error — show the error inline so admin can correct
- Channel card shows last webhook received timestamp once connected

---

### Journey 2: Admin Builds Knowledge Base

```
Knowledge Base page
  ├─ Tab: "Website URLs"
  │    └─ Textarea: paste URLs (one per line)
  │         └─ "Crawl & Index" button → POST /api/v1/chatbot/knowledge-base/index
  │              └─ Progress banner: "Indexing 12 pages… ~3 min remaining"
  │                   ├─ Completes → Banner: "Index updated · 247 chunks · 12 pages" (dismiss)
  │                   └─ Error → Banner: "3 pages failed to crawl" [View Details]
  │
  ├─ Tab: "Documents"
  │    └─ Drag-and-drop upload area (PDF, DOCX, TXT)
  │         └─ Upload + index → same progress banner pattern
  │
  ├─ Tab: "FAQ"
  │    └─ Q/A text pairs with "Add Entry" / delete row
  │         └─ Auto-indexed on save (no separate index step)
  │
  └─ "Test Bot" button (top-right) → opens <Sheet> slide-over
```

**Key UX rules:**
- Progress banner docks below page header; dismissable after completion
- All three source types are indexed into the same vector store — no source-type distinction in Test Bot answers
- "Re-index All" button available when index is stale (any source modified since last index)

---

### Journey 3: Admin Tests the Bot

```
Knowledge Base page → "Test Bot" button
  └─ Sheet slides in from right (480px wide, full height)
       ├─ Header: "Test Bot" [FlaskConical icon] [X close]
       ├─ Chat message area (scrollable, bot-only thread)
       ├─ Input box: "Ask your bot a question…" + Send button
       └─ Bot response:
            ├─ AI disclosure badge: "I'm an AI assistant."
            ├─ Response text
            └─ Source citation: "Based on: [chunk title / URL] · [similarity score]%"
```

**Key UX rules:**
- Test Bot always uses the current index (no "draft" vs "live" distinction at MVP)
- Confidence score shown only in Test Bot — not visible to end visitors
- Empty state: "Your knowledge base has no content yet. Add URLs, documents, or FAQ entries to get started."

---

### Journey 4: Agent Works the Inbox

```
Inbox page
  ├─ Left panel (380px): Thread List
  │    ├─ Filter bar: [All | Escalated | Bot-active | Resolved] [Channel dropdown] [Date range]
  │    ├─ Thread rows (sorted: escalated first, then by last activity)
  │    │    └─ Each row: [Channel icon] [Visitor name/handle] [Last message preview] [Time] [Status badge]
  │    │         └─ Colour accent: amber border = escalated; blue = bot-active; grey = resolved
  │    └─ Real-time update via SSE — new escalations insert at top with amber flash animation
  │
  └─ Right panel (flex-1): Thread Detail
       ├─ Header: [Visitor name] [Channel badge] [Status badge]  [Re-enable Bot] [Resolve ▾]
       ├─ Message history (scrollable)
       │    └─ Bubbles: bot (left, grey bg), visitor (left, white), agent (right, primary bg)
       ├─ WhatsApp 24h warning banner (conditional, yellow):
       │    "WhatsApp messaging window expired. Visitor must message first to reopen."
       └─ Reply box (disabled if opted-out or WhatsApp window expired):
            ├─ Textarea: "Reply as [Agent Name]…"
            └─ Send button → POST /api/v1/chatbot/conversations/{id}/messages
```

**Key UX rules:**
- Opted-out threads: reply box replaced with read-only notice "Visitor has opted out. Human agents may still reply manually if visitor re-initiates."
- "Resolve ▾" is a split-button: primary action = Resolve; dropdown includes "Re-open" and "Export Thread"
- Selecting a thread marks it as read (removes any unread indicator); badge count on nav item decrements
- No "assign to agent" at MVP — single workspace, all agents share the queue

---

### Journey 5: Admin Reviews Analytics

```
Analytics page (/chatbot/analytics)
  ├─ Date range picker (default: last 7 days)
  ├─ Summary row (4 stat cards):
  │    [Total Conversations] [Bot Containment Rate] [Leads Captured] [Escalations]
  │
  ├─ Chart row (2 columns):
  │    [Conversations over time — line chart] [Channel breakdown — bar chart]
  │
  └─ Table: Outcome breakdown
       Columns: Channel | Bot-resolved | Escalated | Lead-captured | Opted-out
```

**Key UX rules:**
- Scoped to current workspace only (enforced server-side; no UI toggle)
- "Refresh" button for manual update; auto-refresh badge shows "Updated X min ago"
- Export button (CSV) top-right — admin role only

---

### Journey 6: Admin Configures Bot Settings

```
Bot Settings page (/chatbot/settings)
  ├─ Section: AI & Disclosure
  │    ├─ AI Disclosure text [textarea, min 10 chars, non-empty enforced]
  │    └─ Token cap per session [number input, default: 4000]
  │
  ├─ Section: Lead Capture
  │    ├─ Enable lead capture [toggle]
  │    ├─ Min turns before trigger [number, default: 3]
  │    ├─ Intent keywords [tag input, comma-separated]
  │    └─ Privacy policy URL [URL input]
  │
  ├─ Section: Business Hours
  │    ├─ Enable out-of-hours mode [toggle]
  │    ├─ Timezone [select]
  │    ├─ Hours per day [time range pickers, Mon–Sun]
  │    └─ Out-of-hours message [textarea]
  │
  ├─ Section: Compliance
  │    ├─ Conversation retention (days) [number input, min: 30, default: 90]
  │    └─ Opt-out management [link → /settings tab]
  │
  └─ [Save Changes] button (sticky bottom bar on scroll)
```

**Key UX rules:**
- All sections use inline editing — no modal per field
- Unsaved changes: sticky bottom bar appears with "You have unsaved changes" + [Save] [Discard]
- Validation errors are inline per field; form does not submit until all errors cleared
- Opt-out management links to the existing `/settings` page (new "Opt-outs" tab) — not duplicated here

---

## Component Strategy

### Components from Existing shadcn/ui Catalogue (reuse as-is)

| Component | Used for |
|---|---|
| `<Card>` | Channel cards, stat cards, KB source entries |
| `<Sheet>` | Test Bot panel, channel connection form |
| `<Tabs>` | Knowledge Base source types; Inbox filter tabs |
| `<Badge>` | Thread status, channel status, nav unread count |
| `<Progress>` | KB indexing progress bar |
| `<Textarea>` | URL input, reply box, bot config text fields |
| `<Select>` | Channel filter, timezone picker |
| `<Input>` | Credential fields, FAQ Q&A |
| `<Button>` | All CTAs |
| `<Separator>` | Settings section dividers |
| `<Dialog>` | Bulk export confirmation only |
| `<Sonner>` (toast) | Channel connected success, escalation notification |
| `<SidebarGroup>` + `<SidebarGroupLabel>` | Chatbot nav group |

### Custom Components Required

#### 1. `<ChannelCard>`

**Purpose:** Display a single channel's connection status and actions.

**Anatomy:**
```
[Channel logo / icon]  [Channel name]        [Status pill]
[Last activity: "2 min ago"]
[Connect / Disconnect / Reconnect button]
```

**States:** `disconnected` (grey) | `connecting` (spinner) | `connected` (green) | `error` (red, shows error message) | `pending-approval` (amber, Meta verification pending)

**Variants:** Small (sidebar hint) / Full card (Channels page grid)

---

#### 2. `<ThreadRow>`

**Purpose:** Single row in the inbox thread list.

**Anatomy:**
```
[colour accent bar (4px left border)]
[Channel icon (16px)]  [Visitor name / handle]   [Time ago]
[Last message preview (truncated, 1 line)]        [Status badge]
```

**States:** unread (bold name) | read (normal weight) | selected (bg-accent) | hovered

**Status badges:** `escalated` (amber) | `bot-active` (blue) | `agent-active` (indigo) | `resolved` (green) | `out-of-hours` (violet) | `opted-out` (grey)

---

#### 3. `<MessageBubble>`

**Purpose:** Single message in Thread Detail history.

**Anatomy:**
```
[sender label: "Bot" / "Agent: K.R." / "Visitor"]
[message text bubble]
[timestamp]
[AI disclosure badge — bot messages only]
```

**Variants:** `bot` (left-aligned, slate bg) | `visitor` (left-aligned, white bg, border) | `agent` (right-aligned, primary bg, white text)

---

#### 4. `<KnowledgeSourceRow>`

**Purpose:** Single source entry in the Knowledge Base source list.

**Anatomy:**
```
[source type icon]  [URL / filename / "FAQ"]   [Chunks: 42]  [Status: Indexed ✓]
[Last indexed: 5 min ago]                                    [Delete]
```

**States:** `indexed` | `indexing` (spinner + progress %) | `error` (red icon + error tooltip) | `stale` (amber — source updated since last index)

---

#### 5. `<WhatsAppWindowBanner>`

**Purpose:** Legal-compliant warning when agent tries to reply after 24h window expiry.

**Anatomy (inline, inside Thread Detail reply area):**
```
[amber/yellow banner]
⚠️ WhatsApp 24-hour messaging window has expired.
The visitor must send a message first to reopen the conversation.
```

**Behaviour:** Renders instead of the reply textarea when `whatsapp_window_expired === true`. Not dismissable. Disappears automatically when a new inbound message arrives (SSE event).

---

## UX Consistency Patterns

### Button Hierarchy

| Action type | Variant | Example |
|---|---|---|
| Primary (one per page/section) | `variant="default"` | "Crawl & Index", "Save Changes", "Send" |
| Secondary / neutral | `variant="outline"` | "Test Bot", "Export", "Cancel" |
| Destructive | `variant="destructive"` | "Disconnect channel", "Delete source" |
| Ghost / quiet | `variant="ghost"` | Icon-only actions (delete row, copy) |

### Feedback Patterns

| Situation | Pattern |
|---|---|
| Background job started | Dismissable progress banner below page header |
| Background job complete | Banner updates to success state with dismiss button |
| Background job failed (partial) | Banner shows warning state with "View Details" link |
| Form field validation error | Inline red text below field; field border turns red |
| API success (instant) | Toast (Sonner, bottom-right, 4s auto-dismiss) |
| API error (instant) | Toast (destructive variant) + retry suggestion |
| Destructive action (disconnect channel) | Inline confirmation: button changes to "Are you sure? [Confirm] [Cancel]" — no modal |

### Empty States

Every list/table with potential empty state has a dedicated empty state:

| Page / list | Empty state |
|---|---|
| Channels page | Cards for each channel type with "Connect" CTA; not truly "empty" — always shows all 3 channel options |
| KB source list | "No sources yet. Add a website URL, upload a document, or create FAQ entries." |
| Inbox thread list | "No conversations yet. Conversations will appear here when your first channel is connected and receives a message." |
| Inbox — Resolved tab | "No resolved conversations in this date range." |
| Analytics | "Not enough data yet. Analytics update every 15 minutes once conversations begin." |

### Loading States

- **Page-level load:** Skeleton cards (matching the page's card/table structure) — not a full-page spinner
- **Thread Detail load:** Skeleton bubbles in message area
- **Inline button loading:** `<LoadingButton>` (already in the component library at `components/ui/loading-button.tsx`)

### Form Validation

- **Client-side:** Required fields, min length, URL format — validated on blur
- **Server-side:** Errors mapped to field level where possible; unattributable errors shown as page-level alert banner
- **Submit gate:** Primary submit button disabled while any field has an active error

---

## Responsive Design & Accessibility

### Breakpoints

| Breakpoint | Layout changes |
|---|---|
| `lg` (1024px+) | Full 2-panel Inbox; 3-column channel grid; full sidebar |
| `md` (768–1023px) | Sidebar collapses to icons; Inbox switches to single-panel (thread list → tap to open detail); 2-column channel grid |
| `sm` (<768px) | Not a target for MVP admin UI; graceful degradation only |

### Inbox Responsive Behaviour

On tablet (`md`), the Inbox uses a single-panel pattern:
- Thread list fills full width
- Tapping a thread navigates to a full-width Thread Detail view
- "← Back to Inbox" breadcrumb at top of Thread Detail
- No SSE thread-list-while-in-detail on tablet MVP (polling fallback acceptable)

### Accessibility Requirements

- **Keyboard navigation:** All interactive elements reachable via Tab; `J/K` shortcut in inbox thread list
- **ARIA labels:** `<ThreadRow>` includes `aria-label="Conversation with {visitor}, {status}, {time}"`;  `<ChannelCard>` includes `aria-label="{channel} channel, {status}"`
- **Focus management:** After sheet open (`<Sheet>`), focus moves to first interactive element; after sheet close, focus returns to trigger button
- **Colour:** Status colours never used as the sole differentiator — always accompanied by a label or icon (colour-blind safe)
- **Reduced motion:** `@media (prefers-reduced-motion)` — amber flash animation on new escalation is replaced with a static amber background
- **WCAG 2.1 AA:** Minimum contrast ratio 4.5:1 for body text; 3:1 for large text and UI elements

---

## Route Map

| Route | Component file | Role access |
|---|---|---|
| `/chatbot/channels` | `routes/_layout/chatbot/channels.tsx` | Admin |
| `/chatbot/knowledge-base` | `routes/_layout/chatbot/knowledge-base.tsx` | Admin |
| `/chatbot/inbox` | `routes/_layout/chatbot/inbox.tsx` | Admin + Agent |
| `/chatbot/inbox/$threadId` | `routes/_layout/chatbot/inbox.$threadId.tsx` | Admin + Agent |
| `/chatbot/analytics` | `routes/_layout/chatbot/analytics.tsx` | Admin + Agent (read) |
| `/chatbot/settings` | `routes/_layout/chatbot/settings.tsx` | Admin |

Settings Opt-out tab extension:
| `/settings` (existing) | New "Opt-outs" tab added to existing settings page | Admin |

---

## Integration with Existing Pages

| Existing page | Change |
|---|---|
| `/contacts` | Bot-captured leads appear automatically with `chatbot-lead` tag and `source: whatsapp/facebook/telegram`. No page changes needed — the Contact model is already workspace-scoped and tag-aware. |
| `/analytics` | Unchanged — covers campaigns/sequences/calls. `/chatbot/analytics` is the separate bot-specific dashboard. No cross-contamination of metrics. |
| `/settings` | New "Opt-outs" tab added listing opted-out visitors per channel, with manual re-enable action (OC4). Tab is admin-only. |
| `AppSidebar.tsx` | New `SidebarGroup` for Chatbot section added; Inbox item shows escalation badge count. |

---

_UX Design Specification complete — 2026-05-13_
_Ready for: Epic creation (`bmad-create-epics-and-stories`)_
