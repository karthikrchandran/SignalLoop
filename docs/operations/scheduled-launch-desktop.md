# Scheduled Launch Desktop Setup

## Purpose

This guide describes a low-cost launch environment for SignalLoop when:

- Development and testing happen on a Windows laptop.
- A separate Windows desktop runs the customer-facing application.
- The desktop is available for an agreed four-to-six-hour operating window.
- The launch customer pays little or nothing.
- Personal cash burn must remain close to zero.

This is a controlled launch-partner environment, not a 24/7 production platform.
It prioritizes a clean boundary, recoverability, and predictable cost.

## Recommended architecture

```text
Development laptop
  -> source code, tests, and reviewed commits
  -> private Git repository

Launch desktop
  -> checked-out release commit
  -> built web application
  -> FastAPI API and required workers
  -> real-time voice-session orchestration
  -> local Redis
  -> local Ollama
  -> optional local faster-whisper
  -> Cloudflare Tunnel

Managed services
  -> Neon Free PostgreSQL
  -> customer-owned SMTP or Amazon SES
  -> Twilio telephone calls and media streams
  -> Deepgram streaming speech-to-text and text-to-speech
  -> Groq low-latency conversational LLM
```

The laptop must not connect directly to the launch database during normal
development. Use a separate local database or a separate Neon development
project on the laptop.

## Why Neon is recommended

SignalLoop already uses PostgreSQL through SQLModel, SQLAlchemy, Alembic, and
the `psycopg` driver. Replacing PostgreSQL with a different database would
require application and migration changes without reducing immediate cost.

Neon and Supabase are both managed PostgreSQL services. Choosing Neon means
PostgreSQL remains the database engine, but no PostgreSQL server needs to run
on the desktop.

Neon is the recommended launch choice because:

- It is a direct fit for the existing application.
- Its Free plan scales inactive compute to zero.
- Its Free plan is designed for intermittent development and demo workloads.
- The application does not currently need Supabase Auth, Storage, or Realtime.
- It keeps database management separate from the launch desktop.

As of July 2026, Neon Free includes 100 compute-unit hours and 0.5 GB storage
per project. Neon gives an example of approximately three hours per day at an
average of one compute unit. Database compute is active only while queries are
running, so a four-to-six-hour application window can still fit when usage is
light and intermittent. Verify current limits before creating the project:

https://neon.com/pricing

### When Supabase is reasonable

Supabase Free is an acceptable alternative if SignalLoop later adopts its Auth,
Storage, or Realtime capabilities. Its Free plan currently includes a 500 MB
database, but free projects can pause after one week of inactivity and do not
include automatic backups.

Do not migrate application authentication or storage to Supabase merely to use
its database. That would increase scope without lowering the current cost.

https://supabase.com/pricing

## Expected monthly cash cost

| Item | Launch choice | Expected cost |
|---|---|---:|
| Web, API, and workers | Launch desktop | $0 |
| Database | Neon Free | $0 |
| Redis | Local container | $0 |
| Proposal and email drafting | Ollama on the desktop | $0 API cost |
| Secure public ingress | Cloudflare Tunnel | $0 |
| Email | Customer SMTP or low-volume SES | $0-$2 |
| Twilio local number | Launch voice number | About $1.15 |
| Live AI voice usage | Twilio + Deepgram + Groq | About $0.04-$0.08/call minute |
| Electricity | Four-to-six-hour operating window | $2-$8 |
| Domain | Existing domain preferred | $0-$2 equivalent |
| Monitoring and backup tools | Local and existing storage | $0 |
| **Expected fixed total** | Before live call minutes | **$3-$16 per month** |

Code-generation LLM usage on the development laptop is excluded from this
operating estimate. LLM use inside the customer workflow, including proposal
and email drafting, is included through local Ollama. Live voice is a required
variable expense because telephone transport and low-latency speech services
cannot be provided reliably by the desktop alone.

Use these initial voice allowances:

| Included live-call allowance | Planning range |
|---|---:|
| 100 minutes/month | $4-$8 |
| 500 minutes/month | $20-$40 |
| 1,000 minutes/month | $40-$80 |

These are planning ranges, not guaranteed prices. Confirm destination-specific
rates and current provider pricing before launch:

- https://www.twilio.com/en-us/voice/pricing/us
- https://deepgram.com/pricing
- https://groq.com/pricing

## Desktop requirements

### Minimum

- Windows 11 Pro or a supported Windows 11 edition.
- Four modern CPU cores.
- 16 GB RAM.
- 100 GB free SSD space.
- Stable wired or Wi-Fi internet.
- Ability to disable sleep during the operating window.
- Administrator access for initial software installation.

This minimum is suitable for the application and a small 4B local model. It
is also suitable for real-time voice orchestration because Twilio, Deepgram,
and Groq perform the latency-sensitive voice processing remotely.

### Recommended

- Eight or more modern CPU cores.
- 32 GB RAM.
- 250 GB free SSD space.
- Wired Ethernet.
- Uninterruptible power supply if the local power supply is unreliable.

No GPU is required for the recommended live AI voice stack. A CPU-only desktop
with 32 GB RAM can run a quantized 8B model for non-real-time proposal and
email drafting, but generation will take longer.

### Optional upgrade for faster local drafting

- 64 GB RAM.
- NVIDIA GPU with 12 GB or more VRAM.
- 500 GB available SSD space.

This optional upgrade affects local drafting speed. It is not required for
real-time AI calls. Do not buy new hardware solely for the first launch partner
until the existing desktop has been tested with the real workload.

## Accounts to prepare

Create or identify:

1. A private Git repository account with read access from the desktop.
2. A Neon account protected by multi-factor authentication.
3. A Cloudflare account and a domain managed by Cloudflare DNS.
4. A customer-approved SMTP relay, or an Amazon SES account.
5. A Twilio account with a voice-capable number.
6. A Deepgram account for streaming speech-to-text and text-to-speech.
7. A Groq account for the real-time conversational LLM.
8. An off-machine backup destination, such as an existing encrypted cloud drive
   or external disk.

Do not share personal master passwords with the customer. Create separate
service credentials and store them only on the launch desktop. Prefer
customer-owned Twilio and high-volume provider accounts when practical.

## Software to install on the desktop

Install:

- Git.
- Node.js 20 or later and npm.
- Python 3.11.
- `uv`.
- Docker Desktop with the WSL 2 backend.
- Ollama for Windows for non-real-time drafting.
- `cloudflared`.
- PostgreSQL client tools for `pg_dump` and `pg_restore`.

Only the PostgreSQL client tools are required. Do not install or start a local
PostgreSQL server when Neon is the launch database.

Twilio, Deepgram, and Groq are external APIs. They do not require GPU drivers
or local model installation. SignalLoop connects to them using provider
credentials.

### Do not install for the initial launch

Do not install:

- A local PostgreSQL server. Neon is the system of record.
- NVIDIA CUDA or other GPU runtimes when the desktop has no supported GPU.
- A locally hosted real-time conversational LLM.
- A locally hosted telephony server or SIP carrier.
- An internet-facing SMTP server.
- Kubernetes.
- The faster-whisper service solely for live voice; Deepgram supplies streaming
  STT. Install faster-whisper later only if batch/post-call transcription is
  required.

After installation, open a new PowerShell window and verify:

```powershell
git --version
node --version
npm --version
python --version
uv --version
docker version
ollama --version
cloudflared --version
pg_dump --version
```

## Prepare the Neon database

1. Create one Neon project for the launch environment.
2. Name it clearly, for example `signalloop-launch`.
3. Keep autoscaling conservative and scale-to-zero enabled.
4. Copy the host, port, database, user, and password separately.
5. Do not store the full connection string in source control or documentation.
6. Enable multi-factor authentication on the Neon account.

SignalLoop currently builds its database URI from separate environment values:

```env
POSTGRES_SERVER=<neon-host>
POSTGRES_PORT=5432
POSTGRES_DB=<neon-database>
POSTGRES_USER=<neon-user>
POSTGRES_PASSWORD=<neon-password>
```

Use the connection values issued by Neon. Do not copy example values.

Neon requires encrypted database connectivity. The current `psycopg` connection
negotiates TLS with the Neon endpoint. Before broader customer use, add explicit
`sslmode=require` support to the application configuration so the requirement
is visible and testable rather than implicit.

### Apply migrations

From `apps/api` on the desktop:

```powershell
uv sync --frozen
uv run alembic upgrade head
uv run python -m app.initial_data
```

Run migrations only from the checked-out release commit. Back up the launch
database before applying future migrations.

## Create the launch environment file

Create `.env` in the repository root on the desktop. Never commit it.

Use this structure and replace every placeholder:

```env
PROJECT_NAME=SignalLoop
ENVIRONMENT=production
SECRET_KEY=<long-random-secret>
FIRST_SUPERUSER=<launch-admin-email>
FIRST_SUPERUSER_PASSWORD=<unique-long-password>

FRONTEND_HOST=https://app.<your-domain>
SERVER_HOST=api.<your-domain>
BACKEND_CORS_ORIGINS=["https://app.<your-domain>"]
VITE_API_URL=https://api.<your-domain>

POSTGRES_SERVER=<neon-host>
POSTGRES_PORT=5432
POSTGRES_DB=<neon-database>
POSTGRES_USER=<neon-user>
POSTGRES_PASSWORD=<neon-password>

REDIS_URL=redis://127.0.0.1:6379/0

OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen3:4b

TWILIO_ACCOUNT_SID=<twilio-account-sid>
TWILIO_AUTH_TOKEN=<twilio-auth-token>
TWILIO_PHONE_NUMBER=<twilio-e164-phone-number>
DEEPGRAM_API_KEY=<deepgram-api-key>
GROQ_API_KEY=<groq-api-key>

SMTP_HOST=<customer-or-ses-smtp-host>
SMTP_PORT=587
SMTP_USER=<smtp-user>
SMTP_PASSWORD=<smtp-password>
EMAILS_FROM_EMAIL=<approved-sender-address>
SMTP_FROM_EMAIL=<approved-sender-address>
SMTP_FROM_NAME=SignalLoop
SMTP_USE_TLS=false
SMTP_USE_STARTTLS=true
```

Generate secrets with a password manager. Do not use `changethis`, reuse a
personal password, or copy secrets from the development laptop.

Restrict `.env` permissions to the Windows account that runs SignalLoop.

Use `qwen3:4b` on a 16 GB desktop. Change `OLLAMA_MODEL` to `qwen3:8b` after
confirming the desktop has 32 GB RAM and the draft response time is acceptable.

## Start local Redis

Redis is ephemeral coordination state, not the system of record. Keep it local
on the launch desktop.

Create the container once:

```powershell
docker run -d `
  --name signalloop-redis `
  --restart no `
  -p 127.0.0.1:6379:6379 `
  -v signalloop-redis-data:/data `
  redis:7 redis-server --appendonly yes
```

On later operating days:

```powershell
docker start signalloop-redis
```

Binding to `127.0.0.1` prevents Redis from being exposed to the local network.

## Prepare local proposal drafting

Install Ollama from its official Windows distribution, then pull:

```powershell
ollama pull qwen3:8b
```

Use `qwen3:4b` if the desktop has 16 GB RAM or if 8B generation is too slow:

```powershell
ollama pull qwen3:4b
```

Qwen3 open-weight models use the Apache 2.0 license:

https://github.com/QwenLM/Qwen3

The model may draft:

- Proposal narrative.
- Follow-up messages.
- Summaries.
- Plain-language explanations.

The model must not calculate or approve:

- Prices.
- Quantities.
- Tax.
- Margin.
- Discounts.
- Contract terms.
- Payment instructions.

Those values must come from deterministic application logic and require human
approval before sending.

The repository's current local default is `llama3.2:1b`. It is suitable for a
small demo but is not the recommended customer-facing proposal model.

## Configure live AI voice

Live AI voice is part of the launch environment. Use the direct provider stack
already represented in SignalLoop:

```text
Twilio call
  -> Twilio Media Stream
  -> SignalLoop authenticated WebSocket
  -> Deepgram streaming speech-to-text
  -> Groq conversational LLM
  -> Deepgram streaming text-to-speech
  -> Twilio caller audio
```

In `Settings -> Providers`, configure the launch workspace with:

| Capability | Provider |
|---|---|
| `voice` | `twilio` |
| `stt` | `deepgram` |
| `tts` | `deepgram` |
| `llm` | `groq` |

The API uses `SERVER_HOST` to construct the public Twilio callback and secure
WebSocket URLs. Set it to the public API hostname without a scheme:

```env
SERVER_HOST=api.<your-domain>
```

The required public routes are:

| Purpose | Route |
|---|---|
| Call instructions | `https://api.<your-domain>/api/v1/voice/twiml` |
| Status callback | `https://api.<your-domain>/api/v1/voice/status` |
| Recording callback | `https://api.<your-domain>/api/v1/voice/recording` |
| Live media | `wss://api.<your-domain>/api/v1/voice/media-stream` |

The media-stream route validates the call, account, and signed stream token
before performing provider work. Do not bypass that validation.

Set a low initial call budget:

- Maximum one simultaneous call.
- Maximum 10 test calls per day.
- Maximum 100 live minutes for the first billing month.
- Approved destinations only.
- Manual campaign activation.
- Immediate stop on opt-out, repeated provider failure, or budget exhaustion.

The existing faster-whisper service remains useful for batch and post-call
transcription. It is not a replacement for Deepgram streaming STT during live
calls. Local Ollama is for non-real-time drafting; it is not the conversational
LLM for live calls on a CPU-only desktop.

Before customer operation, complete one measured live call through the entire
Twilio -> Deepgram -> Groq -> Deepgram -> Twilio path. Mocked tests and provider
configuration alone are not sufficient evidence.

## Configure email

Use this order of preference:

1. Customer-owned Microsoft 365, Google Workspace, or approved SMTP relay.
2. Amazon SES using the customer's domain.
3. Mailpit only for demonstrations where messages must not leave the desktop.

SMTP is a protocol, not a sending reputation service. Do not operate an
internet-facing SMTP server from the desktop.

For a live domain, configure SPF, DKIM, and DMARC. Start at low volume and
require human approval. The generic SMTP adapter sends messages but does not
provide the full SendGrid webhook and event-normalization behavior. Verify what
delivery, bounce, and reply tracking the launch workflow actually needs.

## Build the web application

Build on the launch desktop from the reviewed release commit:

```powershell
Set-Location apps\web
npm ci
$env:VITE_API_URL = "https://api.<your-domain>"
npm run build
Set-Location ..\..
```

The build output is `apps/web/dist`.

The current `StartApp.ps1` starts the Vite development server and the API with
reload enabled. Do not use it for the launch environment.

Until a dedicated launch script is added, serve the built web image locally:

```powershell
docker build `
  -f apps/web/Dockerfile `
  --build-arg VITE_API_URL=https://api.<your-domain> `
  --build-arg NODE_ENV=production `
  -t signalloop-web:launch .

docker run -d `
  --name signalloop-web `
  --restart no `
  -p 127.0.0.1:5173:80 `
  signalloop-web:launch
```

Rebuild the image for each reviewed release.

## Start the API and required workers

From `apps/api`, start the API without reload:

```powershell
uv run python -m uvicorn app.main:app `
  --host 127.0.0.1 `
  --port 8001 `
  --workers 1
```

Start the call worker in a separate PowerShell window. It is required for the
launch voice agent:

```powershell
uv run python -m app.workers.call_worker
```

For live email sequences, start the sequence worker in another window:

```powershell
uv run python -m app.workers.sequence_worker
```

Start the post-call worker only when the approved workflow includes recordings,
summaries, or operator notifications:

```powershell
uv run python -m app.workers.postcall_worker
```

The first implementation task after this guide is approved should create
production start, stop, status, and backup scripts so these commands do not
depend on memory or manual window management.

## Configure Cloudflare Tunnel

Cloudflare Tunnel makes outbound-only connections from the desktop and avoids
opening inbound router or firewall ports:

https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/

Create one named tunnel and two public hostnames:

| Public hostname | Local service |
|---|---|
| `app.<your-domain>` | `http://127.0.0.1:5173` |
| `api.<your-domain>` | `http://127.0.0.1:8001` |

The API hostname must support both HTTPS callbacks and secure WebSocket traffic.
Twilio connects to the `wss://` media-stream route generated by the API.

Do not publish Redis, Ollama, the STT service, Docker, database ports, API
documentation, or operating-system administration ports.

Protect administrative access through the application login. Consider
Cloudflare Access in front of the launch environment when the customer user
list is small and known.

Do not install the tunnel as an always-running Windows service for the initial
scheduled model. Start it only after the application passes local health
checks, and stop it at the end of the operating window.

## Start-of-window procedure

Run these steps in order:

1. Confirm the desktop is on wired power and sleep is disabled temporarily.
2. Confirm the expected release commit:

   ```powershell
   git status --short
   git rev-parse --short HEAD
   ```

3. Start Redis.
4. Start Ollama.
5. Start the built web container.
6. Start the API.
7. Start the call worker and any other required workers.
8. Check the local health endpoint:

   ```powershell
   Invoke-RestMethod http://127.0.0.1:8001/api/v1/utils/health-check/
   ```

9. Sign in locally and perform one read-only application smoke test.
10. Confirm the provider-readiness screen shows Twilio, Deepgram, Groq, Redis,
    public callbacks, and the call worker as ready.
11. Start Cloudflare Tunnel.
12. Verify the public web, API health, HTTPS callback, and secure WebSocket
    reachability from outside the desktop.
13. Place one approved test call.
14. Tell the launch customer the operating window has started.

If any required health check fails, do not start the tunnel.

## End-of-window procedure

1. Pause campaigns and new work.
2. Allow the sequence worker to finish or stop cleanly.
3. Confirm no work remains in a running state.
4. Stop Cloudflare Tunnel first.
5. Stop the API and workers.
6. Stop the web container:

   ```powershell
   docker stop signalloop-web
   ```

7. Stop Redis:

   ```powershell
   docker stop signalloop-redis
   ```

8. Create and verify the database backup.
9. Re-enable normal desktop sleep settings.
10. Record incidents, failed sends, and manual corrections.

## Backup and restore

Neon's short Free-plan restore window is useful but is not the only backup.

Create one logical database backup after each operating window:

```powershell
$backupStamp = Get-Date -Format "yyyyMMdd-HHmmss"
pg_dump `
  --format=custom `
  --no-owner `
  --no-privileges `
  --file="D:\SignalLoopBackups\signalloop-$backupStamp.dump" `
  "postgresql://<user>:<password>@<host>/<database>?sslmode=require"
```

Do not place the password directly in reusable scripts. Store the connection
string in an access-controlled environment variable or password-manager
workflow when backup automation is implemented.

Keep:

- The most recent seven operating-window backups.
- At least one encrypted copy off the launch desktop.
- A monthly restore-test record.

Test restoration into a separate Neon branch or separate recovery database.
Never test a restore over the active launch database.

## Deployment boundary

Use this release flow:

1. Make changes on the laptop.
2. Run the relevant tests on the laptop.
3. Commit the reviewed scope.
4. Push the commit to the private remote.
5. On the desktop, stop public access and back up the database.
6. Fetch the exact release commit.
7. Install locked dependencies.
8. Apply migrations.
9. Rebuild the web image.
10. Start locally and complete health checks.
11. Start the tunnel.

Do not edit application source directly on the launch desktop. Emergency
configuration changes must be recorded and later incorporated into the normal
release process.

## Security rules

- Never expose ports 5432, 6379, 11434, or 9000 publicly.
- Never commit `.env`, database dumps, customer exports, recordings, or API
  credentials.
- Use unique launch credentials and multi-factor authentication.
- Run the desktop with a dedicated non-administrator Windows account after
  installation is complete.
- Enable BitLocker or equivalent full-disk encryption.
- Apply Windows security updates outside the customer operating window.
- Keep Windows Firewall enabled.
- Disable unused workers and provider credentials.
- Require approval before proposal, email, discount, invoice, or payment
  actions.
- Set low daily sending and activity limits.
- Keep the customer informed that availability is scheduled rather than 24/7.

## Launch verification checklist

- [ ] Laptop and desktop use different database projects.
- [ ] Desktop runs a reviewed release commit with a clean worktree.
- [ ] `.env` contains no default secrets.
- [ ] Neon migrations complete successfully.
- [ ] Redis listens only on `127.0.0.1`.
- [ ] Ollama is not publicly reachable.
- [ ] Qwen3 produces an acceptable draft from approved facts.
- [ ] Proposal totals remain deterministic and human-approved.
- [ ] Twilio, Deepgram, and Groq use launch-specific credentials.
- [ ] Voice, STT, TTS, and LLM provider selections are correct.
- [ ] The call worker reports a current heartbeat.
- [ ] Public Twilio callback URLs use the expected API hostname.
- [ ] The authenticated `wss://` media-stream route is reachable.
- [ ] A real end-to-end test call has acceptable latency and clean teardown.
- [ ] Daily call-count and minute limits are configured.
- [ ] The web application is built rather than served by Vite development mode.
- [ ] The API runs without reload.
- [ ] Only required workers are running.
- [ ] Local API health check passes.
- [ ] Cloudflare exposes only the web and API services.
- [ ] Login and tenant boundaries work through the public URL.
- [ ] Test email uses an approved sender.
- [ ] Daily send limits are configured.
- [ ] Database backup completes.
- [ ] A restore test has been performed in an isolated database.
- [ ] Start and stop procedures have been rehearsed.

## Upgrade triggers

Stay on the scheduled desktop and Neon Free only while all of these remain true:

- Availability is explicitly scheduled.
- Database storage remains below 400 MB.
- Neon usage remains below 75 compute-unit hours per month.
- Voice usage remains within the funded monthly allowance.
- One temporary outage would not create material customer harm.
- Manual support remains manageable.
- The launch customer understands the environment's limitations.

Upgrade the database or hosting when any of these occurs:

- The first meaningful recurring payment is received.
- The customer needs unattended or 24/7 operation.
- Database storage or compute approaches the free limit.
- Voice usage becomes material enough to require customer-owned credentials,
  negotiated rates, or pass-through billing.
- Backup retention must exceed the free restore window.
- More than one customer depends on the same desktop.
- The workflow handles material financial, regulated, or high-risk data.
- Desktop or home-network failures begin affecting customer outcomes.

The first paid upgrade should usually be managed application hosting and a paid
database tier. Do not buy enterprise tools before revenue or risk justifies
them.
