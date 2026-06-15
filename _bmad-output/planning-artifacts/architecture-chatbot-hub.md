---
stepsCompleted: [1, 2, 3, 4, 5, 6, 7]
workflowType: architecture
project_name: SignalLoop — ChatBot Hub
user_name: K.Ramachandran
date: "2026-05-13"
inputDocuments:
  - _bmad-output/planning-artifacts/prd-chatbot-hub.md
  - _bmad-output/planning-artifacts/architecture.md
  - compose.yml
  - apps/api/app/infrastructure/providers/
---

# Architecture Decision Document: ChatBot Hub — Shared Business Chatbot Brain

_This document builds the ChatBot Hub extension architecture on top of the existing SignalLoop system. All decisions are grounded in the finalised ChatBot Hub PRD (v2026-05-13) and the existing SignalLoop MVP architecture._

---

## 1. Architecture Goal

ChatBot Hub extends SignalLoop Phase 1 (email sequences + AI voice calling) with a shared inbound AI chatbot brain deployable across multiple messaging channels simultaneously. A single workspace configures its knowledge base once; all channel-facing bots answer consistently from that shared source of truth.

The architecture must:

1. Extend — not replace — the existing SignalLoop stack (FastAPI, PostgreSQL, Redis, Groq, React+TypeScript).
2. Add a RAG pipeline (crawl → chunk → embed → store → retrieve → generate) that is workspace-isolated and cost-controlled.
3. Support at least three real-time channel adapters (Facebook Messenger, WhatsApp Business, Telegram) through a common interface.
4. Integrate with the existing `ProviderCredential` model, notification system, and contact pool.
5. Deliver ≤5 s p95 end-to-end bot response latency.
6. Be runnable in the existing `compose.yml`-based development environment with a single additional service change (pgvector image swap).

### Architecture Principles (inherited from SignalLoop + ChatBot Hub additions)

1. **Extend existing patterns, don't reinvent.** Channel adapters follow the existing `NotificationProviderAdapter` pattern. Workers follow the existing `call_worker.py` / `sequence_worker.py` pattern. Credentials follow the existing `ProviderCredential` model.
2. **Workspace isolation is non-negotiable.** Every vector query, conversation session, and lead write is scoped to `workspace_id`. There is no shared index, no cross-tenant reads.
3. **Async-first for webhook processing.** HTTP 200 back to provider within 5 s; all heavy processing (RAG, LLM, channel send) happens in `chat_worker.py`.
4. **Exactly-once inbound semantics.** Inbound message deduplication by `(channel, provider_message_id)` before queuing.
5. **Graceful degradation over silent failures.** Every failure path (LLM timeout, index error, channel delivery failure) produces a visible record (dead-letter log, operator alert) not a silent drop.
6. **Cost control by design.** Token cap per session (default 4,000 tokens). Embedding via Ollama (zero per-token cost). Chunked retrieval limits LLM context size.
7. **Privacy by design.** PII (conversation history, captured leads) is workspace-partitioned, retention-configurable, and purgeable on request.

---

## 2. Technology Stack Decisions

> All decisions below were made collaboratively in the PRD party mode and open question resolution sessions. The stack is additive — all new components integrate with the existing SignalLoop stack.

### Existing Stack (unchanged)

| Layer | Technology | Version |
|---|---|---|
| Backend API | FastAPI (Python) | existing |
| Database | PostgreSQL | 17 → `pgvector/pgvector:pg17` (one-line compose swap) |
| Cache / queue | Redis | 7 |
| LLM | Groq Llama 3.1 8B | existing API key |
| Frontend | React + TypeScript + Vite | existing |
| Worker pattern | Background async workers (arq/custom) | existing |
| Credentials store | `ProviderCredential` (encrypted at rest) | existing |
| Notification system | Existing SignalLoop notification system | existing |

### New Components (ChatBot Hub)

| Component | Technology | Decision rationale |
|---|---|---|
| Vector store | `pgvector` on PostgreSQL 17 | Reuses existing Postgres; no new service; workspace isolation via `workspace_id` column; cosine similarity natively supported |
| Embedder | `nomic-embed-text` via Ollama | Already in infra; 768-dim vectors; zero per-token cost; offline-capable |
| Crawler | `httpx` + `BeautifulSoup4` | No Chromium dependency for MVP; sufficient for static/SSR sites; Playwright/Crawl4AI available post-MVP behind feature flag |
| Document parser | `pypdf2`, `python-docx` | Standard Python libraries; no external service dependency |
| Chunker | `langchain.text_splitter` (RecursiveCharacterTextSplitter) | Battle-tested; supports overlap; token-aware |
| Chat worker | `chat_worker.py` (new, sibling to `call_worker.py`) | Consistent with existing worker architecture |
| Session storage | Redis (existing) | Key: `chat:session:{workspace_id}:{channel}:{visitor_id}`; TTL: 24 h |

### Compose Change Required (Epic 1 Task)

```yaml
# compose.yml — change db service image:
# Before:  image: postgres:17
# After:   image: pgvector/pgvector:pg17
```

First Alembic migration must include: `CREATE EXTENSION IF NOT EXISTS vector;`

---

## 3. Logical System Components

### 3.1 Channel Adapter Layer

**Pattern:** Each channel gets its own adapter class implementing `ChatChannelAdapter`, which extends the existing `NotificationProviderAdapter` ABC.

**Location:** `apps/api/app/infrastructure/providers/chat/`

```
apps/api/app/infrastructure/providers/chat/
├── base.py                  # ChatChannelAdapter ABC
├── facebook_messenger.py    # FacebookMessengerAdapter
├── whatsapp_cloud.py        # WhatsAppCloudAdapter
├── telegram_bot.py          # TelegramBotAdapter
└── registry.py              # channel_type → adapter class map
```

**`ChatChannelAdapter` interface:**

```python
class ChatChannelAdapter(ABC):
    @abstractmethod
    def verify_webhook(self, request: Request) -> bool: ...

    @abstractmethod
    def parse_inbound_event(self, payload: dict) -> InboundMessage | None: ...

    @abstractmethod
    async def send_message(self, conversation_id: str, text: str) -> DeliveryReceipt: ...

    @abstractmethod
    def normalize_visitor_id(self, raw_id: str) -> str: ...

    @abstractmethod
    def is_opt_out_message(self, text: str) -> bool: ...

    @abstractmethod
    def is_non_text_message(self, payload: dict) -> bool: ...
```

**`InboundMessage` schema:**

```python
@dataclass
class InboundMessage:
    workspace_id: UUID
    channel: ChannelType          # facebook | whatsapp | telegram
    provider_message_id: str      # for deduplication
    visitor_id: str               # normalized visitor identifier
    text: str | None              # None for non-text messages
    is_non_text: bool
    received_at: datetime
    raw_payload: dict             # preserved for audit log
```

**Webhook endpoints (FastAPI routers):**

```
POST /webhooks/facebook/{workspace_id}
GET  /webhooks/facebook/{workspace_id}     # hub.verify challenge
POST /webhooks/whatsapp/{workspace_id}
GET  /webhooks/whatsapp/{workspace_id}     # Meta verify challenge
POST /webhooks/telegram/{workspace_id}     # secret token header
```

All endpoints: validate signature → acknowledge HTTP 200 → push to Redis queue → return. Processing never happens synchronously in the webhook handler.

### 3.2 Inbound Message Queue

**Technology:** Redis list (LPUSH / BRPOP)

**Queue key:** `chatbot:inbound:{workspace_id}`

**Message schema:**

```json
{
  "workspace_id": "uuid",
  "channel": "facebook|whatsapp|telegram",
  "provider_message_id": "string",
  "visitor_id": "string",
  "text": "string|null",
  "is_non_text": false,
  "received_at": "ISO8601",
  "raw_payload": {}
}
```

**Deduplication:** Redis SET `chatbot:dedup:{workspace_id}:{channel}:{provider_message_id}` with 24 h TTL. If key exists on inbound, discard and return HTTP 200 immediately.

### 3.3 Chat Worker (`chat_worker.py`)

**Location:** `apps/workers/chat_worker.py`

**Responsibilities:**

1. BRPOP from `chatbot:inbound:{workspace_id}`
2. Load conversation session from Redis (`chat:session:…`)
3. Check opt-out registry — if opted-out, skip bot, surface in inbox
4. Check non-text — send graceful fallback message if `is_non_text`
5. Check bot-off mode for channel — if off, route to inbox without bot
6. Run RAG pipeline (retrieve → prompt construction → LLM generation)
7. Apply token cap check (NFR-CB16: 4,000 tokens default)
8. Send response via channel adapter
9. Update conversation session in Redis
10. Evaluate escalation triggers (BOT7)
11. If escalation triggered: update thread status, notify inbox
12. Evaluate lead capture triggers (LC1)
13. On failure: exponential backoff retry × 3, then dead-letter to `chatbot:deadletter:{workspace_id}`

**Error recovery:** Dead-lettered items are visible in the operator admin panel via a new `/admin/chatbot/dead-letters` endpoint.

### 3.4 RAG Pipeline

```
KnowledgeSource (DB)
    │
    ▼
[Ingestion Worker: knowledge_indexing_worker.py]
    │
    ├── URL source → httpx + BeautifulSoup4 → text extraction
    ├── Document source → pypdf2 / python-docx → text extraction
    ├── FAQ/Q&A source → raw text
    │
    ▼
[Chunker: RecursiveCharacterTextSplitter]
    chunk_size=400 tokens, chunk_overlap=50 tokens
    │
    ▼
[Embedder: nomic-embed-text via Ollama HTTP API]
    POST http://ollama:11434/api/embeddings
    model: nomic-embed-text
    → 768-dim float vectors
    │
    ▼
[Vector Store: pgvector table knowledge_chunks]
    INSERT with workspace_id, source_id, chunk_text, embedding
    │
    ▼
[At query time: Retriever]
    SELECT ... ORDER BY embedding <=> query_embedding LIMIT 5
    WHERE workspace_id = $1 AND index_version = $2
```

**Index versioning:** Each re-index run generates a new `index_version` UUID. Existing conversation sessions store their `pinned_index_version`; new sessions use `current_index_version`. Old chunks are soft-deleted (not immediately purged) until no active sessions reference that version.

### 3.5 Bot Conversation Engine

**Location:** `apps/api/app/domain/chatbot/` (domain logic, called by chat_worker.py)

```
apps/api/app/domain/chatbot/
├── engine.py              # ConversationEngine: orchestrates RAG + LLM + state
├── prompts.py             # System prompt templates (bot persona, grounding, disclosure)
├── escalation.py          # EscalationDetector
├── lead_capture.py        # LeadCaptureStateMachine
├── opt_out.py             # OptOutRegistry (reads/writes DB)
└── token_counter.py       # TokenBudgetTracker (per session)
```

**System prompt construction (per request):**

```
[SYSTEM]
{bot_persona_description}  ← from BotConfig (BOT9/CH9)
You are an AI assistant. You must always identify yourself as an AI (disclosure: "{ai_disclosure_text}").
Answer only from the provided context. If the context does not contain the answer, say:
"I don't have that information — let me connect you to someone who can help."
Do not invent or extrapolate facts.

[CONTEXT]
{top_k retrieved chunks, each with source name}

[CONVERSATION HISTORY]
{last 10 turns from Redis session}

[USER]
{current visitor message}
```

**Token budget tracking:** After each LLM call, `token_counter.py` accumulates input + output tokens. When `session_token_total >= token_cap`, `engine.py` sends the cap-exceeded fallback message and sets session state to `TOKEN_LIMIT_REACHED` (stops further LLM calls; bot routes to escalation).

### 3.6 Admin API (new endpoints)

All new endpoints are added to the existing FastAPI application under `/api/v1/chatbot/`:

```
# Channel management
GET    /api/v1/chatbot/channels
POST   /api/v1/chatbot/channels
GET    /api/v1/chatbot/channels/{channel_id}
PUT    /api/v1/chatbot/channels/{channel_id}
DELETE /api/v1/chatbot/channels/{channel_id}
PATCH  /api/v1/chatbot/channels/{channel_id}/toggle

# Knowledge base
GET    /api/v1/chatbot/knowledge-sources
POST   /api/v1/chatbot/knowledge-sources
PUT    /api/v1/chatbot/knowledge-sources/{source_id}
DELETE /api/v1/chatbot/knowledge-sources/{source_id}
POST   /api/v1/chatbot/knowledge-sources/reindex
GET    /api/v1/chatbot/knowledge-sources/{source_id}/status

# Test bot
POST   /api/v1/chatbot/test                   # returns answer + top chunks

# Inbox
GET    /api/v1/chatbot/inbox/threads
GET    /api/v1/chatbot/inbox/threads/{thread_id}
POST   /api/v1/chatbot/inbox/threads/{thread_id}/reply
PATCH  /api/v1/chatbot/inbox/threads/{thread_id}/resolve
PATCH  /api/v1/chatbot/inbox/threads/{thread_id}/reopen
GET    /api/v1/chatbot/inbox/threads/export    # CSV/JSON download

# Opt-out management
GET    /api/v1/chatbot/opt-outs
DELETE /api/v1/chatbot/opt-outs/{opt_out_id}   # admin re-enable (with audit)

# Analytics
GET    /api/v1/chatbot/analytics

# Bot config (persona, hours, disclosure)
GET    /api/v1/chatbot/config
PUT    /api/v1/chatbot/config

# Dead-letter queue (operator)
GET    /api/v1/chatbot/dead-letters
POST   /api/v1/chatbot/dead-letters/{id}/retry
```

**Authentication:** All endpoints require existing JWT session with `workspace_id` scope. Inbox reply, export, opt-out management require `admin` or `agent` role. Export restricted to `admin` role.

### 3.7 Admin UI (React)

New pages/routes added to existing React application:

```
/chatbot/channels            → ChannelsPage
/chatbot/knowledge-base      → KnowledgeBasePage
/chatbot/test                → TestBotPage
/chatbot/inbox               → InboxPage
/chatbot/inbox/:threadId     → ThreadDetailPage
/chatbot/analytics           → AnalyticsPage
/chatbot/settings            → BotConfigPage (persona, hours, disclosure, opt-out mgmt)
```

Navigation item "Chatbot Hub" added to the existing sidebar, visible to admin and agent roles.

**Real-time inbox updates:** WebSocket or Server-Sent Events (SSE) subscription on `/api/v1/chatbot/inbox/events` pushes new thread/escalation notifications to the inbox page without polling.

---

## 4. Database Schema (Additions)

All new tables are created via Alembic migrations. All tables include `workspace_id UUID NOT NULL REFERENCES workspaces(id)` for isolation. Row-level policies or application-layer filters enforce workspace scope.

### 4.1 Enable pgvector Extension

```sql
-- Migration 0001_enable_pgvector.py
CREATE EXTENSION IF NOT EXISTS vector;
```

### 4.2 `channel_configs` — Per-channel bot configuration

```sql
CREATE TABLE channel_configs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id    UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    channel         VARCHAR(32) NOT NULL,           -- facebook|whatsapp|telegram
    is_active       BOOLEAN NOT NULL DEFAULT FALSE,
    bot_name        VARCHAR(100),
    greeting_msg    TEXT,
    escalation_msg  TEXT,
    out_of_hours_msg TEXT,
    persona_desc    VARCHAR(300),
    ai_disclosure   VARCHAR(500) NOT NULL DEFAULT 'I''m an AI assistant.',
    bot_off_mode    BOOLEAN NOT NULL DEFAULT FALSE,
    credential_id   UUID REFERENCES provider_credentials(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (workspace_id, channel)
);
```

### 4.3 `workspace_bot_config` — Global workspace bot settings

```sql
CREATE TABLE workspace_bot_config (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id            UUID NOT NULL UNIQUE REFERENCES workspaces(id) ON DELETE CASCADE,
    business_hours_timezone VARCHAR(64) NOT NULL DEFAULT 'UTC',
    business_hours_days     INTEGER[] NOT NULL DEFAULT ARRAY[1,2,3,4,5],  -- ISO weekday
    business_hours_start    TIME NOT NULL DEFAULT '09:00',
    business_hours_end      TIME NOT NULL DEFAULT '18:00',
    token_cap_per_session   INTEGER NOT NULL DEFAULT 4000,
    retention_days          INTEGER NOT NULL DEFAULT 90,
    privacy_notice_text     TEXT,
    privacy_policy_url      VARCHAR(500),
    reindex_schedule_time   TIME NOT NULL DEFAULT '02:00',
    current_index_version   UUID,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 4.4 `knowledge_sources` — Knowledge base source registry

```sql
CREATE TABLE knowledge_sources (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id    UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    source_type     VARCHAR(32) NOT NULL,   -- url|document|faq|qa_pair
    name            VARCHAR(255) NOT NULL,
    config          JSONB NOT NULL DEFAULT '{}',
                    -- url: { "url": "...", "crawl_depth": 2 }
                    -- document: { "filename": "...", "storage_path": "..." }
                    -- faq: { "content": "..." }
                    -- qa_pair: { "question": "...", "answer": "..." }
    status          VARCHAR(32) NOT NULL DEFAULT 'pending',
                    -- pending|indexing|ready|failed
    chunk_count     INTEGER,
    last_indexed_at TIMESTAMPTZ,
    error_message   TEXT,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_knowledge_sources_workspace ON knowledge_sources(workspace_id);
```

### 4.5 `knowledge_chunks` — Vector index

```sql
CREATE TABLE knowledge_chunks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id    UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    source_id       UUID NOT NULL REFERENCES knowledge_sources(id) ON DELETE CASCADE,
    index_version   UUID NOT NULL,          -- ties chunk to a specific re-index run
    chunk_text      TEXT NOT NULL,
    embedding       vector(768),            -- nomic-embed-text dimension
    chunk_index     INTEGER NOT NULL,       -- sequential position within source
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- HNSW index for fast approximate nearest-neighbour search
CREATE INDEX idx_knowledge_chunks_embedding
    ON knowledge_chunks
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

CREATE INDEX idx_knowledge_chunks_workspace_version
    ON knowledge_chunks(workspace_id, index_version);
```

### 4.6 `chat_conversations` — Conversation thread registry

```sql
CREATE TABLE chat_conversations (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id            UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    channel                 VARCHAR(32) NOT NULL,
    visitor_id              VARCHAR(255) NOT NULL,   -- normalized by adapter
    status                  VARCHAR(32) NOT NULL DEFAULT 'bot_active',
                            -- bot_active|escalated|agent_active|resolved|out_of_hours|opted_out
    pinned_index_version    UUID,                    -- KB version pinned at session start
    session_token_count     INTEGER NOT NULL DEFAULT 0,
    lead_capture_state      VARCHAR(32) DEFAULT 'none',
                            -- none|greeting|open|privacy_notice|collecting|created|declined
    contact_id              UUID REFERENCES contacts(id),
    assigned_agent_id       UUID,
    customer_last_message_at TIMESTAMPTZ,            -- WhatsApp 24h window tracking
    out_of_hours_flag       BOOLEAN NOT NULL DEFAULT FALSE,
    started_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_activity_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at                TIMESTAMPTZ,
    turn_count              INTEGER NOT NULL DEFAULT 0,
    escalation_reason       VARCHAR(128),
    outcome                 VARCHAR(32),            -- bot_resolved|escalated|lead_captured
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (workspace_id, channel, visitor_id, started_at)
);
CREATE INDEX idx_chat_conversations_workspace ON chat_conversations(workspace_id);
CREATE INDEX idx_chat_conversations_status ON chat_conversations(workspace_id, status);
CREATE INDEX idx_chat_conversations_last_activity ON chat_conversations(workspace_id, last_activity_at DESC);
```

### 4.7 `chat_messages` — Persistent message log

```sql
CREATE TABLE chat_messages (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES chat_conversations(id) ON DELETE CASCADE,
    workspace_id    UUID NOT NULL,   -- denormalized for partition-scoped queries
    sender_role     VARCHAR(16) NOT NULL,    -- visitor|bot|agent
    message_text    TEXT,
    is_non_text     BOOLEAN NOT NULL DEFAULT FALSE,
    media_type      VARCHAR(64),             -- image|voice|document|sticker|location|other
    bot_confidence  FLOAT,                  -- cosine score of best retrieved chunk
    token_count     INTEGER,
    provider_message_id VARCHAR(255),       -- for deduplication
    sent_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_chat_messages_conversation ON chat_messages(conversation_id, sent_at);
CREATE UNIQUE INDEX idx_chat_messages_dedup
    ON chat_messages(workspace_id, provider_message_id)
    WHERE provider_message_id IS NOT NULL;
```

### 4.8 `opt_out_registry` — Channel-scoped opt-out records

```sql
CREATE TABLE opt_out_registry (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id    UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    channel         VARCHAR(32) NOT NULL,
    visitor_id      VARCHAR(255) NOT NULL,
    opted_out_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    opted_out_by    VARCHAR(32) NOT NULL DEFAULT 'visitor',  -- visitor|admin
    re_enabled_at   TIMESTAMPTZ,
    re_enabled_by   UUID,                   -- admin user_id
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,   -- FALSE = re-enabled
    UNIQUE (workspace_id, channel, visitor_id)
);
CREATE INDEX idx_opt_out_registry_workspace ON opt_out_registry(workspace_id, channel, is_active);
```

### 4.9 `analytics_snapshots` — Pre-aggregated analytics

```sql
CREATE TABLE analytics_snapshots (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id    UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    channel         VARCHAR(32),            -- NULL = aggregate
    snapshot_date   DATE NOT NULL,
    total_conversations INTEGER NOT NULL DEFAULT 0,
    total_messages  INTEGER NOT NULL DEFAULT 0,
    bot_resolved    INTEGER NOT NULL DEFAULT 0,
    escalations     INTEGER NOT NULL DEFAULT 0,
    leads_captured  INTEGER NOT NULL DEFAULT 0,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (workspace_id, channel, snapshot_date)
);
```

---

## 5. Redis Data Structures

| Key pattern | Type | Content | TTL |
|---|---|---|---|
| `chat:session:{workspace_id}:{channel}:{visitor_id}` | JSON string | Last N message turns (default 10) | 24 h |
| `chatbot:inbound:{workspace_id}` | List | Serialised `InboundMessage` JSON | none (queue) |
| `chatbot:dedup:{workspace_id}:{channel}:{provider_message_id}` | String | `"1"` | 24 h |
| `chatbot:deadletter:{workspace_id}` | List | Failed message envelope with error details | 7 days |
| `chatbot:reindex:lock:{workspace_id}` | String | `"1"` | 15 min (prevents concurrent re-index) |
| `chatbot:token_budget:{workspace_id}:{conversation_id}` | String | `"<cumulative_token_count>"` | 24 h |

---

## 6. Implementation Patterns & Consistency Rules

These rules ensure multiple AI agents write compatible code across all ChatBot Hub epics.

### 6.1 Naming Conventions

| Concern | Convention | Example |
|---|---|---|
| DB table names | `snake_case`, plural | `knowledge_chunks`, `channel_configs` |
| DB column names | `snake_case` | `workspace_id`, `is_active` |
| API endpoints | `kebab-case` resource nouns, plural | `/knowledge-sources`, `/chat-conversations` |
| Python files | `snake_case` | `chat_worker.py`, `facebook_messenger.py` |
| Python classes | `PascalCase` | `ChatChannelAdapter`, `ConversationEngine` |
| Python functions | `snake_case` | `verify_webhook()`, `parse_inbound_event()` |
| React components | `PascalCase` | `InboxPage`, `ThreadDetailPage` |
| React hooks | `camelCase` with `use` prefix | `useChatThreads()`, `useBotConfig()` |
| React routes | `kebab-case` | `/chatbot/knowledge-base`, `/chatbot/inbox` |
| Redis key namespaces | `chatbot:` prefix | `chatbot:inbound:`, `chat:session:` |

### 6.2 API Response Conventions

All API responses follow the existing SignalLoop response envelope (no change):

```json
{ "data": { ... }, "meta": { ... } }          // success
{ "error": { "code": "...", "message": "..." } }  // error
```

Pagination follows existing cursor-based pattern. No offset pagination for message lists.

### 6.3 Workspace Isolation Rule

**Every database query that touches any ChatBot Hub table MUST include `WHERE workspace_id = :workspace_id`** (or equivalent ORM filter). No query may omit this filter. This is enforced via:

1. All repository functions accept `workspace_id: UUID` as first argument
2. Service layer always passes `workspace_id` extracted from the authenticated JWT
3. Integration tests include a cross-workspace isolation test per resource type

### 6.4 Channel Adapter Registration

New channel adapters are registered in `registry.py`. Workers and routers look up adapters by channel type string. Adding a new channel never requires modifying existing router or worker code — only registering a new adapter.

```python
CHANNEL_REGISTRY: dict[str, type[ChatChannelAdapter]] = {
    "facebook": FacebookMessengerAdapter,
    "whatsapp": WhatsAppCloudAdapter,
    "telegram": TelegramBotAdapter,
}
```

### 6.5 Webhook Handler Pattern

All webhook handlers follow this exact pattern — no exceptions:

```python
@router.post("/webhooks/{channel}/{workspace_id}")
async def inbound_webhook(channel: str, workspace_id: UUID, request: Request):
    adapter = get_adapter(channel)
    if not adapter.verify_webhook(request):
        raise HTTPException(status_code=401, detail="Signature invalid")
    payload = await request.json()
    msg = adapter.parse_inbound_event(payload)
    if msg is None:
        return {"status": "ok"}  # non-message event (delivery receipt, etc.)
    if await is_duplicate(workspace_id, channel, msg.provider_message_id):
        return {"status": "ok"}
    await enqueue_inbound(workspace_id, msg)
    await log_webhook_event(workspace_id, channel, msg, "queued")
    return {"status": "ok"}
```

### 6.6 Error Handling in Chat Worker

```python
for attempt in range(1, MAX_RETRIES + 1):
    try:
        await process_message(msg)
        break
    except Exception as e:
        if attempt == MAX_RETRIES:
            await dead_letter(workspace_id, msg, error=str(e))
            await alert_operator(workspace_id, msg.provider_message_id)
        else:
            await asyncio.sleep(2 ** attempt)  # exponential backoff
```

### 6.7 Lead Capture State Machine

State is stored in `chat_conversations.lead_capture_state`. The `LeadCaptureStateMachine` in `lead_capture.py` transitions state and never modifies it outside the state machine class.

```
none → greeting → open_conversation
open_conversation → [intent_detected] → privacy_notice_prompt
privacy_notice_prompt → [consent_given]  → collecting
privacy_notice_prompt → [consent_declined] → declined
collecting → [details_provided] → lead_created → confirmed
collecting → [details_declined] → declined
```

After `declined`, `lead_capture_state` is set to `declined` and the state machine does not re-trigger for that session.

### 6.8 AI Disclosure Enforcement

The `ai_disclosure` field from `channel_configs` is **always** injected into the system prompt. The `prompts.py` module raises `AssertionError` if `ai_disclosure` is empty or shorter than 10 characters. There is no code path that bypasses disclosure injection.

### 6.9 WhatsApp 24-Hour Window Enforcement

`chat_conversations.customer_last_message_at` is updated by the chat worker on every inbound visitor message for WhatsApp conversations. Before dispatching any agent reply, `WhatsAppCloudAdapter.send_message()` checks:

```python
if channel == "whatsapp":
    elapsed = now() - conversation.customer_last_message_at
    if elapsed > timedelta(hours=24):
        raise WhatsAppWindowExpiredError("24-hour messaging window expired")
```

The inbox UI checks this via a dedicated field in the thread API response (`is_whatsapp_window_open: bool`) and disables the reply input accordingly.

---

## 7. Project Structure Additions

The following additions are made to the existing SignalLoop monorepo structure. No existing directories are deleted or renamed.

```
apps/
├── api/
│   └── app/
│       ├── domain/
│       │   └── chatbot/               ← NEW: chatbot domain logic
│       │       ├── __init__.py
│       │       ├── engine.py          # ConversationEngine
│       │       ├── prompts.py         # system prompt templates
│       │       ├── escalation.py      # EscalationDetector
│       │       ├── lead_capture.py    # LeadCaptureStateMachine
│       │       ├── opt_out.py         # OptOutRegistry
│       │       └── token_counter.py   # TokenBudgetTracker
│       ├── infrastructure/
│       │   ├── providers/
│       │   │   └── chat/              ← NEW: channel adapters
│       │   │       ├── base.py        # ChatChannelAdapter ABC
│       │   │       ├── facebook_messenger.py
│       │   │       ├── whatsapp_cloud.py
│       │   │       ├── telegram_bot.py
│       │   │       └── registry.py
│       │   ├── rag/                   ← NEW: RAG pipeline components
│       │   │   ├── __init__.py
│       │   │   ├── crawler.py         # httpx + BeautifulSoup4
│       │   │   ├── document_parser.py # pypdf2, python-docx
│       │   │   ├── chunker.py         # RecursiveCharacterTextSplitter
│       │   │   ├── embedder.py        # Ollama nomic-embed-text
│       │   │   └── retriever.py       # pgvector cosine similarity
│       │   └── vector_store/          ← NEW: pgvector repository
│       │       ├── __init__.py
│       │       └── chunk_repository.py
│       ├── routers/
│       │   ├── chatbot/               ← NEW: admin API routers
│       │   │   ├── __init__.py
│       │   │   ├── channels.py
│       │   │   ├── knowledge_sources.py
│       │   │   ├── inbox.py
│       │   │   ├── analytics.py
│       │   │   ├── config.py
│       │   │   └── dead_letters.py
│       │   └── webhooks/              ← NEW: inbound webhook handlers
│       │       ├── __init__.py
│       │       └── chat_webhooks.py   # Facebook, WhatsApp, Telegram endpoints
│       └── db/
│           └── migrations/
│               ├── 0001_enable_pgvector.py           ← NEW
│               ├── 0002_channel_configs.py           ← NEW
│               ├── 0003_workspace_bot_config.py      ← NEW
│               ├── 0004_knowledge_sources.py         ← NEW
│               ├── 0005_knowledge_chunks.py          ← NEW (with vector column)
│               ├── 0006_chat_conversations.py        ← NEW
│               ├── 0007_chat_messages.py             ← NEW
│               ├── 0008_opt_out_registry.py          ← NEW
│               └── 0009_analytics_snapshots.py       ← NEW
├── workers/
│   ├── call_worker.py                 (existing)
│   ├── sequence_worker.py             (existing)
│   ├── chat_worker.py                 ← NEW: inbound message processor
│   └── knowledge_indexing_worker.py   ← NEW: RAG ingestion pipeline
└── web/
    └── src/
        ├── pages/
        │   └── chatbot/               ← NEW: chatbot admin UI pages
        │       ├── ChannelsPage.tsx
        │       ├── KnowledgeBasePage.tsx
        │       ├── TestBotPage.tsx
        │       ├── InboxPage.tsx
        │       ├── ThreadDetailPage.tsx
        │       ├── AnalyticsPage.tsx
        │       └── BotConfigPage.tsx
        ├── components/
        │   └── chatbot/               ← NEW: chatbot-specific components
        │       ├── ThreadList.tsx
        │       ├── MessageHistory.tsx
        │       ├── ReplyInput.tsx      # WhatsApp window guard built-in
        │       ├── KnowledgeSourceCard.tsx
        │       └── TestBotPanel.tsx
        └── hooks/
            └── chatbot/               ← NEW: chatbot-specific hooks
                ├── useChatThreads.ts
                ├── useBotConfig.ts
                └── useKnowledgeSources.ts

tests/
├── unit/
│   └── chatbot/                       ← NEW: unit tests
│       ├── test_conversation_engine.py
│       ├── test_lead_capture_sm.py
│       ├── test_escalation_detector.py
│       ├── test_token_counter.py
│       └── test_channel_adapters.py
├── integration/
│   └── chatbot/                       ← NEW: integration tests
│       ├── test_webhook_facebook.py
│       ├── test_webhook_whatsapp.py
│       ├── test_webhook_telegram.py
│       ├── test_rag_pipeline.py
│       ├── test_workspace_isolation.py  # REQUIRED: cross-workspace leak test
│       └── test_opt_out_enforcement.py
└── e2e/
    └── chatbot/                       ← NEW: end-to-end tests
        ├── test_full_conversation.py
        └── test_lead_capture_flow.py
```

---

## 8. Security Architecture

### 8.1 Webhook Signature Verification

| Channel | Mechanism | Implementation |
|---|---|---|
| Facebook Messenger | HMAC-SHA256 of payload using `app_secret`; verified in `X-Hub-Signature-256` header | `FacebookMessengerAdapter.verify_webhook()` |
| WhatsApp Cloud API | Same as Facebook (shared Meta platform); `X-Hub-Signature-256` | `WhatsAppCloudAdapter.verify_webhook()` |
| Telegram | `X-Telegram-Bot-Api-Secret-Token` header matched against stored secret | `TelegramBotAdapter.verify_webhook()` |

**Rule:** Verification always happens before any payload deserialization or logging. Any request failing verification receives HTTP 401 and a security audit log entry. The raw payload bytes are used for signature computation (not parsed JSON).

### 8.2 Credential Storage

All channel tokens (Facebook Page access token, WhatsApp Business phone number ID + bearer token, Telegram bot token) are stored in the existing `ProviderCredential` model using the existing AES-256 encryption mechanism. The chat worker decrypts credentials on use; they are never stored in Redis or logged.

### 8.3 Workspace Data Isolation

Three layers of isolation:

1. **Application layer:** All repository functions enforce `workspace_id` filter (see §6.3).
2. **Database layer:** All tables have `workspace_id NOT NULL` with FK to `workspaces`. Future: row-level security policies for defence-in-depth.
3. **Vector index layer:** All pgvector queries include `WHERE workspace_id = :workspace_id AND index_version = :version`. No cross-workspace embedding query is possible via the application layer.

### 8.4 PII Handling

- Conversation message text and captured visitor PII are stored in `chat_messages` and `contacts`.
- Retention is enforced by a nightly purge job that soft-deletes records older than `workspace_bot_config.retention_days`.
- Export endpoint restricted to admin role. Export includes audit log entry.
- Lead capture consent event is recorded in `contacts` audit log (LC7).

### 8.5 Token Budget as a Security Control

In addition to cost control, the 4,000-token cap per session also limits the blast radius of prompt injection attempts embedded in visitor messages — long injected context exceeds the budget and triggers graceful escalation rather than unbounded LLM processing.

---

## 9. Deployment Topology

### 9.1 Development (compose.yml)

One-line change to existing `compose.yml`:

```yaml
services:
  db:
    image: pgvector/pgvector:pg17   # was: postgres:17
```

Add Ollama service if not already present (for `nomic-embed-text`):

```yaml
  ollama:
    image: ollama/ollama:latest
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama
```

Add new worker processes to the worker service or as a separate `chat_worker` service:

```yaml
  chat_worker:
    build: ./apps/workers
    command: python chat_worker.py
    depends_on: [db, redis, ollama]
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
      - OLLAMA_URL=http://ollama:11434

  knowledge_indexing_worker:
    build: ./apps/workers
    command: python knowledge_indexing_worker.py
    depends_on: [db, redis, ollama]
```

### 9.2 Production

Follows the existing SignalLoop production topology (container orchestration, managed Postgres, Redis). Additional production notes:

- `pgvector/pgvector:pg17` is a drop-in replacement for `postgres:17` — same upgrade path, managed DB support available on RDS, Cloud SQL, Supabase, Neon.
- Ollama in production: deploy on a GPU-enabled instance or use a hosted embedding API. The `embedder.py` abstraction supports swapping to OpenAI/Cohere embeddings via config change without code changes.
- `chat_worker.py` and `knowledge_indexing_worker.py` are stateless; scale horizontally. Use Redis queue for load distribution.
- WebSocket / SSE for inbox real-time: handled by a FastAPI background task or a dedicated SSE endpoint; no separate pub/sub service required for MVP.

---

## 10. Architecture Validation

### 10.1 Requirement Coverage Check

| PRD Section | Architecture Coverage |
|---|---|
| CH1–CH9 Channel management | §3.1 Channel Adapter Layer, §4.2 `channel_configs`, §3.6 Admin API |
| KB1–KB12 Knowledge base | §3.4 RAG Pipeline, §4.4–4.5, §3.6, §3.7 |
| BOT1–BOT13 Conversation engine | §3.3 Chat Worker, §3.5 Bot Conversation Engine |
| LC1–LC7 Lead capture | §6.7 Lead Capture State Machine, §4.6 `chat_conversations` |
| HH1–HH9 Inbox and handoff | §3.6 Admin API `/inbox`, §3.7 React routes, §4.6–4.7 |
| OC1–OC4 Opt-out / compliance | §4.8 `opt_out_registry`, §3.3 step 3, §3.6 opt-out endpoints |
| AN1–AN4 Analytics | §4.9 `analytics_snapshots`, §3.6 analytics endpoint |
| WS1–WS5 Webhook security | §8.1 Webhook signature verification, §6.5 webhook handler pattern |
| NFR-CB1 (p95 5 s response) | Async worker (§3.3), Redis queue (§3.2) |
| NFR-CB5 (99.9% availability) | Dead-letter + retry (§6.6) |
| NFR-CB8 (credentials encrypted) | §8.2 Credential Storage |
| NFR-CB9 (workspace isolation) | §6.3, §8.3 |
| NFR-CB12 (retention/purge) | §8.4, `workspace_bot_config.retention_days` |
| NFR-CB15 (WhatsApp 24h window) | §6.9, `chat_conversations.customer_last_message_at` |
| NFR-CB16 (token cap) | §3.5 TokenBudgetTracker, §6.8 |

### 10.2 Integration Points with Existing SignalLoop

| Integration | Method | Notes |
|---|---|---|
| Contact pool write-back | Existing `Contact` model + repository | LC4: create/upsert contact with `chatbot-lead` tag |
| `ProviderCredential` | Existing model unchanged | CH2: store channel tokens using same encryption |
| Notification system | Existing notification service | HH8: escalation alert uses existing workspace admin email notification |
| JWT authentication | Existing auth middleware | All new endpoints use same JWT scope + role check |
| Worker pattern | Sibling workers | `chat_worker.py` follows same Redis queue + error pattern as `call_worker.py` |

### 10.3 Decisions That Must Not Be Changed by Implementation Agents

1. **`workspace_id` isolation is mandatory on every DB query.** No exceptions.
2. **AI disclosure is always injected into every system prompt.** Non-configurable bypass is forbidden.
3. **Webhook signature verification happens before payload deserialization.** Order must not be reversed.
4. **In-flight sessions pin their index version.** A re-index must not invalidate active sessions.
5. **Opt-out check precedes RAG and LLM.** Bot must not respond to opted-out visitors.
6. **WhatsApp 24h window check is in the adapter send path, not the worker.** It cannot be bypassed by a direct DB insert.
7. **Token budget tracking is cumulative across the session.** It must not reset on each turn.

---

_Architecture document complete. Ready for Epic and Story breakdown (bmad-create-epics-and-stories)._
