---
title: Environment Variables Reference
description: Every environment variable EngageHub reads, what it does, and whether it is required for local development.
date: 2026-05-28
---

# Environment Variables Reference

EngageHub reads its configuration from two `.env` files:

- `./.env` — backend, workers, infrastructure. Loaded by `apps/api/app/core/config.py` via Pydantic Settings.
- `apps/web/.env` — frontend (Vite). Only variables prefixed `VITE_` are exposed to the browser bundle.

Copy `./.env.example` to `./.env` to start. Frontend defaults in `apps/web/.env` already point at the local API.

## Backend `.env`

### Core (required)

| Variable | Default in example | What it does |
| --- | --- | --- |
| `PROJECT_NAME` | `EngageHub` | Shown in OpenAPI title and outbound email "from" name fallback. |
| `ENVIRONMENT` | `local` | One of `local`, `staging`, `production`. Outside `local`, default secrets like `changethis` cause hard failures. |
| `SECRET_KEY` | `changethis` | JWT signing key. **Must** be changed for any non-local use; warned in local. |
| `FIRST_SUPERUSER` | `admin@example.com` | Email of the seed superuser created by `app.initial_data`. |
| `FIRST_SUPERUSER_PASSWORD` | `changethis` | Password of the seed superuser. Change this — you'll use it to log in. |
| `FRONTEND_HOST` | `http://localhost:5173` | Used to construct password-reset links. |
| `BACKEND_CORS_ORIGINS` | `["http://localhost:5173"]` | JSON list of allowed CORS origins. |

### Database & cache (required)

| Variable | Default in example | What it does |
| --- | --- | --- |
| `POSTGRES_SERVER` | `localhost` | Postgres host. |
| `POSTGRES_PORT` | `5432` | Postgres port. |
| `POSTGRES_DB` | `engagehub` | Database name. Must exist (`createdb -U postgres engagehub`). |
| `POSTGRES_USER` | `postgres` | Postgres user. |
| `POSTGRES_PASSWORD` | `changethis` | Postgres password. Must be changed in non-local environments. |
| `REDIS_URL` | `redis://localhost:6379/0` | Full Redis URL. Override DB index with `/1`, `/2`, etc. |

### Outbound SMTP (optional — for transactional email like password reset)

| Variable | Default | What it does |
| --- | --- | --- |
| `SMTP_HOST` | empty | When set together with `EMAILS_FROM_EMAIL`, enables transactional email. Use `localhost:1025` to capture in Mailpit. |
| `SMTP_PORT` | `587` | SMTP port. Use `1025` for Mailpit. |
| `SMTP_USER` | empty | SMTP auth user. Leave blank for Mailpit. |
| `SMTP_USERNAME` | empty | Provider-layer alias for `SMTP_USER`. Leave blank for Mailpit. |
| `SMTP_PASSWORD` | empty | SMTP auth password. Leave blank for Mailpit. |
| `EMAILS_FROM_EMAIL` | `noreply@example.com` | Default "from" address. |
| `EMAILS_FROM_NAME` | derived from `PROJECT_NAME` | Default "from" display name. |
| `SMTP_FROM_EMAIL` | empty | Provider-layer alias for `EMAILS_FROM_EMAIL`. |
| `SMTP_FROM_NAME` | empty | Provider-layer alias for `EMAILS_FROM_NAME`. |
| `SMTP_USE_TLS` | `false` | Provider-layer implicit TLS toggle. Keep `false` for Mailpit. |
| `SMTP_USE_STARTTLS` | `true` | Provider-layer STARTTLS toggle. Keep `false` for Mailpit. |
| `EMAIL_RESET_TOKEN_EXPIRE_HOURS` | `48` | Lifetime of password-reset tokens. |

### Provider integrations (optional — feature-gated)

Each adapter fails closed when its key is empty, so the API and UI still boot without them.

| Variable | Feature | What it does |
| --- | --- | --- |
| `SENDGRID_API_KEY` | Campaign email | Sender API key. Without it, the sequence worker skips sends. |
| `SENDGRID_WEBHOOK_SECRET` | Inbound delivery events | HMAC secret for verifying SendGrid event webhooks. |
| `SENDGRID_FROM_EMAIL` | Campaign email | "From" address used by the sequence worker. |
| `TWILIO_ACCOUNT_SID` | Voice outreach | Twilio account SID. |
| `TWILIO_AUTH_TOKEN` | Voice outreach | Twilio auth token. |
| `TWILIO_PHONE_NUMBER` | Voice outreach | Caller-ID number used by the call worker. |
| `VAPI_API_KEY` | Managed AI voice | Vapi API key used when the workspace voice provider is `vapi`. |
| `VAPI_PHONE_NUMBER_ID` | Managed AI voice | Vapi phone number ID used for outbound calls. |
| `VAPI_ASSISTANT_ID` | Managed AI voice | Saved Vapi assistant ID used for outbound calls. |
| `VAPI_API_BASE_URL` | Managed AI voice | Vapi API base URL. Defaults to `https://api.vapi.ai`. |
| `VAPI_CALL_ENDPOINT` | Managed AI voice | Vapi call creation endpoint. Defaults to `/call`. |
| `DEEPGRAM_API_KEY` | Post-call processing | Transcription provider key. |
| `GROQ_API_KEY` | Post-call processing | LLM provider key for call summaries. |
| `OLLAMA_BASE_URL` | Local LLM | Local Ollama server URL. Defaults to `http://localhost:11434`. |
| `OLLAMA_MODEL` | Local LLM | Local Ollama model. Defaults to `llama3.2:1b`. |
| `FASTER_WHISPER_BASE_URL` | Local STT | Local faster-whisper service URL. Defaults to `http://localhost:9000`. |
| `FASTER_WHISPER_MODEL` | Local STT | Local faster-whisper model name. Defaults to `base`. |

### Operational

| Variable | Default | What it does |
| --- | --- | --- |
| `TEAM_NOTIFICATION_EMAIL` | empty | Optional ops mailbox to alert on critical events. |
| `MAX_RETRY_COUNT` | `3` | Dead-letter retry cap before a job is parked. |
| `SENTRY_DSN` | empty | When set, errors are forwarded to Sentry. |
| `EMAIL_TEST_USER` | `test@example.com` | Used only by automated tests. |

## Frontend `apps/web/.env`

Only variables prefixed `VITE_` are exposed to the browser bundle.

| Variable | Default | What it does |
| --- | --- | --- |
| `VITE_API_URL` | `http://localhost:8001` | Base URL the SPA uses to reach the API. |

## Quick recipes

### Bare-minimum local-only setup

```dotenv
ENVIRONMENT=local
SECRET_KEY=local-dev-not-a-real-secret
FIRST_SUPERUSER=admin@example.com
FIRST_SUPERUSER_PASSWORD=local-dev-password
POSTGRES_PASSWORD=postgres
```

Everything else inherits from `.env.example`. SendGrid/Twilio/Deepgram/Groq are off; transactional email goes nowhere.

### Local with captured outbound email via Mailpit

Add on top of the bare minimum:

```dotenv
SMTP_HOST=localhost
SMTP_PORT=1025
SMTP_TLS=false
SMTP_USE_TLS=false
SMTP_USE_STARTTLS=false
SMTP_USER=
SMTP_PASSWORD=
EMAILS_FROM_EMAIL=dev@localhost
SMTP_FROM_EMAIL=dev@localhost
SMTP_FROM_NAME=EngageHub Demo
```

Mailpit must be running (it is, if you ran `.\StartServer.ps1`). View captured email at <http://localhost:8025>.

### Near-zero local providers

Use this when you want provider selection to work locally without paid vendor accounts:

```dotenv
SMTP_HOST=localhost
SMTP_PORT=1025
SMTP_TLS=false
SMTP_USE_TLS=false
SMTP_USE_STARTTLS=false
EMAILS_FROM_EMAIL=dev@localhost
SMTP_FROM_EMAIL=dev@localhost
SMTP_FROM_NAME=EngageHub Demo

OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2:1b

FASTER_WHISPER_BASE_URL=http://localhost:9000
FASTER_WHISPER_MODEL=base
```

Start the local helper stack with `.\tooling\demo-up.ps1`, or start each service manually. The demo seed script selects `smtp`, `ollama_local`, and `faster_whisper_local` for the default workspace.

### Local with real provider testing

Add only the provider blocks you actually plan to exercise. Never commit real keys — keep them in a personal `.env` only.

## Where to look in code

- Backend settings class: `apps/api/app/core/config.py` (Pydantic `Settings`).
- Provider adapters: `apps/api/app/infrastructure/`.
- Frontend env access: `import.meta.env.VITE_*` inside `apps/web/src/`.
