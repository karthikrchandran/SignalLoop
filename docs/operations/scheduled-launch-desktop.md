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
  -> local Redis
  -> local Ollama
  -> optional local faster-whisper
  -> Cloudflare Tunnel

Managed services
  -> Neon Free PostgreSQL
  -> customer-owned SMTP or Amazon SES
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
| LLM drafting | Ollama on the desktop | $0 API cost |
| Secure public ingress | Cloudflare Tunnel | $0 |
| Email | Customer SMTP or low-volume SES | $0-$2 |
| Electricity | Four-to-six-hour operating window | $2-$8 |
| Domain | Existing domain preferred | $0-$2 equivalent |
| Monitoring and backup tools | Local and existing storage | $0 |
| **Expected total** |  | **$2-$15 per month** |

Code-generation LLM usage on the development laptop is excluded from this
operating estimate. LLM use inside the customer workflow, including proposal
and email drafting, is included through local Ollama.

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
will be slow for transcription and larger models.

### Recommended

- Eight or more modern CPU cores.
- 32 GB RAM.
- 250 GB free SSD space.
- NVIDIA GPU with at least 8 GB VRAM, if available.
- Wired Ethernet.
- Uninterruptible power supply if the local power supply is unreliable.

An NVIDIA GPU is helpful but not required. A CPU-only desktop with 32 GB RAM
can run a quantized 8B model, but proposal generation will take longer.

### Preferred for faster local AI

- 64 GB RAM.
- NVIDIA GPU with 12 GB or more VRAM.
- 500 GB available SSD space.

Do not buy new hardware solely for the first launch partner until the existing
desktop has been tested with the real workload.

## Accounts to prepare

Create or identify:

1. A private Git repository account with read access from the desktop.
2. A Neon account protected by multi-factor authentication.
3. A Cloudflare account and a domain managed by Cloudflare DNS.
4. A customer-approved SMTP relay, or an Amazon SES account.
5. An off-machine backup destination, such as an existing encrypted cloud drive
   or external disk.

Do not share personal master passwords with the customer. Create separate
service credentials and store them only on the launch desktop.

## Software to install on the desktop

Install:

- Git.
- Node.js 20 or later and npm.
- Python 3.11.
- `uv`.
- Docker Desktop with the WSL 2 backend.
- Ollama for Windows.
- `cloudflared`.
- PostgreSQL client tools for `pg_dump` and `pg_restore`.

Only the PostgreSQL client tools are required. Do not install or start a local
PostgreSQL server when Neon is the launch database.

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
OLLAMA_MODEL=qwen3:8b

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

## Local transcription

The existing faster-whisper service is suitable for batch or post-call
transcription. It is not a complete replacement for real-time streaming voice.

Leave transcription and voice workers disabled for the first launch unless the
launch workflow requires them. This reduces CPU use and operational risk.

Do not claim live AI calling unless the customer supplies the required provider
account and the complete call path has been verified.

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

For live email sequences, start the sequence worker in a separate PowerShell
window:

```powershell
uv run python -m app.workers.sequence_worker
```

Do not start the call or post-call workers unless those workflows are in the
approved launch scope.

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
7. Start only the required workers.
8. Check the local health endpoint:

   ```powershell
   Invoke-RestMethod http://127.0.0.1:8001/api/v1/utils/health-check/
   ```

9. Sign in locally and perform one read-only application smoke test.
10. Start Cloudflare Tunnel.
11. Verify the public web and API health URLs from a different device.
12. Tell the launch customer the operating window has started.

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
- One temporary outage would not create material customer harm.
- Manual support remains manageable.
- The launch customer understands the environment's limitations.

Upgrade the database or hosting when any of these occurs:

- The first meaningful recurring payment is received.
- The customer needs unattended or 24/7 operation.
- Database storage or compute approaches the free limit.
- Backup retention must exceed the free restore window.
- More than one customer depends on the same desktop.
- The workflow handles material financial, regulated, or high-risk data.
- Desktop or home-network failures begin affecting customer outcomes.

The first paid upgrade should usually be managed application hosting and a paid
database tier. Do not buy enterprise tools before revenue or risk justifies
them.
