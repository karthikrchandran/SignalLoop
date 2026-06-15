---
title: Troubleshooting
description: Known local-development failure modes and how to recover.
date: 2026-05-28
---

# Troubleshooting

If something broke, walk this list top to bottom. Most "I can't run the app" reports are one of the first five entries.

## 1. PowerShell refuses to run `.ps1` scripts

**Symptom:** `cannot be loaded because running scripts is disabled on this system`.

**Fix:** Allow scripts for the current terminal window only:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
```

This resets when the window closes. Do not change machine-wide policy unless you have a reason.

## 2. A port is already in use

**Symptom:** API or web fails to bind to `:8001` / `:5173`, or a Worker window dies immediately.

**Diagnose:**

```powershell
Get-NetTCPConnection -LocalPort 8001 -State Listen -ErrorAction SilentlyContinue |
    Select-Object LocalAddress, LocalPort, OwningProcess | Format-List
```

Replace `8001` with the conflicting port. Map `OwningProcess` to a name with `Get-Process -Id <pid>`.

**Fix:** Either stop the conflicting process, or run `.\StopApp.ps1` to kill stale FastAPI/Vite/worker processes before retrying.

## 3. `Set-Location` drift in a persistent terminal

**Symptom:** Commands run from the wrong directory; `uv` exports land in unexpected paths.

**Fix:** Use absolute paths for `uv --project` and `--output-file`. The persistent terminal's `cwd` can shift between calls if a prior script changed it.

## 4. Database is empty / login fails

**Symptom:** Web app says "invalid email or password" with the credentials you just set in `.env`.

**Fix:**

```powershell
cd apps\api
uv run alembic upgrade head
uv run python -m app.initial_data    # seeds FIRST_SUPERUSER
cd ..\..
uv run seed_db.py                    # optional sample data
```

If `initial_data` reports the user already exists but you still can't log in, your `FIRST_SUPERUSER_PASSWORD` was changed *after* the first seed. The seeding step only inserts; it doesn't update. Either change the password via the API/UI or drop the database and re-seed:

```powershell
dropdb -U postgres signalloop
createdb -U postgres signalloop
cd apps\api
uv run alembic upgrade head
uv run python -m app.initial_data
```

## 5. Alembic migration mismatch after pulling main

**Symptom:** API fails to start with an error mentioning a missing column, table, or revision, or `alembic` reports multiple heads.

**Fix:**

```powershell
cd apps\api
uv run alembic upgrade head
```

If `alembic` reports multiple heads, list them and merge:

```powershell
uv run alembic heads
uv run alembic merge -m "merge heads" <rev1> <rev2>
uv run alembic upgrade head
```

## 6. Postgres is not running

**Symptom:** `connection refused` to `localhost:5432`.

**Fix:**

```powershell
.\StartServer.ps1
```

Or directly:

```powershell
pg_ctl -D "$env:USERPROFILE\scoop\apps\postgresql\current\data" -l postgres.log start
```

Confirm with `Test-NetConnection localhost -Port 5432`.

## 7. Redis is not running

**Symptom:** Worker logs "connection refused" against `redis://localhost:6379/0`.

**Fix:**

```powershell
.\StartServer.ps1
```

Or:

```powershell
redis-server --service-start
```

## 8. Mailpit isn't capturing email

**Symptom:** No mail appears at <http://localhost:8025> after triggering a password reset or transactional email.

**Checks:**

1. `.env` has `SMTP_HOST=localhost` and `SMTP_PORT=1025`.
2. `EMAILS_FROM_EMAIL` is set (otherwise `Settings.emails_enabled` is `false` and no email is attempted).
3. Mailpit is running (`.\StartServer.ps1` reports it UP).

## 9. SECRET_KEY validation error on startup

**Symptom:** API refuses to start with `The value of SECRET_KEY is "changethis"`.

**Fix:** Any non-`local` `ENVIRONMENT` forbids `changethis` for `SECRET_KEY`, `POSTGRES_PASSWORD`, and `FIRST_SUPERUSER_PASSWORD`. Either change those values or set `ENVIRONMENT=local`.

## 10. Provider call fails closed with no obvious error

**Symptom:** Workers run but no email/call ever goes out, and there is no traceback.

**Cause:** The relevant managed-provider key is empty, or the selected local provider process is not running. Adapters fail closed by design when dependencies are absent (see `apps/api/app/infrastructure/`).

**Fix:** For managed providers, populate the relevant `SENDGRID_*`, `TWILIO_*`, `DEEPGRAM_API_KEY`, or `GROQ_API_KEY` in `.env`, then restart the workers (`.\StopApp.ps1` then `.\StartApp.ps1 -Workers`). For local providers, confirm Mailpit, Ollama, and the STT service are listening on ports `1025`, `11434`, and `9000`.

## 11. Ollama is not responding

**Symptom:** The selected LLM provider is `ollama_local`, but summaries or LLM-backed features return empty output.

**Checks:**

1. `Test-NetConnection localhost -Port 11434` returns `TcpTestSucceeded: True`.
2. `ollama list` shows `llama3.2:1b`.
3. `.env` has `OLLAMA_BASE_URL=http://localhost:11434` and `OLLAMA_MODEL=llama3.2:1b`.

**Fix:**

```powershell
ollama pull llama3.2:1b
ollama serve
```

If `ollama serve` says the address is already in use, Ollama is already running.

## 12. Local STT service is not ready

**Symptom:** The selected STT provider is `faster_whisper_local`, but transcription is empty or the worker logs mention `localhost:9000`.

**Checks:**

1. Open <http://localhost:9000/health>.
2. Check `$env:USERPROFILE\.local-services\stt.err.log` if you started with `.\tooling\demo-up.ps1`.
3. First start can take time because faster-whisper dependencies and model files may download.

**Fix:**

```powershell
uv run --with-requirements tooling/stt_service/requirements.txt uvicorn tooling.stt_service.main:app --host 0.0.0.0 --port 9000
```

## 13. Provider Setup is missing from the sidebar

**Symptom:** You can open Settings, but there is no Providers item.

**Cause:** The Providers page is only shown to superusers.

**Fix:** Sign in as the account from `FIRST_SUPERUSER`, or ask an existing superuser to grant the right role.

## 14. Pylance shows hundreds of "unknown" type errors

**Symptom:** The Python language server lights up the codebase with import errors that don't reflect real problems.

**Cause:** VS Code is using the wrong interpreter (system Python instead of the project `.venv` created by `uv`).

**Fix:** Command Palette → `Python: Select Interpreter` → choose `.\.venv\Scripts\python.exe`. Reload window if needed.

## 15. Noisy `__pycache__` changes appear in `git status`

**Cause:** Python wrote bytecode files alongside imports.

**Fix:** Set `PYTHONDONTWRITEBYTECODE=1` for your shell before running Python:

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
```

## 16. `rg` not found in terminal

**Symptom:** `'rg' is not recognized as an internal or external command`.

**Fix:** This workspace doesn't ship ripgrep. Use VS Code's built-in search, or `Select-String` in PowerShell. In Copilot Chat, `grep_search` is the equivalent tool.

## 17. JSON file written by PowerShell breaks a Python parser

**Symptom:** A Python parser rejects a JSON file with `Unexpected UTF-8 BOM`.

**Cause:** `Set-Content -Encoding UTF8` writes a BOM.

**Fix:** Write without BOM:

```powershell
[System.IO.File]::WriteAllText($path, $content, [System.Text.UTF8Encoding]::new($false))
```

## 18. Playwright spec times out

**Common causes:**

1. API or web dev server is not running.
2. Port 5173/8001 is taken by a stale process — `.\StopApp.ps1` then `.\StartApp.ps1`.
3. Database was not seeded; the spec expects fixtures that aren't there. Run `uv run seed_db.py`.
4. First-run delay — Playwright needs to launch the browser; allow a longer timeout on the first run.

## 19. Frontend can't reach the API (CORS or 404)

**Checks:**

1. `apps/web/.env` has `VITE_API_URL=http://localhost:8001` (or your custom port).
2. `BACKEND_CORS_ORIGINS` in root `.env` includes the frontend origin.
3. The API is actually running (`http://localhost:8001/api/v1/utils/health-check/` returns OK).

## When you're stuck

1. `Get-Content apps\api\.cov_run.txt` and any other recent log files in `apps/api/` often have the actual stack trace.
2. Check `_bmad-output/planning-artifacts/` for recent decisions that may explain unexpected behaviour.
3. Capture the exact command, the full output, and your `.env` (with secrets redacted) before asking for help.
