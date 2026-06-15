---
title: Developer Onboarding & Handover
description: Day-one setup for a new SignalLoop engineer.
date: 2026-05-28
---

# Developer Onboarding & Handover

This guide takes a new engineer from a fresh Windows laptop to a fully running SignalLoop stack with passing tests. It is written for the actual repository on disk — no assumed cloud accounts and no production credentials.

## 1. Prerequisites

Install in this order. Versions listed are the minimum that has been verified.

| Tool | Version | Install (Windows) |
| --- | --- | --- |
| Git | 2.40+ | `scoop install git` |
| Python | 3.10+ | `scoop install python` |
| `uv` (Python package manager) | latest | `scoop install uv` or `pipx install uv` |
| Node.js | 20+ | `scoop install nodejs-lts` |
| npm | 10+ | bundled with Node |
| PostgreSQL | 14+ | `scoop install postgresql` |
| Redis | any recent | `scoop install redis` (Windows port) |
| Mailpit | latest | `scoop install mailpit` (or download from mailpit.axllent.org) |
| Ollama | latest | optional for local LLM demos; install from ollama.com |
| VS Code | latest | optional but recommended; workspace is tuned for it |
| PowerShell | 5.1 or 7 | preinstalled on Windows |

Confirm with:

```powershell
git --version
python --version
uv --version
node --version
npm --version
psql --version
redis-server --version
ollama --version
```

## 2. Clone the repository

```powershell
cd $env:USERPROFILE
git clone <repo-url> eMailVoice
cd eMailVoice
```

> All paths in this guide assume the repo root is `eMailVoice`. Adjust if you cloned to a different folder.

## 3. Configure your environment file

Copy the example file and edit values you care about.

```powershell
Copy-Item .env.example .env
```

Required edits for a local-only run:

- `SECRET_KEY` — set to any non-default string (the API refuses to start with `changethis` outside `ENVIRONMENT=local` and warns even in local).
- `POSTGRES_PASSWORD` — set to your local Postgres password.
- `FIRST_SUPERUSER_PASSWORD` — set to a memorable test password (you will log in with this).

Optional (only if you need that feature):

- `SENDGRID_API_KEY`, `SENDGRID_FROM_EMAIL` — outbound email via SendGrid.
- `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER` — outbound voice.
- `VAPI_API_KEY`, `VAPI_PHONE_NUMBER_ID`, `VAPI_ASSISTANT_ID` — managed AI voice via Vapi.
- `DEEPGRAM_API_KEY` — call transcription.
- `GROQ_API_KEY` — post-call summarisation.

Local-only provider values are safe to leave in `.env`: `SMTP_*` can point at Mailpit, `OLLAMA_*` points at the local Ollama server, and `FASTER_WHISPER_*` points at the local STT helper service. Do not add paid provider keys until you have registered for those services.

All provider adapters fail closed when keys are absent, so the stack boots cleanly with only the required edits above. See [environment-variables.md](./environment-variables.md) for the full list and meaning of every variable.

## 4. Start infrastructure (Postgres, Redis, Mailpit)

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\StartServer.ps1
```

The script prints UP/DOWN status for each port. All three must be UP before continuing. See [docs/operations/dev-scripts.md](../operations/dev-scripts.md) for what each script does.

## 5. Install dependencies and run migrations

Backend:

```powershell
cd apps\api
uv sync
uv run alembic upgrade head
uv run python -m app.initial_data    # seeds the FIRST_SUPERUSER account
cd ..\..
```

Frontend:

```powershell
cd apps\web
npm install
cd ..\..
```

## 6. Seed a small sample dataset (optional but recommended)

```powershell
uv run seed_db.py
```

This populates the database with sample contacts, templates, and a draft campaign so the UI has something to render on first login.

## 7. Start the app

```powershell
.\StartApp.ps1
```

Two PowerShell windows open: `API :8001` and `Web :5173`. Add `-Workers` to also launch the sequence/call/postcall workers — only needed when testing delivery.

Open the browser and verify:

- API docs: <http://localhost:8001/docs>
- API health: <http://localhost:8001/api/v1/utils/health-check/>
- Web app: <http://localhost:5173>
- Mailpit inbox: <http://localhost:8025>

Log in with the email from `FIRST_SUPERUSER` and the password you set in `FIRST_SUPERUSER_PASSWORD`.

### Start the near-zero demo stack

For the local-only demo path, use the helper script instead of starting each provider by hand:

```powershell
ollama pull llama3.2:1b      # run once after installing Ollama
.\tooling\demo-up.ps1
```

This starts Mailpit, attempts to start Ollama, starts the faster-whisper STT service with `uv`, starts the API and web app, then seeds provider selections for the default workspace. After signing in as a superuser, open `Settings -> Providers` to confirm `smtp`, `ollama_local`, and `faster_whisper_local` are selected.

## 8. Run the smoke tests

Backend smoke (fast subset):

```powershell
cd apps\api
uv run pytest -q tests/api/routes/test_health.py
```

Frontend smoke (Playwright):

```powershell
cd apps\web
npm test -- tests/sequences.spec.ts tests/voice-agents.spec.ts
```

Both should report green. If either fails, see [troubleshooting.md](./troubleshooting.md).

## 9. Stop everything cleanly

End-of-day shutdown:

```powershell
.\StopApp.ps1
.\StopServer.ps1
```

## 10. What to read next

- [Codebase tour](./codebase-tour.md) — understand the layout before you start making changes.
- [Testing guide](./testing.md) — the full test menu (unit, integration, smoke, coverage).
- [Architecture overview](../architecture/README.md) — system context, data model, process flows.
- The active BMAD sprint plan under `_bmad-output/planning-artifacts/` — the canonical "what are we building right now".

## Handover checklist (outgoing engineer)

Use this when handing the project to someone else. Pair with the new engineer for one session to walk through each item.

- [ ] Confirm the recipient has access to the Git remote and any provider accounts they will own.
- [ ] Share the latest `.env` values via a secrets vault (never commit). Include the seeded superuser email and password being used in dev.
- [ ] Walk through `_bmad-output/planning-artifacts/` — current PRD, epics, sprint status.
- [ ] Walk through any open PRs and their review state.
- [ ] Walk through the entries in `docs/runbooks/` (operational procedures). If empty, capture at least one runbook for the most-recent production incident or release.
- [ ] Walk through the in-flight tickets and where they're blocked.
- [ ] Walk the recipient through steps 4-8 above on their machine, end to end.
- [ ] Add the recipient as a maintainer on the repository and any CI/CD systems.
- [ ] Remove your access only after the recipient confirms they can deploy and rollback.
