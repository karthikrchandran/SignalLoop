---
stepsCompleted: [1, 2, 3]
inputDocuments:
  - _bmad-output/planning-artifacts/prd-chatbot-hub.md
  - _bmad-output/planning-artifacts/architecture-chatbot-hub.md
  - _bmad-output/planning-artifacts/ux-design-chatbot-hub.md
  - _bmad-output/planning-artifacts/validation-report-chatbot-hub.md
project: SignalLoop — ChatBot Hub
date: "2026-05-13"
totalEpics: 9
totalStories: 30
---

# SignalLoop ChatBot Hub — Epic & Story Breakdown

## Overview

This document provides the complete epic and story breakdown for the **ChatBot Hub** extension of SignalLoop, decomposing all PRD functional requirements, architecture decisions, and UX design specifications into implementable, independently-deliverable stories.

**Coverage:** 63 FRs (CH1–9, KB1–12, BOT1–13, LC1–7, HH1–9, OC1–4, AN1–4, WS1–5) · 16 NFRs · 9 Architecture requirements · 6 UX Design requirements

---

## Requirements Inventory

### Functional Requirements

**Channel Management (CH1–CH9)**

- CH1: Support connecting and disconnecting Facebook Messenger, WhatsApp Business Cloud API, and Telegram Bot API
- CH2: Store channel credentials in existing encrypted ProviderCredential store, scoped to workspace
- CH3: Verify channel webhooks at connection time (Facebook hub.verify, WhatsApp/Meta signature, Telegram confirmation); reject failures
- CH4: Allow admins to toggle each channel active/inactive without deleting credentials
- CH5: Allow custom bot display name, greeting message, escalation message, and out-of-hours message per channel
- CH6: Display live/inactive/error status of each connected channel on the Channels page
- CH7: Allow admins to configure business hours (days, time range, timezone) per workspace; tag threads as out-of-hours when escalation occurs outside hours
- CH8: Handle channel provider API errors gracefully — retry up to 3 times; dead-letter failed outbound messages
- CH9: Allow admins to configure a bot persona description (up to 300 chars) injected into the LLM system prompt

**Knowledge Base Management (KB1–KB12)**

- KB1: Admin CRUD for knowledge sources via Knowledge Base management UI
- KB2: Website URL crawl source type — crawl depth 1–5 (default 2), up to 50 pages per source
- KB3: Document upload source type — PDF, DOCX, TXT up to 20 MB each
- KB4: Manual FAQ / free-form text source type
- KB5: Structured Q&A pair entry source type
- KB6: Chunk each source ~300–500 tokens with overlap; embed via configured model; store in workspace-scoped vector index
- KB7: Manual Re-index trigger — reprocess all active sources and rebuild workspace vector index
- KB8: Scheduled nightly re-index (default 02:00 workspace local time)
- KB9: Show indexing status (pending/indexing/ready/failed) and chunk count per source
- KB10: Scope all vector index reads/writes strictly to workspace — no cross-workspace leakage
- KB11: In-flight conversation sessions must continue using the previous index version until session ends
- KB12: Admin Test Bot panel — submit queries, receive RAG response + top retrieved chunks (text, source, similarity score)

**Bot Conversation Engine (BOT1–BOT13)**

- BOT1: Route every inbound message from any connected channel to the shared bot conversation engine
- BOT2: Greet first-time visitors with configured greeting message or default
- BOT3: For each message, perform semantic similarity search (top-k=5 default), retrieve chunks, construct prompt with context + history
- BOT4: Invoke configured LLM (default: Groq Llama 3.1 8B) with constructed prompt; return response via channel
- BOT5: System prompt grounding instructions — answer only from retrieved context; state inability when context insufficient; no hallucinations
- BOT6: Maintain conversation history per visitor per channel session (minimum 10 turns retained)
- BOT7: Detect escalation triggers: (a) explicit human request, (b) confidence below threshold (default 0.4 cosine), (c) 3+ consecutive low-confidence messages
- BOT8: On escalation trigger — send escalation message to visitor, mark thread escalated, surface in admin inbox
- BOT9: Support bot-off mode per channel — route all inbound directly to inbox without bot engagement
- BOT10: Deliver bot response to visitor channel within 5 seconds p95
- BOT11: Every bot message must include AI disclosure text (configurable wording, non-disableable)
- BOT12: Respond to non-text messages (image, voice, document, sticker, location) with graceful fallback message
- BOT13: When visitor is opted-out, do not send automated response; show thread in inbox with opted-out badge

**Lead Capture (LC1–LC7)**

- LC1: Initiate lead capture flow when visitor expresses purchase intent, requests demo, asks pricing, or exceeds minimum turn threshold (default 3)
- LC2: Collect minimum: visitor name and one contact channel (email or phone)
- LC3: Present privacy notice and obtain explicit consent before collecting PII (PDPA/GDPR/PDPC required)
- LC4: On successful capture with consent, create Contact record with channel source, tag chatbot-lead, and intent field
- LC5: No duplicate contacts — update last-seen and append intent tag if contact already exists
- LC6: Lead capture is optional; if visitor declines, conversation continues; do not re-prompt more than once per session
- LC7: Record consent event (accepted/declined) in audit log per Contact record

**Human Handoff & Admin Inbox (HH1–HH9)**

- HH1: Inbox displays all conversation threads across channels sorted by last activity (most recent first)
- HH2: Each thread shows: channel icon, visitor identifier, last message preview, last message time, status badge
- HH3: Opening an escalated thread shows full message history (bot + visitor turns)
- HH4: Agent can type and send a reply from inbox; delivered to visitor via originating channel within 3 seconds p95
- HH5: Agent reply changes thread status to agent-active; bot does not send automated responses until agent resolves or re-enables bot
- HH6: Agent can mark thread resolved; resolved threads move to Resolved tab
- HH7: Inbox filtering by channel, status, and date range
- HH8: In-app notification (and optional email) to agents on new escalation
- HH9: Export conversation threads (single or bulk by date range/channel) as CSV or JSON; admin role only

**Opt-Out & Compliance (OC1–OC4)**

- OC1: Immediately cease all bot responses when visitor sends opt-out keyword (STOP/Unsubscribe/Cancel/Quit); mark opted-out; record in audit log
- OC2: Opted-out thread remains visible in inbox with opted-out badge; human agents may still reply manually
- OC3: Re-initiating contact by opted-out visitor surfaces thread for human review; bot does not auto-engage; optional single re-opt-in invitation if admin-enabled
- OC4: Opt-out management view in admin settings — view all opted-out visitors per channel; manually re-enable only after admin confirms re-consent

**Analytics (AN1–AN4)**

- AN1: Per-workspace analytics dashboard: total conversations, messages, bot-handled rate, escalation count, leads captured, breakdown by channel — configurable date ranges
- AN2: Analytics data updated at least every 15 minutes
- AN3: Record per-conversation metadata: channel, start/end time, turn count, outcome, bot confidence scores per turn
- AN4: Analytics scoped strictly to workspace; no cross-workspace aggregation

**Webhook Security & Reliability (WS1–WS5)**

- WS1: All inbound webhook endpoints validate provider signature/token before processing; reject with HTTP 401 and log failures
- WS2: Webhook processing is asynchronous — acknowledge HTTP 200 within 5 seconds; process in background worker
- WS3: Failed message processing retried with exponential backoff (up to 3 attempts); dead-lettered after all retries exhausted
- WS4: Log all inbound webhook events (channel, visitor ID, message ID, timestamp, processing outcome) in audit log
- WS5: Deduplicate inbound messages by (channel, provider_message_id); do not send duplicate bot responses

---

### Non-Functional Requirements

- NFR-CB1: Bot response delivered to visitor within 5 seconds p95 (end-to-end: webhook receipt to channel delivery)
- NFR-CB2: KB re-indexing of 50 pages + 5 documents completes within 10 minutes p95
- NFR-CB3: Admin inbox initial thread list loads within 3 seconds p95
- NFR-CB4: Agent reply delivery to visitor completes within 3 seconds p95
- NFR-CB5: Bot webhook ingestion pipeline achieves 99.9% monthly availability
- NFR-CB6: No inbound messages silently dropped — every verified inbound message results in bot response, escalation, or dead-letter record
- NFR-CB7: After LLM provider recovery, queued message processing resumes within 5 minutes
- NFR-CB8: All channel API tokens, webhook secrets, and LLM API keys encrypted at rest via existing ProviderCredential encryption
- NFR-CB9: Vector index data and conversation history partitioned by workspace; no cross-workspace query permitted at any layer
- NFR-CB10: All inbound webhook requests verified via channel provider's official signature scheme before any payload content is processed
- NFR-CB11: Admin inbox access and KB management restricted to workspace admin or agent role
- NFR-CB12: Visitor chat data retained for configurable duration (default 90 days, minimum 30 days); purgeable on request
- NFR-CB13: Architecture supports 500 concurrent inbound conversations per workspace in Phase 2 without architectural changes
- NFR-CB14: KB pipeline supports up to 100,000 chunks per workspace vector index at MVP
- NFR-CB15: Record customer_last_message_at per WhatsApp conversation; gate agent outbound sends — disable reply input + show warning if >24 hours elapsed
- NFR-CB16: LLM token consumption per session capped at configurable limit (default 4,000 tokens); graceful fallback message when limit hit

---

### Additional Requirements (Architecture)

- ARCH1: Change compose.yml db service image from postgres:17 to pgvector/pgvector:pg17 — required before any KB functionality
- ARCH2: First Alembic migration must include CREATE EXTENSION IF NOT EXISTS vector;
- ARCH3: Implement ChatChannelAdapter ABC at apps/api/app/infrastructure/providers/chat/base.py with channel registry pattern; new adapters register without modifying existing workers
- ARCH4: New chat_worker.py at apps/workers/chat_worker.py sibling to call_worker.py — BRPOP from chatbot:inbound:{workspace_id}, runs RAG + LLM pipeline, dispatches channel sends
- ARCH5: New knowledge_indexing_worker.py at apps/workers/knowledge_indexing_worker.py — processes KB source ingestion jobs asynchronously
- ARCH6: Index versioning — each re-index run generates a new index_version UUID; existing sessions pin their version; new sessions use current version; old chunks soft-deleted after no active sessions reference them
- ARCH7: Dead-letter queue chatbot:deadletter:{workspace_id} with 7-day TTL; operator visibility via /api/v1/chatbot/dead-letters endpoint
- ARCH8: Workspace isolation enforced by passing workspace_id as first argument to all repository functions; service layer always passes workspace_id from authenticated JWT; integration tests include cross-workspace isolation test per resource type
- ARCH9: Analytics snapshot job — pre-aggregated analytics_snapshots table; job runs every 15 minutes via scheduler

---

### UX Design Requirements

- UX-DR1: Add "Chatbot" SidebarGroup to AppSidebar.tsx with 5 sub-items (Channels, Knowledge Base, Inbox, Analytics, Settings); Inbox item shows Badge variant="destructive" count of open escalated threads; hidden when count = 0
- UX-DR2: Implement 5 custom React components: ChannelCard (connection status + actions), ThreadRow (colour-accent by status), MessageBubble (bot/agent/visitor variants), KnowledgeSourceRow (source status + chunk count), WhatsAppWindowBanner (24h window enforcement, non-dismissable)
- UX-DR3: Test Bot panel implemented as Sheet slide-over on Knowledge Base page; shows response + source citation (chunk text + similarity score) per answer; stays on KB page (no navigation)
- UX-DR4: Real-time inbox thread list updates via SSE on /api/v1/chatbot/inbox/events; new escalations insert at top with amber flash animation; WhatsAppWindowBanner renders instead of reply textarea when window expired
- UX-DR5: Knowledge Base indexing progress shown as dismissable progress banner below page header (not a full-page spinner); all 3 source tabs (URLs, Documents, FAQ) share same progress banner pattern
- UX-DR6: Add "Opt-outs" tab to existing /settings page for opt-out management (OC4); admin only; no duplicate settings page

---

### FR Coverage Map

| FR | Epic | Primary Story |
|---|---|---|
| WS2, KB10, NFR-CB8, NFR-CB9, ARCH1–5, ARCH8, UX-DR1 | Epic 1 | Stories 1.1–1.3 |
| CH1–CH6, CH8, WS1, WS3–WS5, BOT9, BOT12, BOT13, NFR-CB5, NFR-CB6, NFR-CB10 | Epic 2 | Stories 2.1–2.4 |
| KB1–KB12, NFR-CB2, NFR-CB14, ARCH5–6, UX-DR3, UX-DR5 | Epic 3 | Stories 3.1–3.5 |
| BOT1–BOT8, BOT10–BOT11, NFR-CB1, NFR-CB7, NFR-CB16, ARCH4 | Epic 4 | Stories 4.1–4.4 |
| LC1–LC7 | Epic 5 | Stories 5.1–5.2 |
| HH1–HH9, NFR-CB3, NFR-CB4, UX-DR4 | Epic 6 | Stories 6.1–6.4 |
| OC1–OC4, UX-DR6 | Epic 7 | Stories 7.1–7.2 |
| AN1–AN4, NFR-CB11, ARCH9 | Epic 8 | Stories 8.1–8.2 |
| CH5, CH7, CH9, BOT11 (config UI), NFR-CB12, NFR-CB15, NFR-CB16 (settings UI) | Epic 9 | Stories 9.1–9.2 |

---

## Epic List

### Epic 1: ChatBot Hub Foundation — Infrastructure, Schema & Navigation Shell
Establish all technical prerequisites: pgvector image swap, database migrations for all 9 ChatBot Hub tables, the ChatChannelAdapter ABC with channel registry, and the Chatbot navigation section in the sidebar. Every subsequent epic depends on this foundation being complete.
**FRs covered:** WS2, KB10, NFR-CB8, NFR-CB9, ARCH1–5, ARCH8, UX-DR1

### Epic 2: Channel Management & Webhook Ingestion
Admins can connect, configure, and manage Facebook Messenger, WhatsApp Business, and Telegram channels. The system verifies webhook credentials, reliably ingests inbound messages into the worker queue with deduplication, handles provider errors with retry/dead-letter, and displays channel status on the Channels page.
**FRs covered:** CH1–CH6, CH8, WS1, WS3–WS5, BOT9, BOT12, BOT13, NFR-CB5, NFR-CB6, NFR-CB10

### Epic 3: Knowledge Base Management
Admins can build the bot's knowledge base from website URLs, uploaded documents, and FAQ/Q&A text. The system crawls, parses, chunks, embeds, and indexes all sources into a workspace-scoped pgvector index with status visibility and a manual/scheduled re-index trigger. Admins can test the bot against the current index via the Test Bot panel.
**FRs covered:** KB1–KB12, NFR-CB2, NFR-CB14, ARCH5–6, UX-DR3, UX-DR5

### Epic 4: Bot Conversation Engine & AI Responses
The chat worker processes inbound messages end-to-end: RAG retrieval, prompt construction with grounding rules, LLM generation, AI disclosure, conversation history, escalation detection, token cap enforcement, and non-text fallback. Every inbound message from a connected channel produces either a grounded bot response or an escalation.
**FRs covered:** BOT1–BOT8, BOT10–BOT11, NFR-CB1, NFR-CB7, NFR-CB16, ARCH4

### Epic 5: Lead Capture & Contact Integration
The bot detects visitor intent, presents a privacy-compliant consent notice, collects contact details (name + email/phone), deduplicates against existing contacts, and creates a Contact record in the SignalLoop contact pool with the chatbot-lead tag and intent field. All consent events are logged.
**FRs covered:** LC1–LC7

### Epic 6: Admin Inbox & Human Handoff
Agents can view all conversation threads across channels in real time, open escalations to see full message history, reply as a human agent, resolve threads, filter the queue, receive in-app escalation notifications, and export conversation data.
**FRs covered:** HH1–HH9, NFR-CB3, NFR-CB4, UX-DR4

### Epic 7: Opt-Out & Compliance Controls
The system immediately enforces opt-out keywords on all channels, maintains an audit log of all opt-out events and re-engagement requests, prevents the bot from re-engaging opted-out visitors, and provides admins with an Opt-outs tab in the existing Settings page for opt-out management.
**FRs covered:** OC1–OC4, UX-DR6

### Epic 8: Analytics Dashboard
Admins can view a per-workspace analytics dashboard showing conversation volumes, bot containment rate, escalation counts, and leads captured — broken down by channel and configurable date range. Snapshot data is pre-aggregated every 15 minutes.
**FRs covered:** AN1–AN4, NFR-CB11, ARCH9

### Epic 9: Bot Configuration & Settings UI
Admins can configure the bot persona, business hours, AI disclosure text, token cap, conversation retention, privacy policy URL, and lead capture settings from a dedicated Bot Settings page. All configuration is inline-editable with a sticky unsaved-changes save bar.
**FRs covered:** CH5, CH7, CH9, BOT11 (disclosure config UI), NFR-CB12, NFR-CB15, NFR-CB16 (settings UI)

---

## Epic 1: ChatBot Hub Foundation — Infrastructure, Schema & Navigation Shell

**Goal:** Establish all technical prerequisites for ChatBot Hub: pgvector database image, all database migrations, the ChatChannelAdapter interface and registry, and the Chatbot sidebar navigation group. Every subsequent epic builds on this foundation.

---

### Story 1.1: Enable pgvector and Create All ChatBot Hub Database Migrations

As a developer,
I want the PostgreSQL database upgraded to pgvector and all ChatBot Hub tables created via Alembic migrations,
So that all subsequent epics have the data layer they need from day one.

**Acceptance Criteria:**

**Given** the compose.yml currently uses postgres:17 as the db service image
**When** the developer applies the compose change
**Then** the db service uses pgvector/pgvector:pg17 image and starts successfully with all existing data intact

**Given** the pgvector extension is not yet enabled
**When** the first ChatBot Hub Alembic migration runs
**Then** CREATE EXTENSION IF NOT EXISTS vector; executes successfully and vector extension is confirmed active

**Given** the migrations run against a fresh database
**When** all ChatBot Hub migrations complete
**Then** the following tables exist with correct columns, constraints, and indexes:
- channel_configs (UNIQUE on workspace_id + channel)
- workspace_bot_config (UNIQUE on workspace_id)
- knowledge_sources (with idx_knowledge_sources_workspace index)
- knowledge_chunks (with HNSW index using vector_cosine_ops, m=16, ef_construction=64; and idx_knowledge_chunks_workspace_version index)
- chat_conversations (with status, last_activity, workspace indexes)
- chat_messages (with conversation + dedup unique indexes)
- opt_out_registry (UNIQUE on workspace_id + channel + visitor_id)
- analytics_snapshots (UNIQUE on workspace_id + channel + snapshot_date)

**Given** any ChatBot Hub table is queried with a specific workspace_id
**When** the query executes
**Then** only rows belonging to that workspace_id are returned (enforced by application-layer WHERE clauses validated in migration tests)

**Given** the migrations run in a CI environment
**When** alembic upgrade head is executed
**Then** exit code is 0 and alembic current shows the latest ChatBot Hub revision

---

### Story 1.2: Implement ChatChannelAdapter ABC and Channel Registry

As a developer,
I want a ChatChannelAdapter abstract base class and a channel registry,
So that all channel adapters (Facebook, WhatsApp, Telegram) share a common interface and can be registered without modifying existing worker or router code.

**Acceptance Criteria:**

**Given** the abstract base class is defined at apps/api/app/infrastructure/providers/chat/base.py
**When** a developer inspects it
**Then** it defines these abstract methods: verify_webhook(request) -> bool, parse_inbound_event(payload) -> InboundMessage | None, send_message(conversation_id, text) -> DeliveryReceipt, normalize_visitor_id(raw_id) -> str, is_opt_out_message(text) -> bool, is_non_text_message(payload) -> bool

**Given** the InboundMessage dataclass is defined
**When** an adapter calls parse_inbound_event()
**Then** the returned InboundMessage has fields: workspace_id (UUID), channel (ChannelType), provider_message_id (str), visitor_id (str), text (str | None), is_non_text (bool), received_at (datetime), raw_payload (dict)

**Given** the channel registry at apps/api/app/infrastructure/providers/chat/registry.py
**When** a channel type string ("facebook", "whatsapp", "telegram") is passed to get_adapter(channel_type)
**Then** the corresponding adapter class is returned

**Given** a new channel adapter is added to registry.py
**When** the application starts
**Then** the new adapter is available to all workers and routers without any code changes to those files

**Given** any concrete adapter class
**When** it is instantiated and its interface methods are called
**Then** it raises NotImplementedError if not fully implemented — verified by unit tests for each abstract method

---

### Story 1.3: Add Chatbot Navigation Section to Sidebar

As a workspace admin or agent,
I want a "Chatbot" section in the application sidebar with navigation links to all ChatBot Hub pages,
So that I can access channel management, knowledge base, inbox, analytics, and settings from any page.

**Acceptance Criteria:**

**Given** a user is logged in as a workspace admin
**When** they view the application sidebar
**Then** a "Chatbot" group label appears containing 5 sub-items: Channels (/chatbot/channels), Knowledge Base (/chatbot/knowledge-base), Inbox (/chatbot/inbox), Analytics (/chatbot/analytics), Settings (/chatbot/settings)

**Given** there are 3 open escalated threads
**When** the user views the sidebar
**Then** the Inbox nav item shows a red Badge variant="destructive" with "3"; when all escalations are resolved, the badge is hidden

**Given** a user is logged in as agent role (not admin)
**When** they view the sidebar
**Then** the Channels, Knowledge Base, and Settings items are hidden; only Inbox and Analytics are visible

**Given** a user navigates to any /chatbot/* route
**When** the route renders
**Then** it uses the existing _layout.tsx shell (AppSidebar + SidebarInset) unchanged; the Chatbot nav item is in active/highlighted state; no new layout shell is created

**Given** the 5 placeholder route files do not yet exist
**When** the nav items are clicked
**Then** each route renders a minimal placeholder page (heading + "Coming soon") without 404 errors — placeholder files are created as part of this story

---

## Epic 2: Channel Management & Webhook Ingestion

**Goal:** Admins can connect, configure, and manage Facebook Messenger, WhatsApp Business, and Telegram channels. The system verifies webhook credentials, reliably ingests inbound messages into the processing queue with deduplication, handles provider errors with retry/dead-letter, and displays channel status in a clean Channels page UI.

---

### Story 2.1: Channel Config API — CRUD, Toggle, and Credential Storage

As a workspace admin,
I want to create, update, and toggle my channel configurations via the API,
So that I can manage my channel connections programmatically and all credentials are securely stored.

**Acceptance Criteria:**

**Given** an authenticated admin makes POST /api/v1/chatbot/channels with valid channel type, credentials, and config
**When** the request is processed
**Then** a new channel_configs row is created scoped to the admin's workspace_id; the credential is stored in the existing provider_credentials table using the existing encryption mechanism; HTTP 201 returned with the created channel config (credentials masked)

**Given** an authenticated admin makes PATCH /api/v1/chatbot/channels/{channel_id}/toggle with { "is_active": false }
**When** the request is processed
**Then** channel_configs.is_active is set to false; credentials are retained; the channel stops accepting inbound messages; HTTP 200 returned

**Given** an authenticated admin makes DELETE /api/v1/chatbot/channels/{channel_id}
**When** processed
**Then** the channel config and its associated credential are deleted; HTTP 204 returned

**Given** a request is made with a workspace_id that does not own the channel_id
**When** processed
**Then** HTTP 403 returned; no data modified (workspace isolation enforced)

**Given** GET /api/v1/chatbot/channels is called
**When** the response is returned
**Then** all channels for the requesting workspace are listed with status, bot name, and last webhook received timestamp; channel tokens and secrets are never included in the response body

**Given** an agent role (not admin) calls any channel management endpoint
**When** processed
**Then** HTTP 403 returned

---

### Story 2.2: Facebook Messenger Webhook Adapter

As the system,
I want a Facebook Messenger webhook adapter that handles hub.verify challenges and processes inbound message events,
So that inbound Facebook messages are reliably ingested and queued for the chat worker.

**Acceptance Criteria:**

**Given** Facebook sends GET /webhooks/facebook/{workspace_id} with a hub.verify challenge
**When** the handler processes it
**Then** returns hub.challenge as plain text with HTTP 200 if hub.verify_token matches workspace's stored verify token; HTTP 403 if it does not match

**Given** Facebook sends POST /webhooks/facebook/{workspace_id} with a valid X-Hub-Signature-256 header
**When** the handler validates the HMAC-SHA256 signature against the stored app secret
**Then** on valid: HTTP 200 returned immediately; message pushed to chatbot:inbound:{workspace_id} Redis queue
**And** on invalid: HTTP 401 returned; event logged; payload not processed (WS1)

**Given** a Facebook message event is received
**When** FacebookMessengerAdapter.parse_inbound_event() processes it
**Then** returns InboundMessage with normalized visitor_id (page-scoped PSID); text extracted; is_non_text=True for attachments/stickers/location

**Given** a message with the same provider_message_id arrives twice within 24 hours
**When** the second event is processed
**Then** the Redis dedup key chatbot:dedup:{workspace_id}:facebook:{message_id} already exists; message discarded; HTTP 200 returned without re-queuing (WS5)

**Given** the channel has is_active = false
**When** an inbound webhook event arrives
**Then** the event is acknowledged (HTTP 200) but not queued for bot processing

---

### Story 2.3: WhatsApp Business Cloud API Adapter (with 24-Hour Window Tracking)

As the system,
I want a WhatsApp Business Cloud API webhook adapter that handles Meta verify challenges, processes inbound messages, and tracks the 24-hour customer messaging window,
So that WhatsApp messages are reliably ingested and the WhatsApp platform constraint is enforced.

**Acceptance Criteria:**

**Given** Meta sends GET /webhooks/whatsapp/{workspace_id} verification challenge
**When** processed
**Then** hub.challenge returned with HTTP 200 if hub.verify_token matches; HTTP 403 otherwise

**Given** Meta sends POST /webhooks/whatsapp/{workspace_id} with valid X-Hub-Signature-256
**When** validated
**Then** on valid: HTTP 200 immediately returned; message pushed to Redis queue; chat_conversations.customer_last_message_at updated to now
**And** on invalid: HTTP 401 returned; event logged; payload not processed (WS1)

**Given** a WhatsApp message event is received
**When** WhatsAppCloudAdapter.parse_inbound_event() processes it
**Then** returns InboundMessage with normalized visitor_id (WhatsApp phone number); text extracted; is_non_text=True for image/audio/document/sticker/reaction

**Given** an agent attempts POST /api/v1/chatbot/inbox/threads/{thread_id}/reply
**When** API checks customer_last_message_at
**Then** if >24 hours elapsed: HTTP 422 returned with error code whatsapp_window_expired; reply is not sent (NFR-CB15)

**Given** an opt-out keyword "STOP" is received
**When** WhatsAppCloudAdapter.is_opt_out_message() is called
**Then** returns True; opt-out flow is triggered (OC1)

---

### Story 2.4: Telegram Bot Adapter and Channels Page UI

As a workspace admin,
I want to connect a Telegram Bot channel and see the live status of all connected channels on the Channels page,
So that I have a third channel option and a clear operational overview of all channel connections.

**Acceptance Criteria:**

**Given** Telegram sends POST /webhooks/telegram/{workspace_id} with X-Telegram-Bot-Api-Secret-Token header
**When** the handler validates the secret token
**Then** on valid: HTTP 200 returned; message pushed to Redis queue
**And** on invalid: HTTP 401 returned; event logged (WS1)

**Given** a Telegram update event is received
**When** TelegramBotAdapter.parse_inbound_event() processes it
**Then** returns InboundMessage with normalized visitor_id (Telegram chat_id as string); text extracted; is_non_text=True for photo/audio/document/sticker/location

**Given** an admin navigates to /chatbot/channels
**When** the page renders
**Then** a ChannelCard is shown for each of 3 channel types (Facebook, WhatsApp, Telegram) in a 3-column card grid; each card shows: channel icon, channel name, connection status pill, and Connect/Disconnect/Reconnect button

**Given** a channel has an active connection
**When** the admin views the Channels page
**Then** the ChannelCard shows "Connected · Active" (green), last webhook received timestamp, and a "Disconnect" button

**Given** the admin clicks "Connect" on an unconnected channel card
**When** the connect sheet opens
**Then** a Sheet slide-over appears with required credential fields for that channel; submitting calls POST /api/v1/chatbot/channels; on success, sheet closes and card updates to Connected state; on error, sheet stays open with inline field errors

**Given** a channel delivery fails (provider API 5xx)
**When** the chat worker sends a message and it fails
**Then** it retries up to 3 times with exponential backoff; after 3 failures the message is dead-lettered to chatbot:deadletter:{workspace_id} (CH8, WS3)

---

## Epic 3: Knowledge Base Management

**Goal:** Admins can build and maintain the bot's knowledge base from website URLs, uploaded documents, and FAQ/Q&A entries. The system ingests, chunks, embeds, and indexes all sources into a workspace-scoped pgvector index with visible status and a re-index pipeline. Admins can test the bot against the current index via the Test Bot panel.

---

### Story 3.1: Knowledge Source CRUD API

As a workspace admin,
I want to add, edit, and delete knowledge sources via the API,
So that I can manage what content the bot uses to answer visitor questions.

**Acceptance Criteria:**

**Given** an admin makes POST /api/v1/chatbot/knowledge-sources with source_type "url" and a valid URL
**When** processed
**Then** a knowledge_sources row is created with status=pending; an indexing job is enqueued to knowledge_indexing_worker.py; HTTP 201 returned

**Given** an admin makes POST /api/v1/chatbot/knowledge-sources with source_type "document" and file upload (PDF/DOCX/TXT <= 20 MB)
**When** processed
**Then** file is stored to configured storage path; knowledge_sources row created; indexing job enqueued; HTTP 201 returned

**Given** an admin makes POST with source_type "faq" and text content, or "qa_pair" with question + answer
**When** processed
**Then** knowledge_sources row created with appropriate config JSONB; indexing job enqueued; HTTP 201 returned

**Given** GET /api/v1/chatbot/knowledge-sources is called
**When** the response is returned
**Then** all knowledge sources for the workspace are listed with: id, name, source_type, status, chunk_count, last_indexed_at, error_message; ordered by created_at DESC

**Given** DELETE /api/v1/chatbot/knowledge-sources/{source_id} is called
**When** processed
**Then** the source record and all associated knowledge_chunks (all index versions) are marked deleted; HTTP 204 returned; a re-index is triggered to rebuild the vector index without the deleted source

---

### Story 3.2: Web Crawler and Document Parser (Indexing Worker — Ingestion)

As the system,
I want an async knowledge indexing worker that can crawl website URLs and parse uploaded documents,
So that text content from all source types is reliably extracted for chunking and embedding.

**Acceptance Criteria:**

**Given** a URL source job is dequeued by knowledge_indexing_worker.py
**When** the worker processes it
**Then** it uses httpx + BeautifulSoup4 to fetch and extract visible text from the starting URL and discovered linked pages up to configured crawl depth (max 5); crawl capped at 50 pages per source; robots.txt respected; source status updated to indexing while processing

**Given** a URL returns HTTP 4xx or 5xx
**When** the crawler fetches it
**Then** the page is skipped; error noted in source error_message; crawling continues for other pages; source status becomes ready if at least one page succeeded, failed if zero pages succeeded

**Given** a PDF document source job is dequeued
**When** processed
**Then** pypdf2 extracts text from all pages; extracted text passed to chunker

**Given** a DOCX document source job is dequeued
**When** processed
**Then** python-docx extracts paragraph text; passed to chunker

**Given** a FAQ or Q&A pair source job is dequeued
**When** processed
**Then** content passed directly to chunker without any fetch or parse step

**Given** an indexing job is running
**When** GET /api/v1/chatbot/knowledge-sources/{source_id}/status is polled
**Then** response includes: status, chunk_count (when ready), last_indexed_at (when ready), error_message (when failed)

---

### Story 3.3: Chunking, Embedding, and Vector Store (Indexing Worker — Vectorization)

As the system,
I want the indexing worker to chunk extracted text, generate embeddings via Ollama, and store them in pgvector scoped to the workspace,
So that the RAG pipeline can retrieve relevant content at query time.

**Acceptance Criteria:**

**Given** extracted text is passed to the chunker
**When** the chunking step runs
**Then** RecursiveCharacterTextSplitter is used with chunk_size=400 tokens, chunk_overlap=50 tokens; each chunk is associated with source_id, workspace_id, and current index_version UUID

**Given** a chunk is ready for embedding
**When** the embedder calls Ollama
**Then** POST http://ollama:11434/api/embeddings is called with model=nomic-embed-text and chunk text; a 768-dimensional float vector is returned

**Given** embeddings are generated
**When** written to the vector store
**Then** each knowledge_chunks row includes: workspace_id, source_id, index_version, chunk_text, embedding (vector(768)), chunk_index; all chunks for the same re-index run share the same index_version UUID

**Given** a workspace has active index version A and a re-index is triggered (version B)
**When** version B indexing completes
**Then** workspace_bot_config.current_index_version is updated to B; chunks from A are NOT deleted immediately; they remain until no active sessions reference version A (KB11, ARCH6)

**Given** a cross-workspace isolation test queries knowledge_chunks for workspace B using workspace A's workspace_id
**When** the query executes
**Then** zero rows from workspace B are returned (NFR-CB9, ARCH8)

---

### Story 3.4: Re-Index Pipeline — Manual Trigger and Nightly Schedule

As a workspace admin,
I want to manually trigger a full re-index of all knowledge sources and have the system run a nightly automatic re-index,
So that the bot's knowledge base stays current as content changes.

**Acceptance Criteria:**

**Given** an admin calls POST /api/v1/chatbot/knowledge-sources/reindex
**When** processed
**Then** if chatbot:reindex:lock:{workspace_id} does not exist: a new index_version UUID is generated; all active sources are re-enqueued; lock set with 15-minute TTL; HTTP 202 Accepted returned with the new index_version

**Given** a re-index is already in progress (lock key exists)
**When** a second POST /api/v1/chatbot/knowledge-sources/reindex is called
**Then** HTTP 409 Conflict returned with message "Re-index already in progress"

**Given** the nightly scheduler is configured with reindex_schedule_time = '02:00'
**When** the scheduler fires at 02:00 workspace local time
**Then** it calls the same re-index logic as the manual trigger; the re-index lock prevents concurrent runs (KB8)

**Given** a re-index completes successfully
**When** the last source finishes indexing
**Then** workspace_bot_config.current_index_version is updated; all new sessions use the new version; existing sessions continue with their pinned version (KB11)

**Given** a re-index job runs for a source that fails on all pages
**When** the job completes
**Then** that source status is set to failed with error_message; the re-index lock is released; other successfully indexed sources are available in the new index

---

### Story 3.5: Knowledge Base Management UI and Test Bot Panel

As a workspace admin,
I want a Knowledge Base page where I can manage all my knowledge sources and test the bot's responses before going live,
So that I can confidently build and validate my bot's knowledge base without writing code.

**Acceptance Criteria:**

**Given** an admin navigates to /chatbot/knowledge-base
**When** the page renders
**Then** it shows 3 tabs: "Website URLs", "Documents", "FAQ / Q&A"; a list of KnowledgeSourceRow components; and a "Test Bot" button (Lucide FlaskConical) in the top-right header area

**Given** the admin is on the "Website URLs" tab and types one or more URLs then clicks "Crawl & Index"
**When** submitted
**Then** POST /api/v1/chatbot/knowledge-sources is called; a dismissable progress banner appears below the page header showing "Indexing N pages... ~X min remaining"; the banner updates to success when complete; errors surface as a warning banner (UX-DR5)

**Given** the admin drags a PDF, DOCX, or TXT file onto the "Documents" tab upload area
**When** the file is accepted
**Then** files over 20 MB are rejected with inline error; accepted files trigger POST /api/v1/chatbot/knowledge-sources with the file; same progress banner pattern used (KB3, UX-DR5)

**Given** the admin clicks "Add Entry" on the "FAQ / Q&A" tab
**When** they fill in a question and answer and save
**Then** the entry is saved and auto-indexed without a separate "Index" step; the KnowledgeSourceRow shows status "Indexed" (KB4, KB5)

**Given** the admin clicks "Test Bot"
**When** the Sheet slide-over opens
**Then** it shows a chat-like interface with scrollable message area, input box, and Send button; closing the sheet returns focus to the "Test Bot" button (accessibility) (UX-DR3)

**Given** the admin types a question in the Test Bot sheet and presses Send
**When** POST /api/v1/chatbot/test responds
**Then** the bot response is shown with: AI disclosure badge, response text, and "Based on: [source name] [similarity score]%" citation per response; if KB is empty an empty state message is shown (KB12)

---

## Epic 4: Bot Conversation Engine & AI Responses

**Goal:** The chat worker processes every inbound queued message end-to-end: RAG retrieval, prompt construction with persona + grounding rules + AI disclosure, LLM generation via Groq, conversation history maintenance, escalation detection, token cap enforcement, and non-text fallback. Every inbound message produces either a grounded bot response, an escalation, or a dead-letter record.

---

### Story 4.1: Chat Worker Skeleton — Message Routing and Session Management

As the system,
I want a chat worker that reads from the inbound Redis queue, loads conversation sessions, checks opt-out and bot-off state, and manages session storage,
So that the bot processing pipeline has a reliable, ordered foundation for all message handling.

**Acceptance Criteria:**

**Given** a message is pushed to chatbot:inbound:{workspace_id} by a webhook handler
**When** chat_worker.py runs BRPOP
**Then** the message is dequeued; the worker loads the conversation session from chat:session:{workspace_id}:{channel}:{visitor_id} in Redis (TTL 24h; creates new session if key does not exist)

**Given** a message arrives for an opted-out visitor
**When** the worker processes the message
**Then** no bot response is sent; conversation created/updated in chat_conversations with status=opted_out; message logged in chat_messages with sender_role=visitor; processing stops (BOT13)

**Given** a channel has bot_off_mode = true
**When** the worker processes a message from that channel
**Then** no bot response sent; message saved; thread status set to escalated for human pickup (BOT9)

**Given** the message is_non_text = true
**When** the worker detects this
**Then** graceful fallback message sent via channel adapter ("I can only handle text messages for now. How can I help you in text?"); no RAG pipeline run (BOT12)

**Given** all processing for a message completes successfully
**When** the session is updated
**Then** the Redis session JSON array is updated with new visitor + bot message turns; retains at most the last 10 turns (configurable); TTL reset to 24 hours; chat_conversations.last_activity_at and turn_count updated (BOT6)

---

### Story 4.2: RAG Pipeline Integration and LLM Response Generation

As the system,
I want the chat worker to retrieve relevant knowledge chunks from pgvector and generate grounded responses via the Groq LLM with the configured bot persona and AI disclosure,
So that every text message receives an accurate, context-grounded bot response within 5 seconds p95.

**Acceptance Criteria:**

**Given** a text message is ready for bot processing
**When** the RAG retrieval step runs
**Then** the visitor's message is embedded using nomic-embed-text via Ollama; top-5 chunks retrieved with SELECT ... ORDER BY embedding <=> query_embedding LIMIT 5 WHERE workspace_id = :wid AND index_version = :pinned_version (BOT3, KB10, KB11)

**Given** top-k chunks and conversation history are available
**When** the prompt is constructed
**Then** the system prompt includes: (1) workspace persona_desc from channel_configs, (2) AI disclosure instruction with ai_disclosure text, (3) grounding instructions ("Answer only from context; if context doesn't contain the answer state inability"), (4) retrieved chunks with source names, (5) last 10 conversation turns from Redis, (6) current visitor message (BOT5, BOT11)

**Given** the prompt is constructed
**When** the Groq API is called with Llama 3.1 8B
**Then** the response is returned and sent to the visitor via the channel adapter within 5 seconds p95 from webhook receipt (BOT4, NFR-CB1)

**Given** the LLM returns a response
**When** it is sent to the visitor
**Then** message persisted to chat_messages with: sender_role=bot, message_text, bot_confidence (cosine score of best chunk), token_count

**Given** the Groq API times out or returns an error
**When** the worker catches the exception
**Then** message processing retried with exponential backoff up to 3 times; after 3 failures dead-lettered to chatbot:deadletter:{workspace_id} (WS3, NFR-CB6)

**Given** all retrieved chunks have cosine similarity < 0.4
**When** the grounding check runs
**Then** bot responds with the "I don't have that information — let me connect you to someone who can help" message; the low-confidence turn is counted toward the escalation trigger threshold (BOT5, BOT7c)

---

### Story 4.3: Escalation Detection and Trigger Handling

As the system,
I want the chat worker to detect escalation conditions and transition conversations to escalated state with human agent notification,
So that visitors who need human help are surfaced in the admin inbox within 30 seconds.

**Acceptance Criteria:**

**Given** a visitor message contains explicit human request phrasing ("talk to someone", "speak to an agent", "human please", "I want a human", and similar)
**When** EscalationDetector.check() evaluates the message
**Then** it returns EscalationTrigger.EXPLICIT_REQUEST; escalation flow initiated (BOT7a)

**Given** the best retrieved chunk has cosine similarity < 0.4 and this is the 3rd consecutive low-confidence response in the session
**When** EscalationDetector.check() evaluates
**Then** it returns EscalationTrigger.LOW_CONFIDENCE; escalation initiated (BOT7b, BOT7c)

**Given** an escalation trigger is detected
**When** the escalation flow runs
**Then** (1) configured escalation message sent to visitor via channel adapter, (2) chat_conversations.status updated to escalated, (3) escalation_reason records the trigger type, (4) chat_messages records the bot's escalation message, (5) escalation event pushed to SSE endpoint for inbox real-time update (BOT8, HH8)

**Given** an escalation occurs outside configured business hours
**When** the out-of-hours check runs
**Then** out-of-hours message sent instead of escalation message; chat_conversations.out_of_hours_flag set to true; thread status set to out_of_hours (CH7)

**Given** a conversation has been escalated and an agent has replied
**When** the worker receives a new inbound message for that thread
**Then** the bot does not generate a response; message saved with sender_role=visitor; thread remains in agent_active state (HH5)

---

### Story 4.4: Token Cap Enforcement and First-Visit Greeting

As the system,
I want the chat worker to enforce the per-session LLM token cap and greet first-time visitors with the configured greeting message,
So that costs are controlled and every visitor receives a consistent onboarding experience.

**Acceptance Criteria:**

**Given** a first-time visitor sends their first message
**When** the worker processes it
**Then** if the conversation session has zero prior turns, the bot first sends the configured greeting_msg (or default "Hi! I'm [bot_name], an AI assistant. How can I help you today?") before processing the visitor's message; greeting logged with sender_role=bot (BOT2)

**Given** the session session_token_count is tracked per conversation
**When** the LLM generates a response
**Then** input + output token count is added to chat_conversations.session_token_count and to the Redis token budget key chatbot:token_budget:{workspace_id}:{conversation_id}

**Given** session_token_count >= token_cap (default 4000)
**When** a new message arrives for that conversation
**Then** bot sends: "I've reached the limit of what I can help with in this session. Let me connect you with a team member who can continue helping you."; conversation is escalated; no further LLM calls made for this session (NFR-CB16)

**Given** the token cap is hit
**When** escalation is triggered
**Then** escalation_reason is recorded as "token_limit_reached"; thread appears in inbox with escalated status

---

## Epic 5: Lead Capture & Contact Integration

**Goal:** The bot detects visitor purchase intent, presents a PDPA/GDPR-compliant privacy consent notice, collects name and contact details (email/phone), deduplicates against existing contacts, and creates a Contact record in the SignalLoop contact pool with the chatbot-lead tag and intent field. All consent events are logged.

---

### Story 5.1: Lead Capture State Machine and Contact Write-Back

As the system,
I want the chat worker to detect lead intent, present a privacy consent notice, collect contact details, and write a Contact record to the SignalLoop contact pool,
So that captured leads flow into the existing pipeline for sequence and call follow-up.

**Acceptance Criteria:**

**Given** a conversation has reached min_turns_before_trigger (default 3) and the visitor message expresses purchase intent, demo request, pricing inquiry, or configured intent keywords
**When** the lead capture trigger check runs
**Then** lead_capture_state transitions from open to privacy_notice; bot sends the configured privacy notice message including the privacy_policy_url link (LC1, LC3)

**Given** the visitor responds affirmatively to the privacy notice
**When** the consent check runs
**Then** lead_capture_state transitions to collecting; consent event written to audit log with response=accepted, timestamp, conversation_id; bot prompts for name and contact (LC2, LC7)

**Given** the visitor provides their name and email or phone number
**When** the contact creation step runs
**Then** system checks for existing Contact in workspace with same email/phone; if none: POST /api/v1/contacts creates new Contact with source=chatbot, tag=chatbot-lead, intent=<detected_intent>; if exists: last_seen_at updated and new intent tag appended without duplicate (LC4, LC5)

**Given** the visitor declines the privacy notice or declines to provide contact details
**When** decline is detected
**Then** consent event written to audit log with response=declined; lead_capture_state transitions to declined; conversation continues normally; bot does not re-prompt in this session (LC3, LC6, LC7)

**Given** a Contact is created from a lead capture flow
**When** the confirmation step runs
**Then** bot sends confirmation message; lead_capture_state transitions to created; chat_conversations.contact_id set to new/updated contact ID; chat_conversations.outcome set to lead_captured (LC4)

---

### Story 5.2: Lead Capture Configuration and Contact Pool Integration Test

As a workspace admin,
I want to configure the lead capture trigger settings and verify that captured leads appear correctly in the SignalLoop contacts pool,
So that I can tune the lead capture behaviour and confirm end-to-end integration.

**Acceptance Criteria:**

**Given** an admin sets lead_capture_min_turns = 5 and intent_keywords = ["demo", "pricing", "buy"] in Bot Settings
**When** the chat worker evaluates a conversation
**Then** lead capture is not triggered until 5 turns have elapsed AND an intent keyword is detected

**Given** a lead is captured with intent = "demo-request" from a WhatsApp conversation
**When** the admin navigates to /contacts
**Then** the new contact appears with: source tag whatsapp, tag chatbot-lead, intent demo-request, and the visitor's name and phone/email (LC4)

**Given** the same phone number triggers lead capture a second time
**When** the deduplication check runs
**Then** no duplicate contact created; existing contact last_seen_at updated; chatbot-lead tag retained; new intent tag appended if different (LC5)

**Given** the privacy policy URL is configured in workspace_bot_config
**When** the privacy notice is sent by the bot
**Then** the URL is included in the message; the notice uses the configured privacy_notice_text field

---

## Epic 6: Admin Inbox & Human Handoff

**Goal:** Agents can view all conversation threads in real time, open escalations to see full context, reply as a human agent, resolve threads, filter the queue by channel/status/date, receive in-app escalation notifications, and export conversation data.

---

### Story 6.1: Inbox Thread API — List, Detail, Reply, and Resolve

As a workspace admin or agent,
I want API endpoints that provide the inbox thread list, thread detail, agent reply, and thread resolution,
So that the frontend inbox UI can be built on a complete and secure backend.

**Acceptance Criteria:**

**Given** GET /api/v1/chatbot/inbox/threads is called with optional query params ?status=escalated&channel=whatsapp&from=2026-05-01&to=2026-05-13
**When** the response is returned
**Then** threads filtered by workspace_id and provided filters; sorted by last_activity_at DESC; cursor-paginated; each thread includes: id, channel, visitor_id, visitor_name (if captured), last_message_preview (80 chars), last_activity_at, status, unread_count; p95 response time <= 3 seconds (HH1, HH7, NFR-CB3)

**Given** GET /api/v1/chatbot/inbox/threads/{thread_id} is called
**When** the response is returned
**Then** includes full thread metadata plus complete message history (chat_messages ordered by sent_at ASC); each message includes sender_role, message_text, sent_at, bot_confidence; customer_last_message_at included for WhatsApp threads

**Given** POST /api/v1/chatbot/inbox/threads/{thread_id}/reply is called with { "message": "..." } by an agent
**When** processed
**Then** for WhatsApp: if customer_last_message_at > 24h ago, HTTP 422 with whatsapp_window_expired returned; no message sent
**And** for valid replies: message sent via channel adapter; chat_messages row created with sender_role=agent; thread status set to agent_active; response within 3 seconds p95 (HH4, NFR-CB4)

**Given** PATCH /api/v1/chatbot/inbox/threads/{thread_id}/resolve is called
**When** processed
**Then** chat_conversations.status set to resolved; ended_at set to now; outcome set; HTTP 200 returned (HH6)

**Given** PATCH /api/v1/chatbot/inbox/threads/{thread_id}/reopen is called
**When** processed
**Then** chat_conversations.status reverts to escalated; ended_at cleared; HTTP 200 returned

---

### Story 6.2: Real-Time Inbox UI — Thread List with SSE

As a workspace admin or agent,
I want the inbox thread list to update in real time when new escalations arrive,
So that I never miss an escalation requiring human response.

**Acceptance Criteria:**

**Given** an agent has the Inbox page open at /chatbot/inbox
**When** the page loads
**Then** it renders the left panel (380px) with thread list sorted by last_activity_at DESC; each thread is a ThreadRow with left colour-accent border (amber=escalated, blue=bot-active, indigo=agent-active, green=resolved, violet=out-of-hours, slate=opted-out); filter bar shows All/Escalated/Bot-active/Resolved tabs plus Channel dropdown (HH1, HH2, HH7, UX-DR4)

**Given** the SSE connection to /api/v1/chatbot/inbox/events is established
**When** a new escalation event is pushed
**Then** the new ThreadRow appears at the top of the list with amber flash animation (250ms); escalation badge count on sidebar Inbox nav item increments by 1; a toast notification appears with visitor name and channel (HH8)

**Given** the user's browser does not support SSE or SSE is disconnected
**When** the inbox page detects the disconnection
**Then** the page falls back to 30-second polling of GET /api/v1/chatbot/inbox/threads without error

**Given** an agent selects a thread
**When** the thread is clicked
**Then** the right panel shows Thread Detail for that thread; thread row is visually marked selected; unread indicator cleared; sidebar Inbox badge decrements if thread was escalated and unread

**Given** the inbox has no threads
**When** empty state renders
**Then** "No conversations yet. Conversations will appear here when your first channel is connected and receives a message." is displayed

---

### Story 6.3: Thread Detail UI — Message History and Agent Reply

As a workspace agent,
I want to see the full conversation history in the thread detail panel and reply to visitors as a human agent,
So that I can provide high-quality human support to escalated conversations.

**Acceptance Criteria:**

**Given** a thread is open in the right panel
**When** the Thread Detail renders
**Then** it shows: header with visitor name/handle, channel badge, status badge, action buttons (Re-enable Bot / Resolve); scrollable message history with bot messages as MessageBubble (left, slate bg), visitor messages (left, white border), agent messages (right, primary bg, white text); bot messages show AI disclosure badge (HH3, UX-DR2)

**Given** the thread is a WhatsApp thread and customer_last_message_at > 24 hours ago
**When** Thread Detail renders
**Then** reply textarea is replaced by WhatsAppWindowBanner: "WhatsApp 24-hour messaging window has expired. The visitor must send a message first to reopen the conversation." (amber background, non-dismissable); Send button is hidden (NFR-CB15, UX-DR2, UX-DR4)

**Given** the WhatsAppWindowBanner is showing and the visitor sends a new message (SSE event)
**When** the SSE update is processed
**Then** customer_last_message_at is updated; the banner is replaced by the reply textarea automatically without page refresh

**Given** an agent types a reply and clicks Send
**When** the reply is submitted
**Then** POST /api/v1/chatbot/inbox/threads/{thread_id}/reply is called; on success, the agent's message appears in message history immediately; thread status badge updates to "Agent Active" (HH4, HH5)

**Given** an opted-out visitor's thread is opened
**When** Thread Detail renders
**Then** the reply area shows: "Visitor has opted out. Human agents may still reply manually if the visitor re-initiates contact." instead of the standard reply box (OC2)

---

### Story 6.4: Conversation Export

As a workspace admin,
I want to export conversation threads as CSV or JSON,
So that I can analyse conversation data offline or meet compliance record-keeping requirements.

**Acceptance Criteria:**

**Given** an admin makes GET /api/v1/chatbot/inbox/threads/export?format=csv&from=2026-05-01&to=2026-05-13&channel=whatsapp
**When** processed
**Then** HTTP 200 returned with appropriate Content-Type (text/csv or application/json); file includes: message_id, conversation_id, channel, visitor_id, visitor_name, sender_role, message_text, sent_at, bot_confidence, captured_lead_details; all records scoped to requesting workspace only (HH9)

**Given** an agent role (not admin) calls the export endpoint
**When** processed
**Then** HTTP 403 returned; no data returned (HH9 — admin only)

**Given** a date range is requested that spans > 10,000 messages
**When** the export runs
**Then** the export completes without timeout (processed as streaming response or background job with download link); export is not truncated

---

## Epic 7: Opt-Out & Compliance Controls

**Goal:** The system immediately enforces opt-out keywords across all channels, maintains an audit log of all opt-out and consent events, prevents the bot from re-engaging opted-out visitors, and provides admins with an Opt-outs tab in the existing Settings page.

---

### Story 7.1: Opt-Out Detection, Enforcement, and Audit Log

As the system,
I want to immediately detect opt-out keywords, cease all automated bot responses for that visitor, record the opt-out event, and enforce opt-out status on all subsequent messages,
So that the platform meets WhatsApp Business and Meta platform compliance requirements.

**Acceptance Criteria:**

**Given** a visitor sends "STOP" on WhatsApp (or "Unsubscribe", "Cancel", "Quit" on any channel)
**When** is_opt_out_message() is called by the channel adapter
**Then** returns True; chat worker immediately ceases bot processing; opt_out_registry row created/updated with workspace_id, channel, visitor_id, opted_out_at, opted_out_by=visitor, is_active=true (OC1)

**Given** the opt-out is recorded
**When** the chat worker finalises processing
**Then** chat_conversations.status set to opted_out; opt-out event written to audit log with: timestamp, channel, visitor_id, opt-out keyword used; HTTP 200 returned to channel provider (OC1)

**Given** an opted-out visitor sends any subsequent message
**When** the chat worker processes it
**Then** opt_out_registry checked first; no bot response generated; thread surfaced in inbox with opted_out badge; RAG pipeline not invoked (BOT13, OC2)

**Given** an opted-out visitor sends a re-initiating message AND re_opt_in_invitation_enabled is true
**When** the worker processes the message
**Then** a single re-opt-in invitation is sent ("We noticed you previously opted out. Reply YES to re-subscribe."); this invitation is only sent once per re-initiation event (OC3)

**Given** re_opt_in_invitation_enabled is false (default)
**When** an opted-out visitor sends a message
**Then** no bot message sent; thread appears in inbox for human review only (OC3 default)

---

### Story 7.2: Opt-Out Management UI (Settings Tab)

As a workspace admin,
I want an Opt-outs tab in the existing Settings page where I can view all opted-out visitors and manually re-enable bot engagement after confirming re-consent,
So that I can manage opt-outs in compliance with platform policy.

**Acceptance Criteria:**

**Given** an admin navigates to /settings and clicks the "Opt-outs" tab
**When** the tab renders
**Then** a table is shown listing all opted-out visitors for the workspace with columns: channel, visitor name/handle, opted-out at, opted-out by (visitor/admin); paginated 25 per page; only admin role can see this tab (OC4, UX-DR6)

**Given** an admin clicks "Re-enable" on an opted-out visitor row
**When** the confirmation dialog appears
**Then** dialog reads: "Re-enabling bot engagement for this visitor. Please confirm the visitor has explicitly re-consented to receive messages."; admin must click a confirm button (not just close the dialog)

**Given** the admin confirms the re-enable action
**When** DELETE /api/v1/chatbot/opt-outs/{opt_out_id} is called
**Then** opt_out_registry.is_active set to false; re_enabled_at set to now; re_enabled_by set to admin user_id; row disappears from Opt-outs tab; audit log records the admin re-enable event (OC4)

**Given** the workspace has zero opted-out visitors
**When** the Opt-outs tab renders
**Then** empty state: "No opted-out visitors. Opt-out requests will appear here."

---

## Epic 8: Analytics Dashboard

**Goal:** Admins can view a per-workspace analytics dashboard showing conversation volumes, bot containment rate, escalation count, leads captured, and channel breakdown for configurable date ranges. Analytics data is pre-aggregated every 15 minutes.

---

### Story 8.1: Analytics Snapshot Job and API

As the system,
I want per-conversation metadata recorded and pre-aggregated into analytics snapshots every 15 minutes,
So that the analytics dashboard can query pre-computed data efficiently.

**Acceptance Criteria:**

**Given** a conversation is completed
**When** the chat worker finalises the outcome
**Then** chat_conversations.outcome is set to one of: bot_resolved, escalated, lead_captured; ended_at set; per-turn bot_confidence scores stored in chat_messages (AN3)

**Given** the analytics snapshot scheduler runs every 15 minutes
**When** the job executes for a workspace
**Then** it computes for current snapshot_date: total_conversations, total_messages, bot_resolved count, escalations, leads_captured — both per channel and as workspace aggregate (NULL channel); upserts into analytics_snapshots (AN2, ARCH9)

**Given** GET /api/v1/chatbot/analytics?from=2026-05-01&to=2026-05-13 is called
**When** the response is returned
**Then** includes: summary totals for the date range, daily time-series data, and channel breakdown — all computed from analytics_snapshots; scoped to requesting workspace (AN1, AN4)

**Given** a request is made by an agent role
**When** analytics API responds
**Then** data returned read-only (agents can view); export restricted to admin (NFR-CB11)

---

### Story 8.2: Analytics Dashboard UI

As a workspace admin or agent,
I want an analytics dashboard at /chatbot/analytics with summary stats, charts, and a channel breakdown table,
So that I can monitor bot performance and make informed decisions about knowledge base improvements.

**Acceptance Criteria:**

**Given** an admin navigates to /chatbot/analytics
**When** the page renders (default: last 7 days)
**Then** shows: date range picker; 4 stat cards (Total Conversations, Bot Containment Rate, Leads Captured, Escalations); a line chart of conversations over time; a bar chart of channel breakdown; a table with columns: Channel, Bot-resolved, Escalated, Lead-captured, Opted-out (AN1)

**Given** the admin changes the date range picker to "Last 30 days"
**When** applied
**Then** GET /api/v1/chatbot/analytics?from=...&to=... is called; all charts and stats update without a full page reload

**Given** the workspace has conversations from multiple channels
**When** the channel breakdown table renders
**Then** each connected channel appears as a row with per-channel counts; last row shows workspace aggregate

**Given** analytics data was last updated 5 minutes ago
**When** the admin views the page
**Then** "Updated X min ago" badge shown near date picker; manual "Refresh" button triggers GET /api/v1/chatbot/analytics

**Given** the workspace has no conversation data
**When** the analytics page renders
**Then** all stat cards show "0" or "—"; empty state message: "Not enough data yet. Analytics update every 15 minutes once conversations begin."

---

## Epic 9: Bot Configuration & Settings UI

**Goal:** Admins can configure the bot persona, AI disclosure text, business hours, token cap, conversation retention, privacy policy URL, and lead capture trigger settings from a dedicated Bot Settings page with inline editing and a sticky unsaved-changes bar.

---

### Story 9.1: Bot Configuration API

As a workspace admin,
I want API endpoints to read and update all workspace-level and channel-level bot configuration settings,
So that the settings UI and future integrations have a complete, validated configuration contract.

**Acceptance Criteria:**

**Given** GET /api/v1/chatbot/config is called
**When** the response is returned
**Then** includes all workspace_bot_config fields (business_hours_timezone, business_hours_days, business_hours_start, business_hours_end, token_cap_per_session, retention_days, privacy_notice_text, privacy_policy_url, reindex_schedule_time) and a lead_capture sub-object (min_turns, intent_keywords, re_opt_in_invitation_enabled)

**Given** PUT /api/v1/chatbot/config is called with { "token_cap_per_session": 6000 }
**When** processed
**Then** workspace_bot_config.token_cap_per_session updated to 6000; change takes effect for new sessions; existing sessions continue with original cap; HTTP 200 returned

**Given** PUT /api/v1/chatbot/config is called with { "ai_disclosure": "" }
**When** processed
**Then** HTTP 422 returned with ai_disclosure_required error; field cannot be empty (BOT11); config not updated

**Given** PUT /api/v1/chatbot/config is called with { "retention_days": 10 }
**When** processed
**Then** HTTP 422 returned with retention_days_minimum error; minimum is 30 days (NFR-CB12); config not updated

**Given** PUT /api/v1/chatbot/channels/{channel_id} is called with updated persona_desc, greeting_msg, escalation_msg, out_of_hours_msg, ai_disclosure
**When** processed
**Then** all provided fields updated in channel_configs; new values take effect for new bot responses on that channel; HTTP 200 returned (CH5, CH9)

---

### Story 9.2: Bot Settings UI Page

As a workspace admin,
I want a Bot Settings page at /chatbot/settings with inline-editable configuration sections and a sticky unsaved-changes bar,
So that I can configure all bot behaviour without complex UI interactions.

**Acceptance Criteria:**

**Given** an admin navigates to /chatbot/settings
**When** the page renders
**Then** shows 4 sections separated by Separator: (1) AI & Disclosure (ai_disclosure text, token_cap_per_session), (2) Lead Capture (enable toggle, min_turns, intent_keywords tag input, privacy_policy_url), (3) Business Hours (enable toggle, timezone select, Mon-Sun time range pickers), (4) Compliance (retention_days input, link to Opt-outs tab in /settings); all fields pre-populated from GET /api/v1/chatbot/config

**Given** the admin changes any field value
**When** the field is edited
**Then** a sticky bottom bar appears with "You have unsaved changes" + [Save Changes] and [Discard] buttons

**Given** the admin clicks "Save Changes"
**When** the save is submitted
**Then** PUT /api/v1/chatbot/config called with all changed fields; on success: sticky bar disappears with toast "Settings saved"; on validation error: bar remains with inline field errors per field; no page navigation

**Given** the admin clicks "Discard"
**When** the discard action runs
**Then** all unsaved values revert to last saved values; sticky bar disappears

**Given** the ai_disclosure field is cleared to empty
**When** the admin tries to save
**Then** Save button is disabled (or shows inline error) until field contains at least 1 character; field border turns red with message "AI disclosure text is required and cannot be disabled"

**Given** the retention_days field is set below 30
**When** the admin tries to save
**Then** inline error "Minimum retention period is 30 days" shown; Save is blocked until a valid value is entered (NFR-CB12)

---

_Document complete — 2026-05-13_
_9 Epics · 30 Stories · 63 FRs covered · 16 NFRs referenced · 9 Architecture requirements · 6 UX Design requirements_
