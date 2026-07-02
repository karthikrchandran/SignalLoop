# eMailVoice Repository Graph

Generated from the current checkout on 2026-06-30.

## Workspace Graph

```mermaid
flowchart LR
    Repo[eMailVoice monorepo]

    Repo --> Web[apps/web<br/>React + Vite frontend]
    Repo --> Api[apps/api<br/>FastAPI backend]
    Repo --> Workers[apps/workers<br/>background worker package]
    Repo --> Mobile[apps/mobile]
    Repo --> Contracts[packages/event-contracts]
    Repo --> SharedTypes[packages/shared-types]
    Repo --> Docs[docs]
    Repo --> Bmad[_bmad and _bmad-output]

    Web --> ApiClient[generated/openapi API client]
    Web --> Routes[route tree]
    Web --> Features[feature workspaces]

    Api --> ApiRoutes[app/api/routes]
    Api --> ChatbotRouters[app/routers/chatbot]
    Api --> Domain[app/domain]
    Api --> Infra[app/infrastructure]
    Api --> Integrations[app/integrations]
    Api --> Models[app/domain_models.py + app/models.py]
    Api --> Alembic[app/alembic]
    Api --> ApiWorkers[app/workers]

    Contracts -. shared events .-> Api
    SharedTypes -. shared TS types .-> Web
```

## Backend Layer Graph

```mermaid
flowchart TB
    FastAPI[app/main.py<br/>FastAPI app] --> ApiRouter[app/api/main.py<br/>API router composition]
    FastAPI --> Middleware[core middleware<br/>tracing, security headers, rate limit]
    FastAPI --> Redis[infrastructure/db/redis]

    ApiRouter --> CoreRoutes[app/api/routes<br/>campaigns, contacts, accounts, calls, voice, sequences, signals, templates, prospecting, customer_360]
    ApiRouter --> ChatbotRoot[app/routers/chatbot/router.py]

    ChatbotRoot --> ChatbotSubroutes[analytics, channels, config, dead letters, inbox, knowledge, opt-outs, webhooks]

    CoreRoutes --> DomainServices[domain services]
    ChatbotSubroutes --> ChatbotDomain[domain/chatbot]

    DomainServices --> Models[domain_models.py]
    ChatbotDomain --> ChatbotModels[domain/chatbot/models.py]
    DomainServices --> SequenceModels[domain/sequences/models.py]
    DomainServices --> VoiceModels[domain/voice/models.py]
    DomainServices --> SignalModels[domain/signals/models.py]

    DomainServices --> Providers[infrastructure/providers<br/>email, voice, SMS, LLM, STT, TTS]
    DomainServices --> RAG[infrastructure/rag + vector_store]
    DomainServices --> Audit[domain/audit]
    DomainServices --> Timeline[domain/timeline]

    Workers[app/workers] --> DomainServices
    Workers --> Providers
    Workers --> Models

    Alembic[app/alembic] --> Models
```

## Shared CRM Cutover Graph

```mermaid
flowchart LR
    ECRM[eCRM<br/>/api/shared-records]
    Client[app/integrations/ecrm_shared_records.py]
    SharedDomain[domain/shared_records/service.py]

    ECRM <--> Client
    Client <--> SharedDomain

    ContactsRoute[api/routes/contacts.py] --> SharedDomain
    AccountsRoute[api/routes/accounts.py] --> Client
    CampaignsRoute[api/routes/campaigns.py] --> SharedDomain
    Customer360[domain/customer_360/service.py] --> SharedDomain
    Prospecting[domain/prospecting/service.py] --> SharedDomain
    ChatbotLeadCapture[domain/chatbot/lead_capture.py] --> SharedDomain
    ChatbotInbox[routers/chatbot/inbox.py] --> SharedDomain

    SharedDomain --> ContactPublic[ContactPublic read models]
    SharedDomain --> AccountPublic[AccountPublic and Customer360 read models]

    OperationalTables[progression, timeline, action queue,<br/>voice, signals, sequences, chatbot links]
    OperationalTables -. store shared contact/account ids .-> SharedDomain
    OperationalTables -. no hard FK to local contacts/accounts .-> LocalLegacy[legacy local contacts/accounts fallback tables]
```

## Frontend Graph

```mermaid
flowchart TB
    Vite[apps/web<br/>Vite + React] --> Router[routeTree.gen.ts + routes]
    Vite --> Client[src/client]
    Vite --> Features[src/features]
    Vite --> Components[src/components]
    Vite --> Hooks[src/hooks]
    Vite --> Lib[src/lib]

    Router --> CampaignRoutes[campaigns + lifecycle routes]
    Router --> ContactsRoute[contacts]
    Router --> Customer360Route[customer-360]
    Router --> ProspectingRoute[prospecting]
    Router --> ChatbotRoutes[chatbot routes]
    Router --> VoiceAgentsRoute[voice-agents]
    Router --> SettingsRoutes[settings/provider routes]

    Features --> CampaignsFeature[campaigns]
    Features --> ChatbotFeature[chatbot]
    Features --> SharedApi[API client usage]

    SharedApi --> Backend[apps/api]
```

## Operational Flow Graph

```mermaid
sequenceDiagram
    participant Web as Web UI
    participant API as FastAPI routes
    participant Domain as Domain services
    participant Shared as eCRM shared-records adapter
    participant DB as eMailVoice operational DB
    participant Providers as Email/Voice/Chat providers
    participant Workers as Background workers

    Web->>API: request workspace data/action
    API->>Domain: validate and execute use case
    Domain->>Shared: read/write shared customer/contact data when enabled
    Domain->>DB: write eMailVoice-owned operational history
    Domain->>Providers: send/queue external channel action
    Workers->>DB: poll queued work
    Workers->>Providers: execute delivery/call/post-call work
    Providers-->>API: webhooks/events
    API->>DB: persist event/timeline/signal state
```

## Notes

- `apps/api/app/domain/shared_records/service.py` is now the shared CRM read adapter for eMailVoice page and service reads.
- `apps/api/app/integrations/ecrm_shared_records.py` is the HTTP boundary for eCRM `/api/shared-records`.
- Local `contacts` and `accounts` tables still exist as compatibility/fallback tables, but the current cutover path no longer requires operational rows to have hard foreign keys to those tables.
- ChatBot WhatsApp lead capture now upserts shared contacts directly, and the inbox lead detail view resolves the same shared record instead of reading the local `contacts` table.
- The graph is intentionally architectural. It does not include every file-level import edge because the repo currently has hundreds of source files and generated routes.
