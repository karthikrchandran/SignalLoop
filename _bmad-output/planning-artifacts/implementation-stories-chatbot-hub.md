---
workflowType: bmad-implementation-stories
date: "2026-06-05"
project: "SignalLoop - ChatBot Hub"
sourceDocuments:
  - _bmad-output/planning-artifacts/prd-chatbot-hub.md
  - _bmad-output/planning-artifacts/architecture-chatbot-hub.md
  - _bmad-output/planning-artifacts/ux-design-chatbot-hub.md
  - _bmad-output/planning-artifacts/screen-stories-wireframes-chatbot-hub.md
  - _bmad-output/planning-artifacts/epics.md
status: draft-ready-for-implementation-planning
totalEpics: 8
totalStories: 36
---

# ChatBot Hub Implementation Epics and Stories

## Overview

This artifact converts the ChatBot Hub PRD, architecture, UX spec, and screen-level wireframes into implementation-ready epics and stories.

It complements the existing `_bmad-output/planning-artifacts/epics.md`, which already contains a full functional epic breakdown. This file is more execution-oriented: every story names the target screens, likely API contracts, repo touchpoints, and verification expectations.

## Delivery Principles

1. Deliver vertical slices that users can see, not isolated technical layers.
2. Keep ChatBot Hub inside the existing SignalLoop portal and role model.
3. Enforce workspace isolation in every API, worker, repository, and vector query.
4. Expose async state visibly in the UI: indexing, channel health, inbox events, delivery failures.
5. Treat compliance constraints as product behavior: AI disclosure, opt-out, WhatsApp window, privacy consent.

## Epic Summary

| Epic | Goal | Main screens | Core dependencies |
|---|---|---|---|
| CBH-E1 Foundation and Navigation | Create the shared data, route, and navigation foundation | CBH-S00 | Existing auth/layout |
| CBH-E2 Channels and Webhooks | Let admins connect channels and ingest verified inbound messages | CBH-S01, CBH-S02 | E1 |
| CBH-E3 Knowledge Base and Test Bot | Let admins build and test the shared bot brain | CBH-S03, CBH-S04 | E1 |
| CBH-E4 Bot Runtime and Lead Capture | Process inbound messages with RAG, escalation, consent, and contact write-back | Visitor channels, Inbox data | E2, E3 |
| CBH-E5 Inbox and Human Handoff | Let agents triage, reply, resolve, and export conversations | CBH-S05, CBH-S06 | E2, E4 |
| CBH-E6 Settings and Compliance Controls | Let admins configure safe behavior and manage opt-outs | CBH-S08, CBH-S09 | E1, E4 |
| CBH-E7 Analytics | Let admins and agents monitor chatbot performance | CBH-S07 | E4, E5 |
| CBH-E8 Release Hardening | Verify performance, isolation, compliance, accessibility, and release gates | All | E1-E7 |

## Requirement Coverage

| Requirement group | Primary epics |
|---|---|
| CH1-CH9 Channel management | CBH-E2, CBH-E6 |
| KB1-KB12 Knowledge base | CBH-E3 |
| BOT1-BOT13 Conversation engine | CBH-E4 |
| LC1-LC7 Lead capture | CBH-E4, CBH-E6 |
| HH1-HH9 Human handoff and inbox | CBH-E5 |
| OC1-OC4 Opt-out/compliance | CBH-E4, CBH-E6 |
| AN1-AN4 Analytics | CBH-E7 |
| WS1-WS5 Webhook reliability | CBH-E2, CBH-E8 |
| NFR-CB1-CB16 | CBH-E1-CBH-E8, with final validation in CBH-E8 |

---

## CBH-E1: Foundation and Navigation

### Outcome

Admins and agents can see ChatBot Hub as a first-class section in the existing SignalLoop portal, and the backend has the persistent structures required by later vertical slices.

### Story CBH-E1-S1: Create ChatBot Hub Database Foundation

As a developer, I want pgvector enabled and ChatBot Hub tables added through migrations so that all subsequent stories have workspace-scoped persistence.

Screens: none directly, supports all screens.

Primary backend touchpoints:

- `compose.yml`
- `apps/api/app/alembic/versions/*`
- SQLModel models for channel config, bot config, knowledge sources, chunks, conversations, messages, opt-outs, analytics snapshots

Acceptance criteria:

1. `db` uses `pgvector/pgvector:pg17`.
2. First migration runs `CREATE EXTENSION IF NOT EXISTS vector`.
3. All ChatBot Hub tables include `workspace_id`.
4. Required uniqueness and query indexes from the architecture are present.
5. `uv run alembic upgrade head` succeeds from `apps/api`.
6. Migration tests confirm no cross-workspace reads for representative tables.

Verification:

- Backend migration tests.
- `docker compose config --quiet`.
- Cross-workspace repository tests.

### Story CBH-E1-S2: Add API Domain Skeleton and Repository Guardrails

As a developer, I want shared chatbot domain modules and repository conventions so that every feature uses consistent workspace isolation and error handling.

Screens: none directly.

Primary backend touchpoints:

- `apps/api/app/domain/chatbot/`
- `apps/api/app/routers/chatbot/`
- `apps/api/app/infrastructure/vector_store/`
- `apps/api/app/infrastructure/rag/`

Acceptance criteria:

1. Chatbot router package mounts under `/api/v1/chatbot`.
2. Repository functions accept `workspace_id` as the first argument.
3. Shared response envelope follows existing SignalLoop conventions.
4. Role checks exist for admin-only, agent/admin, and operator-only paths.
5. Tests fail if a repository query omits workspace filtering where feasible.

### Story CBH-E1-S3: Add Chatbot Sidebar Group and Placeholder Routes

As a workspace user, I want Chatbot routes visible in the existing sidebar so that I can reach the new surfaces without a separate app.

Screens: CBH-S00.

Primary frontend touchpoints:

- `apps/web/src/components/Sidebar/AppSidebar.tsx`
- `apps/web/src/components/Sidebar/Main.tsx`
- `apps/web/src/routes/_layout/chatbot.channels.tsx`
- `apps/web/src/routes/_layout/chatbot.knowledge-base.tsx`
- `apps/web/src/routes/_layout/chatbot.inbox.tsx`
- `apps/web/src/routes/_layout/chatbot.analytics.tsx`
- `apps/web/src/routes/_layout/chatbot.settings.tsx`

Acceptance criteria:

1. Admin sees Channels, Knowledge Base, Inbox, Analytics, and Settings.
2. Agent sees Inbox and Analytics only unless current role policy says otherwise.
3. Inbox badge appears only when open escalation count is greater than zero.
4. Placeholder route pages render without 404.
5. Existing non-chatbot routes are unchanged.

Verification:

- Frontend route/render tests.
- Role visibility tests.

---

## CBH-E2: Channels and Webhooks

### Outcome

Admins can connect Facebook Messenger, WhatsApp Business, and Telegram, and verified inbound messages enter the async chatbot queue with deduplication.

### Story CBH-E2-S1: Implement Channel Config API and Credential Storage

As an admin, I want CRUD and toggle APIs for channel configs so that channel setup is secure and workspace-scoped.

Screens: CBH-S01, CBH-S02.

API:

- `GET /api/v1/chatbot/channels`
- `POST /api/v1/chatbot/channels`
- `GET /api/v1/chatbot/channels/{channel_id}`
- `PUT /api/v1/chatbot/channels/{channel_id}`
- `DELETE /api/v1/chatbot/channels/{channel_id}`
- `PATCH /api/v1/chatbot/channels/{channel_id}/toggle`

Acceptance criteria:

1. Admin can create, update, delete, and toggle channels.
2. Credentials are stored through existing encrypted `ProviderCredential`.
3. API responses mask tokens and secrets.
4. Agent role receives 403 for mutating channel endpoints.
5. Cross-workspace channel access returns 403 or 404 without leaking metadata.

### Story CBH-E2-S2: Implement ChatChannelAdapter Registry and Provider Adapters

As the system, I want each channel adapter to share one interface so that workers and webhook routers can process channels uniformly.

Screens: supports CBH-S01, CBH-S02.

Backend touchpoints:

- `apps/api/app/infrastructure/providers/chat/base.py`
- `apps/api/app/infrastructure/providers/chat/facebook_messenger.py`
- `apps/api/app/infrastructure/providers/chat/whatsapp_cloud.py`
- `apps/api/app/infrastructure/providers/chat/telegram_bot.py`
- `apps/api/app/infrastructure/providers/chat/registry.py`

Acceptance criteria:

1. Adapter interface includes webhook verification, event parsing, `send_message() -> DeliveryReceipt`, visitor normalization, opt-out detection, and non-text detection.
2. Facebook verifies `X-Hub-Signature-256` and hub challenge.
3. WhatsApp verifies Meta challenge/signature and normalizes phone visitor IDs.
4. Telegram verifies the exact `X-Telegram-Bot-Api-Secret-Token` header.
5. Unit tests cover valid, invalid, duplicate, and non-text cases per adapter.

### Story CBH-E2-S3: Implement Webhook Ingestion Queue, Dedup, Audit, and Dead Letter

As the system, I want verified inbound channel events acknowledged quickly and processed asynchronously so that provider webhooks are reliable.

Screens: channel status and operator diagnostics.

Backend touchpoints:

- `apps/api/app/routers/webhooks/chat_webhooks.py`
- Redis keys `chatbot:inbound:{workspace_id}`, `chatbot:dedup:{workspace_id}:{channel}:{provider_message_id}`, `chatbot:deadletter:{workspace_id}`
- audit log integration

Acceptance criteria:

1. Invalid signatures return 401 and are logged before payload processing.
2. Valid message events return 200 within 5 seconds and enqueue payload.
3. Duplicate provider message IDs are acknowledged but not requeued.
4. Inactive channel events are acknowledged but not sent to bot processing.
5. Failed processing retries up to 3 times and then dead-letters visibly.

### Story CBH-E2-S5: Implement Dead-Letter Operator API and Retry Flow

As an operator, I want dead-lettered chatbot messages to be visible and retryable so that no verified inbound message fails silently.

Screens: operator diagnostics; no admin-facing MVP screen required unless operations requests one.

API:

- `GET /api/v1/chatbot/dead-letters`
- `POST /api/v1/chatbot/dead-letters/{id}/retry`

Backend touchpoints:

- `apps/api/app/routers/chatbot/dead_letters.py`
- Redis key `chatbot:deadletter:{workspace_id}`
- worker retry/dead-letter helper
- existing operator/admin role guard

Acceptance criteria:

1. After 3 worker failures, the original message payload, provider message ID, channel, workspace ID, attempt count, last error, and failed timestamp are written to `chatbot:deadletter:{workspace_id}`.
2. Dead-letter records are retained for 7 days unless retried or purged by operator policy.
3. `GET /api/v1/chatbot/dead-letters` returns only records for the current workspace unless the caller has explicit operator/superuser scope.
4. `POST /api/v1/chatbot/dead-letters/{id}/retry` requeues the original message to `chatbot:inbound:{workspace_id}`, increments retry metadata, and removes or marks the dead-letter item as retried.
5. Retrying a duplicate provider message preserves WS5 deduplication semantics and does not create duplicate bot responses.
6. All dead-letter view and retry actions are audit logged.
7. Unit and integration tests cover list, retry, unauthorized access, cross-workspace isolation, and expired/deleted dead-letter behavior.

### Story CBH-E2-S4: Build Channels Page and Connection Sheet

As an admin, I want the Channels page and connection sheet so that I can connect and monitor each supported channel.

Screens: CBH-S01, CBH-S02.

Frontend touchpoints:

- `apps/web/src/features/chatbot/ChannelsPage.tsx`
- `apps/web/src/features/chatbot/components/ChannelCard.tsx`
- `apps/web/src/features/chatbot/components/ChannelConnectionSheet.tsx`
- `apps/web/src/features/chatbot/api.ts`

Acceptance criteria:

1. Page renders Facebook, WhatsApp, and Telegram ChannelCards.
2. Cards show disconnected, connecting, connected, inactive, error, and pending approval states.
3. Connect/Edit opens a provider-specific sheet.
4. Save & Verify keeps the sheet open on error and updates the card on success.
5. Keyboard focus moves into and out of the sheet correctly.

---

## CBH-E3: Knowledge Base and Test Bot

### Outcome

Admins can create knowledge sources, watch indexing progress, and test grounded bot answers against the current index.

### Story CBH-E3-S1: Implement Knowledge Source CRUD API

As an admin, I want to add, edit, delete, and list knowledge sources so that I can manage bot content.

Screens: CBH-S03.

API:

- `GET /api/v1/chatbot/knowledge-sources`
- `POST /api/v1/chatbot/knowledge-sources`
- `PUT /api/v1/chatbot/knowledge-sources/{source_id}`
- `DELETE /api/v1/chatbot/knowledge-sources/{source_id}`
- `GET /api/v1/chatbot/knowledge-sources/{source_id}/status`

Acceptance criteria:

1. URL, document, FAQ/free-form, and Q&A sources are supported.
2. Document upload rejects unsupported types and files over 20 MB.
3. Source status includes pending, indexing, ready, failed, and stale.
4. Every source is scoped to workspace.
5. Admin can delete a source without deleting unrelated chunks from another workspace.

### Story CBH-E3-S2: Implement Ingestion Worker for Crawl and Document Parsing

As an admin, I want sources indexed in the background so that long-running ingestion does not block the UI.

Screens: CBH-S03 progress banner.

Backend touchpoints:

- `apps/workers/knowledge_indexing_worker.py`
- `apps/api/app/infrastructure/rag/crawler.py`
- `apps/api/app/infrastructure/rag/document_parser.py`

Acceptance criteria:

1. URL crawl uses `httpx` and `BeautifulSoup4`.
2. Crawl depth is constrained to 1-5 and max 50 pages per source.
3. PDF extraction uses `pypdf2`, DOCX extraction uses `python-docx`, and TXT extraction uses safe text decoding.
4. Worker reports progress and failure details per source.
5. Re-indexing 50 pages and 5 documents meets the 10 minute p95 target in release testing.

### Story CBH-E3-S3: Implement Chunking, Embedding, pgvector Store, and Index Versioning

As the system, I want knowledge chunks embedded into a workspace-scoped vector index so that bot answers use the correct business knowledge.

Screens: CBH-S03, CBH-S04.

Backend touchpoints:

- `apps/api/app/infrastructure/rag/chunker.py`
- `apps/api/app/infrastructure/rag/embedder.py`
- `apps/api/app/infrastructure/vector_store/chunk_repository.py`

Acceptance criteria:

1. Chunking uses `RecursiveCharacterTextSplitter` with approximately 300-500 token chunks and overlap.
2. Embedding uses `nomic-embed-text` through Ollama by default.
3. Chunks are written with `workspace_id`, `source_id`, and `index_version`.
4. Retrieval always filters by `workspace_id` and active or pinned `index_version`.
5. Active sessions keep pinned index version during re-index.

### Story CBH-E3-S4: Implement Manual and Scheduled Re-index

As an admin, I want manual and nightly re-indexing so that my bot stays current.

Screens: CBH-S03.

API:

- `POST /api/v1/chatbot/knowledge-sources/reindex`

Acceptance criteria:

1. Re-index All starts a background job and returns job/status metadata.
2. Scheduled re-index uses workspace local time and default 02:00.
3. Stale sources become ready or failed after indexing.
4. Old chunks are retained while active sessions reference their version.
5. Progress events are consumable by the frontend.

### Story CBH-E3-S5: Build Knowledge Base Page and Test Bot Sheet

As an admin, I want a complete Knowledge Base page with Test Bot so that I can validate answers before going live.

Screens: CBH-S03, CBH-S04.

Frontend touchpoints:

- `apps/web/src/features/chatbot/KnowledgeBasePage.tsx`
- `apps/web/src/features/chatbot/components/KnowledgeSourceRow.tsx`
- `apps/web/src/features/chatbot/components/IndexingProgressBanner.tsx`
- `apps/web/src/features/chatbot/components/TestBotSheet.tsx`

Acceptance criteria:

1. Page has Website URLs, Documents, and FAQ/Q&A tabs.
2. Indexing progress appears below the page header and can be dismissed after completion.
3. Source rows show type, status, chunk count, last indexed time, and failure details.
4. Test Bot sheet sends test questions and renders answer, AI disclosure, source name, chunk excerpt, and similarity score.
5. Empty, loading, error, and no-KB states are covered by component tests.

---

## CBH-E4: Bot Runtime and Lead Capture

### Outcome

Inbound messages produce grounded responses, escalations, or compliant lead capture while preserving opt-out and token-budget controls.

### Story CBH-E4-S1: Implement Chat Worker Session Routing

As the system, I want a chat worker to consume queued inbound messages and maintain per-visitor sessions so that all channel messages are processed consistently.

Backend touchpoints:

- `apps/workers/chat_worker.py`
- Redis `chat:session:{workspace_id}:{channel}:{visitor_id}`
- `chat_conversations`, `chat_messages`

Acceptance criteria:

1. Worker consumes `chatbot:inbound:{workspace_id}` messages.
2. Session history stores at least last 10 turns with TTL.
3. Opt-out check happens before any RAG or LLM work.
4. Bot-off mode routes directly to inbox.
5. Non-text messages receive graceful fallback without RAG invocation.

### Story CBH-E4-S2: Implement RAG Prompting and Grounded LLM Responses

As a visitor, I want the bot to answer from the business knowledge base so that responses are accurate and useful.

Backend touchpoints:

- `apps/api/app/domain/chatbot/engine.py`
- `apps/api/app/domain/chatbot/prompts.py`
- `apps/api/app/infrastructure/rag/retriever.py`

Acceptance criteria:

1. Visitor message is embedded and retrieves top-k chunks from the pinned workspace index.
2. Prompt includes persona, AI disclosure, grounding instructions, source chunks, history, and current message.
3. LLM generation uses the configured provider with Groq Llama 3.1 8B as the default model, matching the architecture decision.
4. Best-chunk confidence is stored.
5. Low-confidence responses use the configured inability/escalation phrasing.
6. LLM response is delivered through the originating channel.
7. p95 bot response time is measured against the 5 second target.

### Story CBH-E4-S3: Implement Escalation Detection and Business Hours Behavior

As a visitor, I want a human handoff when the bot cannot help so that my issue is not trapped in automation.

Screens: CBH-S05, CBH-S06 receive escalated state.

Acceptance criteria:

1. Explicit human-request phrases trigger escalation.
2. Confidence below threshold triggers escalation based on configured logic.
3. Three consecutive unanswered/low-confidence turns trigger escalation.
4. Out-of-hours escalation sends configured out-of-hours message and tags thread.
5. Escalation event pushes to the inbox SSE channel.

### Story CBH-E4-S4: Implement Token Cap and AI Disclosure Enforcement

As an admin, I want AI disclosure and token budget controls enforced centrally so that compliance and cost controls cannot be bypassed.

Acceptance criteria:

1. Every bot message includes or is generated with configured AI disclosure.
2. Empty disclosure config is rejected.
3. Session token usage accumulates across turns.
4. Hitting token cap escalates gracefully without another LLM call.
5. Unit tests prove no bot response path bypasses disclosure injection.

### Story CBH-E4-S5: Implement Lead Capture State Machine and Contact Write-Back

As an admin, I want qualified chat visitors to become SignalLoop contacts so that inbound interest can enter existing follow-up workflows.

Screens: indirectly visible in Inbox and Contacts.

Backend touchpoints:

- `apps/api/app/domain/chatbot/lead_capture.py`
- existing contacts repository/API
- audit log

Acceptance criteria:

1. Purchase/demo/pricing intent or configured keywords can trigger lead capture.
2. Privacy notice and explicit consent occur before collecting PII.
3. Name and email or phone are collected.
4. Existing contacts are updated rather than duplicated.
5. New or updated contacts receive source channel, `chatbot-lead` tag, and intent.
6. Consent accept/decline events are audit logged.

---

## CBH-E5: Inbox and Human Handoff

### Outcome

Agents can work real-time escalations, see full context, respect WhatsApp/opt-out constraints, reply, resolve, reopen, and export threads.

### Story CBH-E5-S1: Implement Inbox Thread API

As an agent, I want APIs for thread list, detail, reply, resolve, and reopen so that the inbox UI can be reliable and secure.

Screens: CBH-S05, CBH-S06.

API:

- `GET /api/v1/chatbot/inbox/threads`
- `GET /api/v1/chatbot/inbox/threads/{thread_id}`
- `POST /api/v1/chatbot/inbox/threads/{thread_id}/reply`
- `PATCH /api/v1/chatbot/inbox/threads/{thread_id}/resolve`
- `PATCH /api/v1/chatbot/inbox/threads/{thread_id}/reopen`

Acceptance criteria:

1. List endpoint supports channel, status, and date filters.
2. List endpoint is cursor-paginated and sorted by last activity descending.
3. Detail endpoint returns ordered message history.
4. Reply endpoint changes status to agent-active and sends through original channel.
5. `chat_conversations.customer_last_message_at` is returned for WhatsApp threads and is updated on every inbound WhatsApp visitor message.
6. WhatsApp replies after 24 hours return a clear `whatsapp_window_expired` error.
7. The 24-hour enforcement is implemented inside `WhatsAppCloudAdapter.send_message()` using `customer_last_message_at`, so direct or alternate send paths cannot bypass the platform guard.
8. API-level reply validation mirrors the adapter check for clear UX errors, but the adapter remains the final enforcement boundary.
9. p95 list load and reply delivery match NFR-CB3 and NFR-CB4 in release testing.

### Story CBH-E5-S2: Implement Inbox SSE and Notification Events

As an agent, I want new escalations to appear in real time so that I do not need to refresh the inbox.

Screens: CBH-S05, CBH-S06.

API:

- `GET /api/v1/chatbot/inbox/events`

Acceptance criteria:

1. SSE emits new escalation, message appended, status changed, and WhatsApp window reopened events.
2. Frontend falls back to polling when SSE disconnects.
3. Sidebar escalation badge updates from events.
4. Toast notification appears for new escalation.
5. Reduced-motion setting disables flash animation while preserving visual state.

### Story CBH-E5-S3: Build Inbox Thread List UI

As an agent, I want a scannable thread list so that I can prioritize escalated and out-of-hours conversations.

Screens: CBH-S05.

Frontend touchpoints:

- `apps/web/src/features/chatbot/InboxPage.tsx`
- `apps/web/src/features/chatbot/components/ThreadRow.tsx`
- `apps/web/src/features/chatbot/hooks/useChatThreads.ts`

Acceptance criteria:

1. Thread list uses a 380px left panel on desktop.
2. Thread rows show channel icon, visitor, preview, time, status badge, and color accent.
3. Filters update the query without full page reload.
4. New escalation inserts at top with visual highlight.
5. Empty and loading states match the screen wireframe.

### Story CBH-E5-S4: Build Thread Detail, Reply Composer, and Compliance States

As an agent, I want full conversation context and a safe reply composer so that I can handle handoffs without violating platform constraints.

Screens: CBH-S06.

Frontend touchpoints:

- `apps/web/src/features/chatbot/ThreadDetailPage.tsx`
- `apps/web/src/features/chatbot/components/MessageBubble.tsx`
- `apps/web/src/features/chatbot/components/ReplyComposer.tsx`
- `apps/web/src/features/chatbot/components/WhatsAppWindowBanner.tsx`

Acceptance criteria:

1. Message history renders bot, visitor, and agent bubble variants.
2. Bot messages show AI disclosure.
3. Reply composer posts agent replies and optimistically appends on success.
4. WhatsApp expired state replaces the composer with a non-dismissable banner.
5. Opted-out state disables bot re-engagement controls and shows the opt-out notice.
6. Resolve and reopen actions update list and detail state.

### Story CBH-E5-S5: Implement Conversation Export

As an admin, I want to export chatbot conversations so that I can analyze data or satisfy compliance requests.

Screens: CBH-S06 action menu, optional Inbox bulk action.

API:

- `GET /api/v1/chatbot/inbox/threads/export`

Acceptance criteria:

1. Admin can export CSV or JSON by date range and channel.
2. Export includes message timestamps, sender role, text, bot confidence, and captured lead details.
3. Agent role receives 403.
4. Export is workspace-scoped.
5. Large exports stream or run as background job without API timeout.

---

## CBH-E6: Settings and Compliance Controls

### Outcome

Admins can tune bot behavior safely and manage opted-out visitors through explicit re-consent.

### Story CBH-E6-S1: Implement Bot Configuration API

As an admin, I want one config API for workspace and channel bot settings so that the settings screen and runtime use the same contract.

Screens: CBH-S08.

API:

- `GET /api/v1/chatbot/config`
- `PUT /api/v1/chatbot/config`
- channel-level config update through `/api/v1/chatbot/channels/{channel_id}`

Acceptance criteria:

1. API returns business hours, timezone, retention, token cap, privacy notice, privacy policy URL, re-index schedule, lead capture settings, and channel overrides.
2. AI disclosure cannot be empty.
3. Retention cannot be below 30 days.
4. Token cap must be positive and within configured system max.
5. Config changes are audit logged where compliance-relevant.

### Story CBH-E6-S2: Build Bot Settings Page

As an admin, I want inline bot settings with a sticky save bar so that I can configure behavior without losing context.

Screens: CBH-S08.

Frontend touchpoints:

- `apps/web/src/features/chatbot/BotSettingsPage.tsx`
- `apps/web/src/features/chatbot/hooks/useBotConfig.ts`

Acceptance criteria:

1. Page renders AI & Disclosure, Lead Capture, Business Hours, and Compliance sections.
2. Editing any field shows unsaved-changes bar.
3. Save submits only changed values or a validated config payload.
4. Discard resets fields to last saved state.
5. Inline validation covers disclosure, URL, retention, and numeric limits.

### Story CBH-E6-S3: Implement Opt-Out Enforcement and Admin API

As the system, I want opt-out keywords to immediately stop bot automation and create auditable records so that channel compliance is enforced.

Screens: CBH-S06, CBH-S09.

API:

- `GET /api/v1/chatbot/opt-outs`
- `DELETE /api/v1/chatbot/opt-outs/{opt_out_id}`

Acceptance criteria:

1. STOP/Unsubscribe/Cancel/Quit are detected across channels.
2. Active opt-out blocks all bot responses before RAG/LLM.
3. Opted-out threads remain visible in inbox.
4. Re-enable requires admin action and audit logging.
5. Optional re-opt-in invitation is sent at most once when enabled.

### Story CBH-E6-S4: Build Settings Opt-Outs Tab

As an admin, I want an Opt-outs tab in existing Settings so that I can manage bot re-enablement deliberately.

Screens: CBH-S09.

Frontend touchpoints:

- `apps/web/src/routes/_layout/settings.tsx`
- `apps/web/src/features/chatbot/OptOutsTab.tsx`

Acceptance criteria:

1. Opt-outs tab appears only for admins.
2. Table lists channel, visitor, opted-out time, opted-out actor, and action.
3. Re-enable opens explicit re-consent confirmation dialog.
4. Confirming calls the re-enable API and updates the table.
5. Empty state renders when no active opt-outs exist.

### Story CBH-E6-S5: Implement Conversation Retention Purge Job

As a workspace admin, I want conversation data retention enforced automatically so that visitor chat data does not live longer than configured.

Screens: CBH-S08 for retention configuration; no separate purge UI in MVP.

Backend touchpoints:

- `workspace_bot_config.retention_days`
- `chat_conversations`
- `chat_messages`
- captured lead/conversation export safeguards
- scheduled purge worker/job

Acceptance criteria:

1. A scheduled purge job runs nightly and evaluates each workspace's `retention_days` setting.
2. Records older than `retention_days` are soft-deleted or anonymized according to the existing SignalLoop deletion pattern.
3. Retention cannot be configured below 30 days and defaults to 90 days.
4. Purged conversations no longer appear in Inbox, Analytics drill-downs, or export results.
5. Aggregated analytics snapshots may remain only if they no longer expose message text or captured PII.
6. Purge actions are audit logged with workspace ID, cutoff timestamp, record counts, and job result.
7. Tests cover default retention, custom retention, minimum validation, cross-workspace isolation, and purge idempotency.

---

## CBH-E7: Analytics

### Outcome

Admins and agents can monitor chatbot performance using pre-aggregated workspace-scoped metrics.

### Story CBH-E7-S1: Implement Analytics Snapshot Job and API

As an admin, I want chatbot metrics to load quickly so that analytics can be reviewed without scanning raw conversations.

Screens: CBH-S07.

Backend touchpoints:

- analytics snapshot scheduler
- `analytics_snapshots`
- `GET /api/v1/chatbot/analytics`

Acceptance criteria:

1. Snapshot job runs every 15 minutes.
2. Snapshot data includes total conversations, messages, bot resolved, escalations, leads captured, opt-outs, and channel breakdown.
3. API supports configurable date range.
4. Results are workspace-scoped.
5. Agent role has read-only access; export remains admin-only if provided.

### Story CBH-E7-S2: Build Analytics Dashboard UI

As an admin or agent, I want summary cards, charts, and breakdowns so that I can identify channel and knowledge-base performance issues.

Screens: CBH-S07.

Frontend touchpoints:

- `apps/web/src/features/chatbot/AnalyticsPage.tsx`

Acceptance criteria:

1. Page shows date range picker, four stat cards, line chart, bar chart, and outcome table.
2. Date range changes refetch data without full reload.
3. Updated X min ago badge is visible.
4. No-data state renders without broken charts.
5. Component tests cover stat rendering and date-range refetch.

---

## CBH-E8: Release Hardening and Validation

### Outcome

The MVP satisfies release gates for channel connectivity, RAG quality, escalation reliability, lead capture, compliance, security, performance, and accessibility.

### Story CBH-E8-S1: Cross-Workspace Isolation Test Suite

As a platform owner, I want automated isolation tests so that ChatBot Hub never leaks data across workspaces.

Acceptance criteria:

1. Tests cover knowledge source list, vector retrieval, conversation threads, messages, opt-outs, analytics, and channel configs.
2. Every tested API rejects or filters another workspace's data.
3. Vector search returns zero chunks from other workspaces.
4. Tests are included in CI.

### Story CBH-E8-S2: Compliance Regression Suite

As a compliance owner, I want automated checks for disclosure, opt-out, WhatsApp window, privacy consent, and non-text fallback so that required controls cannot regress.

Acceptance criteria:

1. Every bot message path includes disclosure.
2. STOP immediately blocks further bot responses.
3. WhatsApp reply input/API blocks after the 24-hour window.
4. Lead capture does not collect PII before consent.
5. Non-text messages receive graceful fallback.

### Story CBH-E8-S3: Performance and Reliability Validation

As an engineering lead, I want release-gate performance tests so that ChatBot Hub meets the MVP NFRs under expected load.

Acceptance criteria:

1. Bot response p95 is less than or equal to 5 seconds over the agreed test set.
2. Agent reply p95 is less than or equal to 3 seconds.
3. Inbox initial list p95 is less than or equal to 3 seconds.
4. Indexing 50 pages plus 5 documents completes within 10 minutes p95.
5. Failed worker jobs retry and dead-letter after 3 attempts.

### Story CBH-E8-S4: Frontend Accessibility and Responsive Validation

As a user, I want ChatBot Hub screens to be keyboard-accessible and tablet-usable so that core workflows remain dependable.

Acceptance criteria:

1. All interactive controls are reachable by keyboard.
2. Sheets return focus to their trigger.
3. Status colors are paired with labels or icons.
4. Inbox tablet mode supports list-to-detail navigation.
5. Reduced-motion preference disables nonessential animation.

### Story CBH-E8-S5: End-to-End Demo Scenarios

As a product owner, I want repeatable E2E scenarios so that the MVP can be demonstrated with confidence.

Acceptance criteria:

1. Admin connects a mock/local channel and sees Connected Active.
2. Admin adds KB content, indexes it, and receives a cited Test Bot answer.
3. Visitor message produces grounded bot response.
4. Visitor asks for human; thread appears in Inbox through real-time update.
5. Agent replies and resolves.
6. Visitor requests demo; lead capture creates or updates Contact with `chatbot-lead`.
7. Visitor sends STOP; bot does not re-engage.

### Story CBH-E8-S6: MVP Release Gate Verification Matrix

As a product owner, I want each PRD release gate verified by a named test or manual protocol so that MVP readiness is objective.

Acceptance criteria:

1. Gate 1, two channels live: Facebook Messenger and WhatsApp Business are connected and process inbound messages end-to-end; Telegram is marked optional and cannot block MVP if Facebook and WhatsApp pass.
2. Gate 2, knowledge base functional: URL crawl, document upload, FAQ/free-form text, and structured Q&A sources all index and return queryable chunks.
3. Gate 3, no hallucination contract: 50 manual test queries against a reference knowledge base produce zero responses that assert facts absent from the retrieved sources; failures block release.
4. Gate 4, escalation reliable: 100% of conversations meeting escalation trigger criteria appear in Inbox within 30 seconds.
5. Gate 5, lead capture reliable: 100% of completed consented lead capture flows create or update a Contact within 60 seconds.
6. Gate 6, privacy consent enforced: 100% of lead capture flows present privacy notice before PII collection and record accept/decline audit events.
7. Gate 7, AI disclosure present: 100% of bot messages include or are generated with configured AI disclosure across Facebook, WhatsApp, and Telegram if enabled.
8. Gate 8, opt-out enforced: STOP halts bot responses within one message turn on WhatsApp and Facebook.
9. Gate 9, non-text handling: image, voice note, and document messages receive graceful fallback on all connected MVP channels.
10. Gate 10, webhook security: all webhook endpoints reject invalid signatures or tokens with HTTP 401 and process zero unsigned payloads.
11. Gate 11, cross-workspace isolation: automated tests confirm workspace A queries return zero workspace B knowledge, conversations, opt-outs, analytics, or channel configs.
12. Gate 12, performance: p95 bot response time is less than or equal to 5 seconds over a 200-request load test.
13. Gate 13, admin inbox functional: an agent can view, reply to, and resolve an escalated conversation end-to-end across connected MVP channels.
14. Gate 14, Telegram optional: release notes explicitly state Telegram status; failing Telegram tests do not block MVP if Facebook and WhatsApp release gates pass.
15. The release report names the test evidence, date run, result, and owner for each gate.

## Detailed PRD ID Traceability Matrix

| PRD ID | Primary story or stories |
|---|---|
| CH1 | CBH-E2-S1, CBH-E2-S2, CBH-E2-S4 |
| CH2 | CBH-E2-S1 |
| CH3 | CBH-E2-S2, CBH-E2-S3 |
| CH4 | CBH-E2-S1, CBH-E2-S4 |
| CH5 | CBH-E2-S1, CBH-E6-S1, CBH-E6-S2 |
| CH6 | CBH-E2-S4 |
| CH7 | CBH-E4-S3, CBH-E6-S1, CBH-E6-S2 |
| CH8 | CBH-E2-S3, CBH-E2-S5, CBH-E8-S3 |
| CH9 | CBH-E6-S1, CBH-E6-S2, CBH-E4-S2 |
| KB1 | CBH-E3-S1, CBH-E3-S5 |
| KB2 | CBH-E3-S1, CBH-E3-S2, CBH-E3-S5 |
| KB3 | CBH-E3-S1, CBH-E3-S2, CBH-E3-S5 |
| KB4 | CBH-E3-S1, CBH-E3-S5 |
| KB5 | CBH-E3-S1, CBH-E3-S5 |
| KB6 | CBH-E3-S3 |
| KB7 | CBH-E3-S4, CBH-E3-S5 |
| KB8 | CBH-E3-S4, CBH-E6-S1 |
| KB9 | CBH-E3-S1, CBH-E3-S5 |
| KB10 | CBH-E1-S1, CBH-E1-S2, CBH-E3-S3, CBH-E8-S1 |
| KB11 | CBH-E3-S3, CBH-E3-S4, CBH-E4-S2 |
| KB12 | CBH-E3-S5 |
| BOT1 | CBH-E4-S1 |
| BOT2 | CBH-E4-S1, CBH-E4-S4 |
| BOT3 | CBH-E4-S2 |
| BOT4 | CBH-E4-S2 |
| BOT5 | CBH-E4-S2, CBH-E8-S6 |
| BOT6 | CBH-E4-S1 |
| BOT7 | CBH-E4-S3 |
| BOT8 | CBH-E4-S3, CBH-E5-S2 |
| BOT9 | CBH-E4-S1, CBH-E2-S1 |
| BOT10 | CBH-E4-S2, CBH-E8-S3, CBH-E8-S6 |
| BOT11 | CBH-E4-S4, CBH-E6-S1, CBH-E6-S2, CBH-E8-S2 |
| BOT12 | CBH-E4-S1, CBH-E8-S2, CBH-E8-S6 |
| BOT13 | CBH-E4-S1, CBH-E6-S3 |
| LC1 | CBH-E4-S5, CBH-E6-S1, CBH-E6-S2 |
| LC2 | CBH-E4-S5 |
| LC3 | CBH-E4-S5, CBH-E8-S2, CBH-E8-S6 |
| LC4 | CBH-E4-S5, CBH-E8-S6 |
| LC5 | CBH-E4-S5 |
| LC6 | CBH-E4-S5 |
| LC7 | CBH-E4-S5, CBH-E8-S6 |
| HH1 | CBH-E5-S1, CBH-E5-S3 |
| HH2 | CBH-E5-S1, CBH-E5-S3 |
| HH3 | CBH-E5-S1, CBH-E5-S4 |
| HH4 | CBH-E5-S1, CBH-E5-S4 |
| HH5 | CBH-E4-S3, CBH-E5-S1, CBH-E5-S4 |
| HH6 | CBH-E5-S1, CBH-E5-S4 |
| HH7 | CBH-E5-S1, CBH-E5-S3 |
| HH8 | CBH-E4-S3, CBH-E5-S2 |
| HH9 | CBH-E5-S5 |
| OC1 | CBH-E6-S3, CBH-E8-S2, CBH-E8-S6 |
| OC2 | CBH-E5-S4, CBH-E6-S3 |
| OC3 | CBH-E6-S3 |
| OC4 | CBH-E6-S4 |
| AN1 | CBH-E7-S1, CBH-E7-S2 |
| AN2 | CBH-E7-S1 |
| AN3 | CBH-E4-S2, CBH-E7-S1 |
| AN4 | CBH-E7-S1, CBH-E8-S1 |
| WS1 | CBH-E2-S2, CBH-E2-S3, CBH-E8-S2, CBH-E8-S6 |
| WS2 | CBH-E2-S3 |
| WS3 | CBH-E2-S3, CBH-E2-S5, CBH-E8-S3 |
| WS4 | CBH-E2-S3, CBH-E2-S5 |
| WS5 | CBH-E2-S3, CBH-E2-S5 |

## Detailed NFR Traceability Matrix

| NFR ID | Primary story or stories |
|---|---|
| NFR-CB1 | CBH-E4-S2, CBH-E8-S3, CBH-E8-S6 |
| NFR-CB2 | CBH-E3-S2, CBH-E8-S3, CBH-E8-S6 |
| NFR-CB3 | CBH-E5-S1, CBH-E5-S3, CBH-E8-S3 |
| NFR-CB4 | CBH-E5-S1, CBH-E5-S4, CBH-E8-S3 |
| NFR-CB5 | CBH-E2-S3, CBH-E8-S3 |
| NFR-CB6 | CBH-E2-S3, CBH-E2-S5, CBH-E8-S3 |
| NFR-CB7 | CBH-E2-S3, CBH-E4-S2, CBH-E8-S3 |
| NFR-CB8 | CBH-E1-S1, CBH-E2-S1, CBH-E8-S2 |
| NFR-CB9 | CBH-E1-S1, CBH-E1-S2, CBH-E3-S3, CBH-E8-S1 |
| NFR-CB10 | CBH-E2-S2, CBH-E2-S3, CBH-E8-S2 |
| NFR-CB11 | CBH-E1-S3, CBH-E2-S1, CBH-E3-S1, CBH-E5-S1, CBH-E7-S1 |
| NFR-CB12 | CBH-E6-S1, CBH-E6-S2, CBH-E6-S5 |
| NFR-CB13 | CBH-E4-S1, CBH-E8-S3 |
| NFR-CB14 | CBH-E1-S1, CBH-E3-S3, CBH-E8-S3 |
| NFR-CB15 | CBH-E5-S1, CBH-E5-S4, CBH-E8-S2 |
| NFR-CB16 | CBH-E4-S4, CBH-E6-S1, CBH-E6-S2 |

## Implementation Order

Recommended order:

1. CBH-E1-S1 through CBH-E1-S3
2. CBH-E2-S1 through CBH-E2-S5
3. CBH-E3-S1 through CBH-E3-S5
4. CBH-E4-S1 through CBH-E4-S5
5. CBH-E5-S1 through CBH-E5-S5
6. CBH-E6-S1 through CBH-E6-S5
7. CBH-E7-S1 through CBH-E7-S2
8. CBH-E8-S1 through CBH-E8-S6

The first demonstrable vertical slice is:

```text
E1 foundation -> E3 KB/Test Bot -> E2 one mock channel -> E4 grounded response -> E5 inbox escalation
```

This proves the defining experience before the full channel matrix is complete.

## Story Readiness Checklist

Each implementation story should be considered ready when:

- PRD requirements are named.
- UX screen IDs are named where applicable.
- API contract or component target is named.
- Workspace isolation expectations are explicit.
- Role access is explicit.
- Loading, empty, error, and success states are included for UI stories.
- Unit/integration/E2E verification is identified.
