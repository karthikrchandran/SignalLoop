---
workflowType: prd
date: "2026-05-13"
revisedDate: "2026-05-13"
revisionNote: "Analyst review (Mary / bmad-agent-analyst): added AI disclosure requirement, WhatsApp 24-hour window constraint, privacy consent in lead capture, non-text message handling, business hours awareness, bot test/preview capability, opt-out/STOP handling, success metrics section, KB in-flight consistency, and conversation export."
inputDocuments:
  - _bmad-output/planning-artifacts/prd.md
  - _bmad-output/planning-artifacts/product-brief-SignalLoop.md
documentPurpose: "Phase 2 PRD — Shared Business Chatbot Brain for multi-channel inbound engagement"
primaryAudience:
  - product_manager
  - solution_architect
  - engineering_lead
  - qa_lead
---

# Product Requirements Document: ChatBot Hub — Shared Business Chatbot Brain

## 1. Product Summary

ChatBot Hub extends SignalLoop with a shared AI-powered chatbot engine that can be deployed simultaneously across multiple official business messaging channels — Facebook Page Messenger, WhatsApp Business, Telegram Bot, and LinkedIn (as an intent capture entry point). Every channel adapter shares the same knowledge brain, meaning a business configures their knowledge base once and all channel-facing bots answer consistently from that single source of truth.

Admins feed the brain by providing one or more of: a website URL to crawl, documents (PDF, DOCX, TXT) to ingest, free-form FAQ text entries, or structured Q&A pairs. The brain indexes this content and uses Retrieval-Augmented Generation (RAG) to answer inbound visitor questions accurately and grounded in the business's own content.

When the bot cannot answer, it gracefully escalates to a human agent and passes the conversation context. Captured leads (name, contact, intent) flow into the existing SignalLoop contact pool for downstream sequence and call follow-up.

---

## 2. Intended Audience for This PRD

- Product owner and product manager: scope, priorities, release gates
- Solution architect and engineering leads: channel adapter design, RAG pipeline, knowledge indexing
- Developers: implementable functional requirements per component
- QA: measurable acceptance targets per channel and knowledge source type
- SRE / platform owner: operational controls, webhook reliability, provider credentials model

---

## 3. MVP Goals

1. Enable a business to connect at least two official inbound messaging channels (Facebook Page Messenger and WhatsApp Business) behind a single shared AI brain.
2. Allow admins to build the bot's knowledge base from website URLs, uploaded documents, and manual FAQ entries — without writing code.
3. Answer inbound visitor questions accurately, citing the business's own content through RAG, with no hallucinated claims.
4. Capture visitor contact details (name, email or phone) and intent as a qualified lead record in the SignalLoop contact pool.
5. Escalate gracefully to a human agent when the bot cannot answer or when the visitor explicitly requests a human.
6. Provide admins with a unified conversation inbox showing all inbound chat threads across all channels.
7. Allow Telegram as an optional third channel at MVP launch.

---

## 4. MVP Scope

### In scope

- **Channel adapters** for:
  - Facebook Page Messenger (Meta Messenger Platform webhook)
  - WhatsApp Business Cloud API (Meta Cloud API webhook)
  - Telegram Bot API (long-polling or webhook)
  - LinkedIn (out-of-scope for real-time bot; in-scope as a lead capture link that routes to WhatsApp or a web landing page — see §4 Out of scope)
- **Knowledge base management UI**: admin can add, edit, and delete knowledge sources
- **Knowledge source types**:
  - Website URL crawl: admin provides one or more URLs; system crawls and indexes the page content (configurable crawl depth, up to 50 pages per source)
  - Document upload: PDF, DOCX, TXT — up to 20 MB per file
  - FAQ / free-form text: paste text blocks, Q&A pairs
  - Manual Q&A entry: structured question + answer pairs
- **RAG pipeline**: chunk, embed, and index all knowledge sources; retrieve relevant chunks at query time; generate grounded answers via LLM
- **Bot conversation engine**: greeting, knowledge-grounded answers, follow-up clarification questions, lead capture flow, escalation to human
- **Lead capture**: structured collection of visitor name + contact (email or phone) + intent during conversation; writes to SignalLoop contact pool
- **Human handoff**: when bot confidence is low or visitor requests human, the thread is flagged and appears in admin inbox with full context
- **Admin conversation inbox**: view all inbound threads across channels, see full message history, reply as human, resolve or re-open
- **Workspace channel credentials**: per-workspace storage of Facebook App credentials, WhatsApp Business phone number ID + token, Telegram Bot token — using existing `ProviderCredential` model
- **Bot configuration per channel**: toggle active/inactive per channel, custom bot name, custom greeting message, escalation message, and out-of-hours message
- **Bot persona**: admin-configurable bot display name (e.g., "Aria from Acme") and a short persona description used to shape the LLM's tone
- **AI identity disclosure**: all bot messages must include a disclosure that the respondent is an AI assistant — required by Meta platform policy and multiple regional regulations
- **Business hours configuration**: admin sets active hours per workspace (days + time range + timezone); escalations outside active hours trigger an out-of-hours auto-reply with a "we'll follow up when we're back" message
- **Non-text inbound message handling**: when a visitor sends an image, voice note, file, or other non-text media, the bot must respond with a graceful fallback message rather than silently dropping the message
- **Opt-out / STOP handling**: when a visitor sends "STOP", "Unsubscribe", or equivalent on any channel, the system must mark the contact as opted-out, cease all bot responses for that visitor, and record the opt-out event — required for WhatsApp Business platform compliance
- **Bot test / preview**: an admin-facing "Test Bot" panel where the admin can send test messages and see the bot's RAG responses in real time before the channel goes live
- **Knowledge base re-indexing**: manual re-index trigger + scheduled nightly re-index; in-flight conversation context is pinned to the current index version until the conversation session ends
- **Basic analytics**: total conversations, messages handled by bot, escalations, leads captured — per channel and aggregate
- **Conversation export**: admin can export conversation threads as CSV or JSON for a specified date range and channel, with PII fields included (requires admin-level permission)
- **Webhook security**: verified webhook signatures (Facebook hub.verify, Meta webhook signature, Telegram secret token)

### Out of scope for MVP

- LinkedIn real-time bot (LinkedIn Messaging API requires partnership approval — in Phase 3; MVP LinkedIn support is a link-to-WhatsApp or lead form redirect only)
- Instagram Direct Message bot (Phase 2+)
- Voice chatbot or audio responses within chat channels
- Multi-language bot responses (Phase 3)
- Multi-workspace / multi-tenant knowledge base isolation beyond workspace-level row separation
- Proactive outbound messaging via chat channels (this product is inbound-first; WhatsApp template broadcast messages are Phase 2)
- Native mobile app for admin inbox
- CRM sync beyond the existing SignalLoop contact pool
- A/B testing of bot responses
- Custom ML fine-tuning of bot models
- Automated appointment booking within chat
- Multi-agent assignment or internal agent-to-agent handoff routing
- WhatsApp Business API template message management (required for proactive messaging after the 24-hour window; Phase 2)

---

## 5. User Roles

| Role | Primary responsibility | What they need from ChatBot Hub |
|---|---|---|
| Workspace Admin | Own the bot setup, knowledge base, and channel connections | Connect channels, configure bot persona and business hours, manage knowledge sources, test bot, view analytics, export conversations |
| Support/Ops Agent | Monitor live conversations, handle escalations, reply as human | Unified inbox, escalation queue, conversation context, reply as human, resolve threads |
| Visitor (end user) | Ask questions, get help, optionally provide contact details | Fast, accurate answers; clear indication they are talking to an AI; friendly handoff when needed; respected opt-out |
| System | Index knowledge, route inbound messages, generate responses, capture leads | Reliable webhook ingestion, RAG retrieval, LLM generation, lead write-back, opt-out enforcement |

---

## 6. Core User Journeys

### Journey 1: Connect a channel and configure the bot

A workspace admin navigates to **Chatbot Hub → Channels**, selects Facebook Page Messenger, enters their Facebook App credentials and Page access token, and clicks Connect. The system verifies the webhook, activates the channel, and shows it as Live. The admin repeats for WhatsApp Business.

### Journey 2: Build the knowledge base

The admin navigates to **Chatbot Hub → Knowledge Base** and adds three sources:
1. Pastes their company website URL (`https://acme.com`) with crawl depth 2 — the system crawls and indexes ~30 pages.
2. Uploads `product-catalog.pdf` — the system extracts and chunks the text.
3. Types a manual Q&A entry: Q: "What are your business hours?" / A: "We're open 9 am – 6 pm SGT, Monday to Friday."

After adding all sources, the admin clicks **Re-index**. The system processes and confirms "Knowledge base is ready — 312 chunks indexed."

### Journey 3: A visitor asks a product question on Facebook Messenger

A visitor on the business's Facebook Page sends: "Hi, do you have a plan that covers 5 users?". The bot greets the visitor, retrieves the relevant pricing chunks from the knowledge base, and responds: "Yes! Our Team Plan covers up to 10 users for $49/month. You can find details at acme.com/pricing." The visitor replies "great, can I talk to someone?" — the bot acknowledges and flags the conversation for human agent pickup.

### Journey 4: Lead capture during a WhatsApp chat

A visitor sends a WhatsApp message: "I want to get a demo." The bot responds with its greeting, then initiates the lead capture flow: "I'd love to help arrange that! Could I get your name and email address so our team can follow up?" The visitor provides details. The bot creates a contact record in SignalLoop with tag `chatbot-lead` and intent `demo-request`, then confirms: "Thanks, you're all set. Someone from our team will reach out shortly!"

### Journey 5: Agent handles an escalation

An escalated conversation from Telegram appears in the admin inbox. The support agent can see the full message history, the reason for escalation ("visitor asked for human"), and the visitor's captured details. The agent replies directly from the inbox. The visitor receives the reply in their Telegram chat. The agent marks the conversation resolved.

### Journey 6: Admin monitors chatbot performance

The admin reviews the **Analytics** dashboard and sees: 240 conversations this week across Facebook and WhatsApp, bot handled 87% without escalation, 31 leads captured, 18 escalations. They see WhatsApp has the highest lead capture rate and decide to promote the WhatsApp number more prominently.

### Journey 7: Admin tests the bot before going live

After building the knowledge base and configuring the bot persona, the admin opens the **Test Bot** panel. They type "What is the refund policy?" and immediately see the bot's RAG-grounded response alongside the matched knowledge chunks. They notice the bot missed a nuance and add a Q&A entry for "full refund within 14 days", re-index, and test again. Satisfied, they activate the channel.

### Journey 8: Visitor sends a message outside business hours

A visitor sends a Facebook Messenger message at 11 PM. The bot is configured with business hours 9 AM – 6 PM SGT. The bot replies: "Hi! I'm Aria, an AI assistant. Our team is currently offline (we're back at 9 AM SGT). I'll do my best to help now, or you can leave a message and a human will follow up in the morning." If an escalation is triggered during off-hours, the thread is queued in the inbox with an `out-of-hours` badge and the agent sees it first thing in the morning.

### Journey 9: Visitor opts out

A visitor on WhatsApp replies "STOP". The system immediately marks the visitor as opted-out, stops all automated bot responses, and records the opt-out event in the audit log. If this visitor contacts the channel again, the system respects the opt-out and does not re-engage the bot unless the visitor explicitly re-opts-in.

---

## 7. Functional Requirements

### Channel management (CH1–CH9)

- **CH1**: The system must support connecting and disconnecting at least three channel types: Facebook Page Messenger, WhatsApp Business Cloud API, and Telegram Bot API.
- **CH2**: For each channel, the system must store the required credentials (tokens, phone number IDs, webhook secrets) in the existing encrypted `ProviderCredential` store, scoped to the workspace.
- **CH3**: The system must verify channel webhooks at connection time (Facebook `hub.verify` challenge, WhatsApp/Meta webhook signature, Telegram webhook confirmation) and reject connections that fail verification.
- **CH4**: The system must allow admins to toggle each channel active or inactive without deleting credentials.
- **CH5**: The system must allow a custom bot display name, greeting message, escalation message, and out-of-hours message to be configured per channel.
- **CH6**: The system must display the live/inactive/error status of each connected channel on the Channels page.
- **CH7**: The system must allow admins to configure business hours (days of week, start time, end time, and timezone) per workspace. When a conversation requires agent escalation outside configured hours, the bot must send the configured out-of-hours message and tag the thread as `out-of-hours` in the inbox.
- **CH8**: The system must handle channel provider API errors gracefully — if a channel delivery fails (e.g., Facebook API 5xx), the system must retry up to 3 times and dead-letter the outbound message with an operator-visible error rather than silently dropping it.
- **CH9**: The system must allow admins to configure a short bot persona description (up to 300 characters) that is injected into the LLM system prompt to shape the bot's tone and role (e.g., "You are Aria, a friendly customer support assistant for Acme Corp. You help customers with product questions and support requests.").

### Knowledge base management (KB1–KB10)

- **KB1**: The system must allow admins to add, edit, and delete knowledge sources from the Knowledge Base management UI.
- **KB2**: The system must support website URL crawl as a knowledge source type. When a URL is provided with a configured crawl depth (1–5, default 2), the system must crawl and extract visible text content from each discovered page up to the depth limit, capped at 50 pages per source.
- **KB3**: The system must support document upload as a knowledge source type, accepting PDF, DOCX, and TXT files up to 20 MB each.
- **KB4**: The system must support manual FAQ / free-form text as a knowledge source type, where the admin pastes or types text content.
- **KB5**: The system must support structured Q&A pair entry as a knowledge source type, where the admin enters discrete question and answer pairs.
- **KB6**: After ingestion, the system must chunk each knowledge source into segments of approximately 300–500 tokens with overlap, embed each chunk using a configured embedding model, and store embeddings in a vector index scoped to the workspace.
- **KB7**: The system must provide a manual **Re-index** trigger that re-processes all active knowledge sources and rebuilds the workspace's vector index.
- **KB8**: The system must run a scheduled nightly re-index (configurable time, default 02:00 workspace local time) to pick up any changes to website sources.
- **KB9**: The system must show the indexing status of each knowledge source (pending, indexing, ready, failed) and the total chunk count after successful indexing.
- **KB10**: The system must scope all vector index reads and writes strictly to the workspace; no cross-workspace knowledge leakage is permitted.
- **KB11**: When a re-index is triggered, in-flight conversation sessions must continue using the previous index version until the session ends; only new sessions started after re-indexing completes must use the new index. This prevents mid-conversation context shifts.
- **KB12**: The system must provide an admin **Test Bot** panel where the admin can submit test queries and receive the bot's RAG-generated response alongside the top retrieved knowledge chunks (chunk text, source name, similarity score) — for validation before the channel goes live.

### Bot conversation engine (BOT1–BOT13)

- **BOT1**: On receiving an inbound message from any connected channel, the system must route the message to the shared bot conversation engine.
- **BOT2**: The bot must greet first-time visitors with the configured greeting message or a default if none is set.
- **BOT3**: For each visitor message, the system must perform a semantic similarity search against the workspace's vector index, retrieve the top-k most relevant chunks (k = 5 default, configurable), and construct a prompt with retrieved context + conversation history.
- **BOT4**: The system must invoke the configured LLM (default: Groq Llama 3.1 8B) with the constructed prompt and return the generated response to the visitor via the channel.
- **BOT5**: The bot must include grounding instructions in the system prompt that instruct the LLM to answer only from retrieved context and to state "I don't have that information — let me connect you to someone who can help" when context is insufficient rather than hallucinating.
- **BOT6**: The system must maintain conversation history per visitor per channel session for context window construction (minimum 10 message turns retained).
- **BOT7**: The system must detect escalation triggers: (a) visitor explicitly requests a human ("talk to someone", "speak to an agent", "human please" and similar), (b) bot confidence indicator is below a configurable threshold (default: 0.4 cosine similarity on best retrieved chunk), or (c) the visitor has sent 3+ consecutive unanswered or low-confidence messages.
- **BOT8**: On escalation trigger, the bot must send the configured escalation message to the visitor, mark the thread as `escalated`, and surface it in the admin inbox for human pickup.
- **BOT9**: The system must support a bot-off mode per channel where all inbound messages are routed directly to the admin inbox without bot engagement.
- **BOT10**: Bot responses must be delivered to the visitor channel within 5 seconds at p95 under normal operating conditions.
- **BOT11**: Every bot message must include a disclosure that the responder is an AI (e.g., "I'm an AI assistant" or "This message was sent by an automated assistant") — this is required by Meta Messenger Platform policy, WhatsApp Business policy, and multiple regional AI transparency regulations. The disclosure wording is configurable but cannot be disabled.
- **BOT12**: When a visitor sends a non-text message (image, voice note, document, sticker, location share, or other unsupported media type), the bot must respond with a graceful fallback message (e.g., "I can only handle text messages for now. How can I help you in text?") rather than ignoring the message silently.
- **BOT13**: When the system receives a message from a visitor who is marked as opted-out, the bot must not send any automated response. The thread must be visible in the admin inbox with an `opted-out` status badge.

### Lead capture (LC1–LC7)

- **LC1**: The bot must initiate a lead capture flow when the visitor expresses purchase intent, requests a demo, asks for pricing, or completes a successful Q&A exchange beyond a configurable minimum turn threshold (default: 3 turns).
- **LC2**: The lead capture flow must collect at minimum: visitor's name and one contact channel (email address or phone number).
- **LC3**: Before collecting PII, the bot must present a brief privacy notice and obtain explicit consent (e.g., "To follow up, I'll need to store your contact details. Is that OK?"). If the visitor declines, LC5 applies. This is required for PDPA, GDPR, and PDPC compliance.
- **LC4**: Upon successful lead capture with consent, the system must create a Contact record in the SignalLoop contact pool with: channel source (e.g., `whatsapp`), tag `chatbot-lead`, and an intent field populated from the detected intent category.
- **LC5**: The system must not create duplicate contact records for the same phone number or email within a workspace; if the contact already exists, the system must update the contact's last-seen timestamp and append the new intent tag.
- **LC6**: Lead capture must be optional for the visitor; if the visitor declines to provide details or declines consent, the conversation continues normally and the bot does not re-prompt more than once per session.
- **LC7**: The consent event and the visitor's response (accepted/declined) must be recorded in the audit log per Contact record for compliance evidence.

### Human handoff and admin inbox (HH1–HH9)

- **HH1**: The admin inbox must display all inbound conversation threads across all connected channels, sorted by last activity (most recent first).
- **HH2**: Each thread in the inbox must show: channel icon, visitor identifier (name if captured, otherwise channel handle), last message preview, time of last message, and status (bot-active, escalated, agent-active, resolved, out-of-hours, opted-out).
- **HH3**: When an agent opens an escalated thread, the system must show the full message history including bot turns and visitor turns.
- **HH4**: The agent must be able to type and send a reply from the inbox; the reply must be delivered to the visitor via the originating channel within 3 seconds at p95.
- **HH5**: When an agent sends a reply, the thread status must change to `agent-active` and the bot must not send further automated responses for that thread until the agent marks it resolved or explicitly re-enables bot.
- **HH6**: The agent must be able to mark a thread as resolved; resolved threads move to the Resolved tab and are no longer highlighted in the main queue.
- **HH7**: The inbox must support filtering by channel, status (escalated, bot-active, agent-active, resolved, out-of-hours, opted-out), and date range.
- **HH8**: The system must send an in-app notification (and optionally email notification) to agents when a new escalation arrives.
- **HH9**: The admin must be able to export conversation threads (single thread or bulk by date range and channel) as CSV or JSON from the inbox. The export must include: message timestamps, sender role (bot/agent/visitor), message text, and captured lead details. Export is restricted to users with admin role.

### Opt-out and compliance (OC1–OC4)

- **OC1**: When a visitor sends an opt-out keyword ("STOP", "Unsubscribe", "Cancel", "Quit", or locale equivalents as required by channel platform policy) on any channel, the system must immediately cease all automated bot responses for that visitor on that channel, mark the visitor as `opted-out` on that channel, and record the opt-out event with timestamp in the audit log.
- **OC2**: An opted-out visitor's thread must remain visible in the admin inbox with an `opted-out` status badge; human agents may still reply manually if the visitor initiates contact again.
- **OC3**: If an opted-out visitor sends a new message (re-initiating contact), the system must not re-engage the bot automatically. The system must surface the thread in the inbox for human agent review. The bot may send a single re-opt-in invitation if the admin has enabled this setting.
- **OC4**: The system must expose an opt-out management view in admin settings where admins can view all opted-out visitors per channel and manually re-enable bot engagement for a visitor only after confirming the visitor has explicitly re-consented.

### Analytics (AN1–AN4)

- **AN1**: The system must provide a per-workspace analytics dashboard showing: total conversations, total messages, bot-handled rate (% of conversations resolved without agent), escalation count, leads captured, and breakdown by channel — for configurable date ranges.
- **AN2**: Analytics data must be updated at least every 15 minutes.
- **AN3**: The system must record per-conversation metadata: channel, start time, end time, turn count, outcome (bot-resolved, escalated, lead-captured), and bot confidence scores per turn.
- **AN4**: Analytics must be scoped strictly to the workspace; cross-workspace aggregation is not permitted.

### Webhook security and reliability (WS1–WS5)

- **WS1**: All inbound webhook endpoints must validate the channel provider's signature or verification token before processing the payload; payloads that fail signature verification must be rejected with HTTP 401 and logged.
- **WS2**: Webhook processing must be asynchronous — the system must acknowledge the provider's POST within 5 seconds (return HTTP 200) and process the message in a background worker.
- **WS3**: Failed message processing (LLM timeout, index error, channel delivery error) must be retried with exponential backoff (up to 3 attempts) and dead-lettered for operator review after all retries are exhausted.
- **WS4**: The system must log all inbound webhook events (channel, visitor ID, message ID, timestamp, processing outcome) in the audit log.
- **WS5**: Duplicate inbound messages (same message ID from a provider) must be de-duplicated; the system must not send duplicate bot responses.

---

## 8. Non-Functional Requirements

### Performance

- **NFR-CB1**: Bot response must be delivered to the visitor within 5 seconds at p95 (end-to-end from webhook receipt to channel delivery).
- **NFR-CB2**: Knowledge base re-indexing of up to 50 crawled pages + 5 uploaded documents must complete within 10 minutes at p95.
- **NFR-CB3**: Admin inbox must load (initial thread list) within 3 seconds at p95.
- **NFR-CB4**: Agent reply delivery to visitor must complete within 3 seconds at p95.

### Reliability

- **NFR-CB5**: The bot webhook ingestion pipeline must achieve 99.9% monthly availability.
- **NFR-CB6**: Inbound messages must not be silently dropped; every inbound message that passes webhook verification must result in either a bot response, an escalation, or a dead-letter record visible to operators.
- **NFR-CB7**: After LLM provider recovery, queued message processing must resume within 5 minutes.

### Security

- **NFR-CB8**: All channel API tokens, webhook secrets, and LLM API keys must be encrypted at rest using the same `ProviderCredential` encryption mechanism used by SignalLoop today.
- **NFR-CB9**: Vector index data and conversation history must be partitioned by workspace; no cross-workspace query is permitted at any layer.
- **NFR-CB10**: All inbound webhook requests must be verified using the channel provider's official signature scheme before any payload content is processed.
- **NFR-CB11**: Admin inbox access and knowledge base management must be restricted to users with the workspace admin or agent role.
- **NFR-CB12**: Visitor chat data (message history, captured PII) must be retained for a configurable duration (default: 90 days, minimum: 30 days) and must be purgeable on request for compliance.

### WhatsApp

- **NFR-CB15**: The system must record the `customer_last_message_at` timestamp per WhatsApp conversation. Agent outbound sends must be gated against this timestamp: if >24 hours have elapsed since the customer's last message, the reply input is disabled and the agent is shown: *"WhatsApp 24-hour messaging window has expired. The visitor must message first to reopen the conversation."*

### Cost Control

- **NFR-CB16**: LLM token consumption per conversation session must be capped at a configurable limit (default: 4,000 tokens) to prevent runaway cost. Sessions that hit the limit must receive a graceful bot message directing the visitor to escalate to a human agent.

### Scalability

- **NFR-CB13**: The architecture must support at least 500 concurrent inbound conversations across all channels for a single workspace in Phase 2 without architectural changes.
- **NFR-CB14**: The knowledge base pipeline must support up to 100,000 chunks per workspace vector index at MVP.

---

## 9. Technical Design Notes

> These are architectural guidance notes for the engineering team; they are not implementation mandates. The architect and engineering leads own the final design decisions.

### Channel adapter pattern

Each channel (Facebook, WhatsApp, Telegram) gets its own adapter class implementing a common `ChatChannelAdapter` interface with methods:
- `verify_webhook(request) → bool`
- `parse_inbound_event(payload) → InboundMessage`
- `send_message(conversation_id, text) → DeliveryReceipt`
- `normalize_visitor_id(raw_id) → str`

This extends the existing `NotificationProviderAdapter` pattern in `apps/api/app/infrastructure/providers/`.

### RAG pipeline components

| Component | Responsibility | Suggested technology |
|---|---|---|
| Crawler | Fetch and extract text from website URLs | **`httpx` + `BeautifulSoup4`** (MVP); Playwright/Crawl4AI behind feature flag post-MVP for JS-rendered sites |
| Document parser | Extract text from PDF/DOCX/TXT | `pypdf2`, `python-docx` |
| Chunker | Split text into 300–500 token segments with overlap | `langchain.text_splitter` or custom |
| Embedder | Generate vector embeddings per chunk | **`nomic-embed-text` via Ollama** (zero token cost; 768-dim vectors; Ollama already in infra) |
| Vector store | Store and query embeddings by workspace | **`pgvector`** on existing Postgres (`pgvector/pgvector:pg17` image in compose) |
| Retriever | Top-k semantic similarity search at query time | `pgvector` cosine similarity |
| Generator | Produce grounded response from context + history | Groq Llama 3.1 8B (existing integration) |

**MVP technology decisions (resolved):** `httpx` + `BeautifulSoup4` for crawling avoids a Chromium system dependency; `nomic-embed-text` via Ollama matches existing infra with zero per-token cost; `pgvector` confirmed — Epic 1 setup task is to change `db` image in `compose.yml` from `postgres:17` to `pgvector/pgvector:pg17` and add `CREATE EXTENSION IF NOT EXISTS vector;` to the first Alembic migration.

### Conversation state storage

Per-visitor conversation sessions are stored in the existing Redis instance:
- Key: `chat:session:{workspace_id}:{channel}:{visitor_id}`
- Value: JSON array of last N message turns (default: 10)
- TTL: 24 hours (configurable)

### Worker model

A new `chat_worker.py` (sibling to `call_worker.py`) consumes inbound messages from a Redis queue, runs the RAG + LLM pipeline, and dispatches channel send calls — consistent with the existing async worker architecture.

### Lead capture state machine

```
GREETING → OPEN_CONVERSATION → [intent_detected] → PRIVACY_NOTICE_PROMPT
→ [consent_given]  → LEAD_CAPTURE_PROMPT → [details_provided] → LEAD_CREATED → CONFIRM
→ [consent_declined] → CONTINUE_CONVERSATION
→ [details_declined] → CONTINUE_CONVERSATION
```

### WhatsApp 24-hour messaging window constraint

WhatsApp Business Cloud API enforces a **24-hour customer service window**: once a customer sends a message, the business can reply freely for 24 hours. After 24 hours with no new customer message, the business can **only** send pre-approved WhatsApp Message Templates (not free-form text). This has two implications:

1. **Agent replies in the inbox**: If an agent tries to reply to a thread where the customer's last message was >24 hours ago, the send will fail with a WhatsApp API error. The system must detect this condition and warn the agent: "This conversation window has expired. You can only re-engage using an approved template message."
2. **Re-engagement**: Phase 2 proactive messaging must use approved templates. For MVP, no proactive re-engagement is required, but the system must surface the window-expired state clearly in the inbox.

The `chat_worker.py` must store the `customer_last_message_at` timestamp per WhatsApp thread and gate agent outbound sends against it.

---

## 10. Release Gates (MVP)

The following conditions must all be met before production release of ChatBot Hub MVP:

1. **Two channels live**: Facebook Page Messenger and WhatsApp Business successfully connected and processing inbound messages end-to-end.
2. **Knowledge base functional**: Website URL crawl, document upload, and FAQ text entry all produce indexed and queryable knowledge with RAG answers grounded in the provided content.
3. **No hallucination contract**: 50 manual test queries against a reference knowledge base produce zero responses that assert facts not present in the knowledge sources.
4. **Escalation reliable**: 100% of conversations meeting escalation trigger criteria surface in admin inbox within 30 seconds.
5. **Lead capture reliable**: 100% of completed lead capture flows (with consent) produce a Contact record in the SignalLoop contact pool within 60 seconds.
6. **Privacy consent enforced**: 100% of lead capture flows present the privacy notice before collecting PII; consent/decline events are recorded in the audit log.
7. **AI disclosure present**: 100% of bot messages include the configured AI disclosure text — verified in regression testing across all channels.
8. **Opt-out enforced**: Sending "STOP" immediately halts all bot responses for that visitor within 1 message turn — verified on WhatsApp and Facebook channels.
9. **Non-text handling**: Bot returns graceful fallback for image, voice note, and document messages — verified on all connected channels.
10. **Webhook security**: All webhook endpoints reject payloads with invalid signatures with HTTP 401; zero unsigned payloads processed in regression testing.
11. **Cross-workspace isolation**: Automated test confirms that a query in workspace A returns zero results from workspace B's knowledge index.
12. **Performance**: p95 bot response time ≤ 5 seconds measured over 200-request load test.
13. **Admin inbox functional**: Agent can view, reply to, and resolve an escalated conversation end-to-end across all connected channels.
14. **Telegram optional**: Telegram may be excluded from MVP release if integration is not stable, without blocking the Facebook + WhatsApp release.

---

## 11. Success Metrics (Post-Launch)

These metrics define what "success" looks like at 30, 60, and 90 days post-launch. They are not release gates but are the KPIs the product team tracks to validate product-market fit and reliability.

| Metric | Target at 30 days | Target at 90 days | Notes |
|---|---|---|---|
| Bot containment rate | ≥ 70% of conversations resolved without agent escalation | ≥ 80% | Indicates knowledge base quality |
| Lead capture conversion rate | ≥ 15% of conversations result in a captured lead | ≥ 20% | Validates chatbot as a lead gen channel |
| Median first response time (bot) | ≤ 3 seconds | ≤ 3 seconds | UX signal — visitors expect near-instant response |
| Escalation response time (agent) | ≤ 2 hours during business hours | ≤ 1 hour | SLA for human pickup of escalated threads |
| Opt-out rate | ≤ 5% of WhatsApp conversations | ≤ 3% | High opt-out signals poor relevance or intrusiveness |
| Knowledge base coverage score | Admins can answer ≥ 80% of a test query set from their KB | ≥ 90% | Tracked via Test Bot panel queries |
| Channel uptime | ≥ 99.9% webhook availability per channel | ≥ 99.9% | Measured by provider webhook delivery success |
| Channels connected per workspace | ≥ 2 channels connected within 7 days of account activation | ≥ 2 | Onboarding health signal |

---

## 12. Open Questions

> ✅ = Decided and applied to PRD. ⚠️ = Requires business/owner confirmation before the indicated Epic kickoff.

| # | Question | Decision / Status | Owner | Verify by |
|---|---|---|---|---|
| OQ1 | Embedding model? | ✅ **`nomic-embed-text` via Ollama** — zero token cost, fits existing infra. Applied to Technical Design Notes. | Architect | — |
| OQ2 | `pgvector` available on Postgres? | ✅ **Resolved: switch `db` service image in `compose.yml` from `postgres:17` to `pgvector/pgvector:pg17`** as part of Epic 1 setup. This is a one-line change. `CREATE EXTENSION vector;` in the first Alembic migration activates it. No Chroma fallback needed. | Architect / SRE | ✅ Resolved — Epic 1 task |
| OQ3 | Verified Meta Business account + approved WhatsApp Business number? | ⚠️ **Owner action required.** Business owner to complete Meta Business Verification and obtain an approved WhatsApp Business phone number before Epic 2 kickoff. Template approval takes 2–7 business days. | Product / Admin | ⚠️ Owner to action before Epic 2 kickoff |
| OQ4 | Conversation retention period — 90 days OK for PDPA/GDPR? | ✅ **90 days default, configurable down to 30 days per workspace.** Applied to NFR-CB12. | Product / Legal | — |
| OQ5 | Escalation notification — which email, or use existing system? | ✅ **Use existing SignalLoop notification system.** Workspace admin email receives alert. Epic 3 story to include last message + trigger reason in notification. | Product | — |
| OQ6 | LinkedIn MVP CTA — WhatsApp deep link or web form? | ✅ **WhatsApp deep link** (`wa.me/<number>?text=Hi`). Zero build cost; drives volume to already-built WhatsApp channel. | Product | — |
| OQ7 | Headless Chromium available for Crawl4AI/Playwright? | ✅ **`httpx` + `BeautifulSoup4` for MVP** (no Chromium dependency). Playwright/Crawl4AI post-MVP behind feature flag. Applied to Technical Design Notes. | Architect | — |
| OQ8 | WhatsApp message templates approved for re-engagement? | ⚠️ **Owner action required.** System surfaces window-expired state only (NFR-CB15); no template send in MVP. Business owner must register with Meta and submit at least one re-engagement template before launch. | Product / Admin | ⚠️ Owner to action before launch |
| OQ9 | Privacy notice wording — who owns it, link or full text? | ✅ **Generic wording adopted:** *"By sharing your details, you confirm you have read and agree to our [Privacy Policy]. We will use your information only to respond to your enquiry."* Privacy policy URL is workspace-configurable (admin settings). Legal review recommended before go-live but wording is unblocking for development. | Product / Legal | ⚠️ Legal review recommended before launch |
| OQ10 | AI disclosure wording — customise? Legal review needed? | ✅ **Default: *"I'm an AI assistant."* Customisable per workspace; minimum 50 characters; non-empty enforced.** Custom wording is workspace admin's responsibility to legal-review. | Product / Legal | — |

---

## 13. Phased Roadmap (Post-MVP)

| Phase | Capabilities |
|---|---|
| **MVP** | Facebook Messenger + WhatsApp Business + Telegram (optional); RAG knowledge base; lead capture; human handoff; admin inbox; basic analytics |
| **Phase 2** | Instagram Direct Message bot; richer analytics and conversation export; proactive re-engagement messages via WhatsApp Business broadcast |
| **Phase 3** | LinkedIn real-time bot (pending API access); multi-language response support; appointment booking integration; CRM sync (HubSpot, Salesforce) |
| **Phase 4** | Fine-tuned brand voice model; advanced sentiment and intent classification; automated A/B testing of bot response styles |
