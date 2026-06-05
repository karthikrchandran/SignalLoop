# Dev Scripts — Start & Stop Reference

Four PowerShell scripts at the repo root manage the full local dev environment.  
Run them from the repo root: `c:\Users\K.Ramachandran\eMailVoice\`

> **First-time requirement:** Allow script execution in your terminal session before running any `.ps1` file:
> ```powershell
> Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
> ```
> This only needs to be set once per terminal window — it resets automatically when the window closes.

---

## Infrastructure Scripts

These control the background services that the app depends on (database, cache, email capture).

### `StartServer.ps1` — Start Postgres, Redis, Mailpit

```powershell
.\StartServer.ps1
```

| Service  | Port  | Purpose                              |
|----------|-------|--------------------------------------|
| Postgres | 5432  | Primary database                     |
| Redis    | 6379  | Task queue and session cache         |
| Mailpit  | 1025  | SMTP capture (web UI: :8025)         |

After running, the script prints UP/DOWN status for each port so you can confirm all three are healthy.

**Mailpit web UI:** http://localhost:8025 — all outgoing dev emails appear here.

---

### `tooling\mailpit-up.ps1` - Start Mailpit only

```powershell
.\tooling\mailpit-up.ps1
```

Use this when you only need local email capture. It starts Mailpit on SMTP port `1025` and web UI port `8025`, reusing the same log folder as the other local scripts: `$env:USERPROFILE\.local-services`.

---

### `tooling\demo-up.ps1` - Start the near-zero local demo stack

```powershell
.\tooling\demo-up.ps1
```

This no-Docker helper starts Mailpit, attempts to start Ollama, starts the faster-whisper STT service with `uv`, starts the API and web app, then runs `tooling\seed_demo_providers.py` to select the local providers for the default workspace.

Run once before LLM demos:

```powershell
ollama pull llama3.2:1b
```

The script expects Postgres and Redis to be available locally. It does not install paid provider credentials.

---

### `StopServer.ps1` — Stop Postgres, Redis, Mailpit

```powershell
.\StopServer.ps1
```

Gracefully stops all three infrastructure services. Run this at end of day or before a system restart.

> Stopping infrastructure while the app is running will cause DB/Redis connection errors. Always run `StopApp.ps1` first.

---

## App Scripts

These launch (or kill) the application processes — API server, web frontend, and background workers.

### `StartApp.ps1` — Start API + Web (+ optional Workers)

**Basic usage — API and web only:**
```powershell
.\StartApp.ps1
```

Opens two named PowerShell windows:
| Window title  | Port  | Command                                        |
|---------------|-------|------------------------------------------------|
| `API  :8001`  | 8001  | `uv run fastapi dev app/main.py --port 8001`   |
| `Web  :5173`  | 5173  | `npm run dev`                                  |

**With delivery workers:**
```powershell
.\StartApp.ps1 -Workers
```

Opens five named PowerShell windows (the two above plus):
| Window title        | Purpose                                              |
|---------------------|------------------------------------------------------|
| `Worker: sequence`  | Sends SendGrid email sequences to contacts           |
| `Worker: call`      | Places Twilio outbound calls (daily cap: 50, quiet hours enforced) |
| `Worker: postcall`  | Transcribes recordings (Deepgram) + AI summary (Groq) |

Each process runs in its own window so you can read live logs. Close a window to stop that process individually.

**When to use `-Workers`:**  
Only needed when actively testing email delivery, voice calls, or post-call processing.  
For UI/API development, the basic `.\StartApp.ps1` is sufficient.

---

### `StopApp.ps1` — Stop All App Processes

```powershell
.\StopApp.ps1
```

Force-stops: `fastapi`, `uvicorn`, local Vite/Node frontend processes, and any Python worker processes.
Infrastructure (Postgres, Redis, Mailpit) is **not** affected — use `StopServer.ps1` for those.

---

## Typical Workflows

### Normal dev day
```powershell
# Morning — start everything
.\StartServer.ps1
.\StartApp.ps1

# Evening — shut down
.\StopApp.ps1
.\StopServer.ps1
```

### Testing workers (email/call features)
```powershell
.\StartServer.ps1
.\StartApp.ps1 -Workers
# ... test ...
.\StopApp.ps1
.\StopServer.ps1
```

### Restart app only (e.g. after a code change that hot-reload missed)
```powershell
.\StopApp.ps1
.\StartApp.ps1          # or .\StartApp.ps1 -Workers
```

---

## URLs at a Glance

| Service         | URL                        |
|-----------------|----------------------------|
| API (Swagger)   | http://localhost:8001/docs  |
| API (ReDoc)     | http://localhost:8001/redoc |
| Web frontend    | http://localhost:5173       |
| Mailpit inbox   | http://localhost:8025       |
| Ollama          | http://localhost:11434      |
| STT service     | http://localhost:9000/health |
| Postgres        | localhost:5432 / DB: `engagehub` / User: `postgres` |
| Redis           | localhost:6379              |
