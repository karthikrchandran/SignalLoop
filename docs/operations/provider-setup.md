# Provider Setup — API Keys & Local Tools

All keys go into the `.env` file at the repo root.  
Start each section only when you're ready to use that feature.

For the current local-only demo, use Mailpit, Ollama, and faster-whisper. Leave paid-provider keys blank until you have registered for those services.

---

## 1. Mailpit — Local Email Capture

Mailpit intercepts all outgoing emails locally so nothing is sent to real inboxes during development.

**Install if needed:**
```powershell
scoop install mailpit
```

**Start/Stop:** Managed automatically by `StartServer.ps1` / `StopServer.ps1`.
To start only Mailpit, run:
```powershell
.\tooling\mailpit-up.ps1
```

**Web UI:** http://localhost:8025  
**SMTP port:** 1025

`.env` settings (already set):
```
SMTP_HOST=localhost
SMTP_PORT=1025
SMTP_TLS=false
SMTP_USE_TLS=false
SMTP_USE_STARTTLS=false
SMTP_USER=
SMTP_PASSWORD=
EMAILS_FROM_EMAIL=noreply@example.com
SMTP_FROM_EMAIL=noreply@example.com
SMTP_FROM_NAME=SignalLoop Demo
```

---

## 2. Ollama - Local LLM

Ollama runs the demo LLM locally on your machine. It does not need an API key.

**Install if needed:** install Ollama from <https://ollama.com>.

**Pull the default model once:**
```powershell
ollama pull llama3.2:1b
```

**Start:** `.\tooling\demo-up.ps1` attempts to start `ollama serve` if port `11434` is not already listening.

`.env` settings:
```
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2:1b
```

---

## 3. Faster Whisper - Local STT

The local STT helper wraps `faster-whisper` behind a small FastAPI service. It is intended for batch transcription and post-call processing, not realtime streaming voice.

**Start manually:**
```powershell
uv run --with-requirements tooling/stt_service/requirements.txt uvicorn tooling.stt_service.main:app --host 0.0.0.0 --port 9000
```

`.\tooling\demo-up.ps1` starts this service automatically.

`.env` settings:
```
FASTER_WHISPER_BASE_URL=http://localhost:9000
FASTER_WHISPER_MODEL=base
```

Health check: http://localhost:9000/health

---

## 4. SendGrid — Transactional Email (production)

Used by the `sequence_worker` to send campaign emails to real contacts.

Do this only after you have a SendGrid account and sender identity.

### Sign Up
1. Go to https://sendgrid.com → **Start for Free**
2. Verify your email address
3. Complete the sender identity verification (add a real "From" email you own)

### Get API Key
1. Dashboard → **Settings** → **API Keys** → **Create API Key**
2. Name it `signalloop-local`
3. Permission: **Restricted Access** → enable **Mail Send** only
4. Copy the key (shown only once)

### Configure Sender
1. Dashboard → **Settings** → **Sender Authentication**
2. Verify at minimum a single sender email address
3. Note that email address — it becomes `SENDGRID_FROM_EMAIL`

### Update `.env`
```
SENDGRID_API_KEY=SG.xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
SENDGRID_FROM_EMAIL=you@yourdomain.com
SENDGRID_WEBHOOK_SECRET=          # leave blank for now
```

**Free tier:** 100 emails/day forever.

---

## 5. Twilio — Outbound Voice Calls

Used by the `call_worker` to make AI-assisted outbound calls.

Do this only after you have a Twilio account and a number you are allowed to use.

### Sign Up
1. Go to https://www.twilio.com → **Sign up**
2. Verify your phone number
3. Answer the onboarding questions: "Send messages" → "With code" → "Python"

### Get Credentials
1. Dashboard shows **Account SID** and **Auth Token** on the main page
2. Click **Get a Trial Number** → choose any US number → confirm

### Update `.env`
```
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_PHONE_NUMBER=+1xxxxxxxxxx
```

**Trial credit:** ~$15 USD free. Trial accounts can only call verified numbers until upgraded.  
**To verify a number (trial):** Console → Phone Numbers → Verified Caller IDs → Add.

---

## 6. Vapi - Managed AI Voice Calls

Used by the `call_worker` when a workspace selects `vapi` as the `voice` provider.
Vapi owns the AI voice session; SignalLoop stores the returned Vapi call ID in the existing call-session provider ID field.

### Configure Vapi
1. Create or choose a Vapi assistant.
2. Create or import a Vapi phone number.
3. Copy the API key, phone number ID, and assistant ID.

### Update `.env`
```
VAPI_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
VAPI_PHONE_NUMBER_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
VAPI_ASSISTANT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
VAPI_API_BASE_URL=https://api.vapi.ai
VAPI_CALL_ENDPOINT=/call
```

For workspace-level credentials, store the API key as `api_key` and use:
```
{
  "phone_number_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "assistant_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
}
```
as `config_json` on a `provider_credentials` row with `provider = "vapi"` and `channel = "voice"`.

---

## 7. Deepgram — Speech-to-Text & Text-to-Speech

Used by the `postcall_worker` to transcribe call recordings and by the call worker for TTS voice synthesis.

Do this only after you have a Deepgram account.

### Sign Up
1. Go to https://console.deepgram.com → **Sign Up**
2. No credit card required for trial

### Get API Key
1. Console → **API Keys** → **Create a New API Key**
2. Name it `signalloop-local`
3. Role: **Member** is sufficient
4. Copy the key

### Update `.env`
```
DEEPGRAM_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

**Free credit:** $200 USD on signup (covers ~hundreds of hours of audio).

---

## 8. Groq — LLM Post-Call Processing

Used by the `postcall_worker` to summarize call transcripts and extract structured data using fast LLM inference.

Do this only after you have a Groq account.

### Sign Up
1. Go to https://console.groq.com → **Sign In with Google/GitHub** or create account
2. No credit card required

### Get API Key
1. Console → **API Keys** → **Create API Key**
2. Name it `signalloop-local`
3. Copy the key

### Update `.env`
```
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

**Free tier:** Generous rate limits on Llama 3 / Mixtral models — sufficient for local dev.

---

## Verification Checklist

After changing provider values, restart the API and workers (`StopApp.ps1` then `StartApp.ps1 -Workers`) and check the API logs for any provider errors on startup.

| Service    | `.env` key              | Test                                      |
|------------|-------------------------|-------------------------------------------|
| Mailpit    | *(no key needed)*       | http://localhost:8025 shows inbox         |
| Ollama     | *(no key needed)*       | `ollama list` shows `llama3.2:1b`         |
| Faster Whisper | *(no key needed)*   | http://localhost:9000/health returns `ok` |
| SendGrid   | `SENDGRID_API_KEY`      | Send a test email via API → appears in SG activity |
| Twilio     | `TWILIO_ACCOUNT_SID`    | Make a test call to your verified number  |
| Vapi       | `VAPI_API_KEY`          | Select `vapi` for voice and start one test call |
| Deepgram   | `DEEPGRAM_API_KEY`      | Workers start without provider errors     |
| Groq       | `GROQ_API_KEY`          | Workers start without provider errors     |

---

## Security Note

Never commit `.env` to git. It is already listed in `.gitignore`.  
For production, use environment variables injected by your hosting platform — never a committed file.

---

## 9. Choose Your Providers (Multi-Provider Support)

The platform supports multiple providers for each capability. Workspace admins can switch providers without redeploying.

In the web app, superusers can open `Settings -> Providers` to review and change the active `email`, `llm`, and `stt` providers for the current workspace. The page does not collect secrets; managed-provider credentials still go through the API.

### Supported capability → provider matrix

| Capability | Provider key | Notes |
|---|---|---|
| `email` | `sendgrid` | API key; production default |
| `email` | `smtp` | Mailpit / Postmark / any SMTP relay |
| `voice` | `twilio` | Outbound calls |
| `voice` | `vapi` | Managed AI voice calls |
| `stt`   | `deepgram` | Real-time + batch transcription |
| `stt`   | `faster_whisper_local` | Local batch transcription service |
| `tts`   | `deepgram` | Voice synthesis |
| `llm`   | `groq` | Free tier (high TPS) |
| `llm`   | `openai` | OpenAI API or any OpenAI-compatible endpoint (set `OPENAI_BASE_URL`) |
| `llm`   | `openrouter` | OpenAI-compatible (uses `openai` adapter, override base URL) |
| `llm`   | `together` | OpenAI-compatible (uses `openai` adapter, override base URL) |
| `llm`   | `ollama_local` | Local-only; no API key needed |

### `.env` keys (extras for new providers)

```
# Generic SMTP relay (used when WorkspaceProviderSelection.email = smtp)
SMTP_HOST=
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_FROM_EMAIL=
SMTP_FROM_NAME=
SMTP_USE_TLS=false
SMTP_USE_STARTTLS=true

# OpenAI / OpenAI-compatible LLM (OpenRouter, Together, vLLM, ...)
OPENAI_API_KEY=
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini

# Ollama (local LLM)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2:1b

# Faster Whisper (local STT)
FASTER_WHISPER_BASE_URL=http://localhost:9000
FASTER_WHISPER_MODEL=base

# Vapi (managed AI voice)
VAPI_API_KEY=
VAPI_PHONE_NUMBER_ID=
VAPI_ASSISTANT_ID=
VAPI_API_BASE_URL=https://api.vapi.ai
VAPI_CALL_ENDPOINT=/call
```

Run the local STT service with:
```powershell
uv run --with-requirements tooling/stt_service/requirements.txt uvicorn tooling.stt_service.main:app --host 0.0.0.0 --port 9000
```

Or start the local demo stack and seed local provider selections in one step:
```powershell
.\tooling\demo-up.ps1
```

### Selection API

All endpoints require an admin token and the `X-Workspace-Id` header matching the path.

**List providers offered per capability**
```http
GET /api/v1/workspaces/{workspace_id}/provider-options
```

**Show this workspace's active selections**
```http
GET /api/v1/workspaces/{workspace_id}/provider-selection
```

**Switch the active provider for one capability**
```http
PUT /api/v1/workspaces/{workspace_id}/provider-selection
Content-Type: application/json

{ "capability": "email", "provider": "smtp" }
```
The chosen provider is used the next time a worker runs. If no selection exists for a capability, the workspace falls back to the platform default (env-configured).

To route outbound voice calls through Vapi:
```http
PUT /api/v1/workspaces/{workspace_id}/provider-selection
Content-Type: application/json

{ "capability": "voice", "provider": "vapi" }
```

**Smoke-test a stored credential**
```http
POST /api/v1/workspaces/{workspace_id}/provider-credentials/{credential_id}/test
```
Returns `{ ok: bool, provider, channel, detail }`. Only verifies the adapter can be constructed — does not perform a real send.

### Credential storage

Provider API keys are stored encrypted (Fernet) in the `provider_credential` table via:
```http
POST /api/v1/workspaces/{workspace_id}/provider-credentials
{
  "provider": "smtp",
  "channel": "email",
  "api_key": "<smtp-password>",
  "config_json": { "host": "smtp.postmark.app", "port": 587, "from_email": "ops@you.com" }
}
```
Plaintext is never returned. Use the `/test` endpoint to verify.
