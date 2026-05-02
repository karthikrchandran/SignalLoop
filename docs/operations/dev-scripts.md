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
| `API  :8000`  | 8000  | `uv run fastapi dev app/main.py`               |
| `Web  :5173`  | 5173  | `bun run dev`                                  |

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

Force-stops: `fastapi`, `uvicorn`, `bun`, and any Python worker processes.  
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
| API (Swagger)   | http://localhost:8000/docs  |
| API (ReDoc)     | http://localhost:8000/redoc |
| Web frontend    | http://localhost:5173       |
| Mailpit inbox   | http://localhost:8025       |
| Postgres        | localhost:5432 / DB: `engagehub` / User: `postgres` |
| Redis           | localhost:6379              |
