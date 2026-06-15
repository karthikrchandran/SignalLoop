# Codex Task — Near-Zero-Cost Demo Stack

> Copy this entire file into Codex (or any AI coding agent) as the task prompt.
> The agent should work autonomously; all file paths and decisions are specified below.
> Do NOT ask clarifying questions — follow every decision stated here and raise
> blockers only when a file is missing or a test fails with an unexpected error.

---

## Context

SignalLoop is a FastAPI + SQLModel + PostgreSQL application that does automated
email sequences and AI-powered outbound calling.  The provider layer has been
partially abstracted (registry, capability ABCs, encrypted credentials table)
but several settings fields are missing from `config.py`, the local STT
adapter is not yet implemented, and there is no dev compose service for Ollama
or a seed script for demo-mode provider selections.

The repo root is the working directory for all file operations.

---

## Goals

Implement exactly these six phases so the app runs with zero paid vendor spend
in a local demo:

| # | Phase | Cost target |
|---|---|---|
| 1 | Fix provider config / env fallback | Free |
| 2 | Wire SMTP → Mailcatcher as the free email path | Free local |
| 3 | Wire Ollama as the free LLM path | Free local hardware |
| 4 | Implement `faster_whisper_local` STT adapter | Free local hardware |
| 5 | Add demo orchestration script + seed | Zero spend |
| 6 | Add frontend Provider Setup page (admin) | N/A |

---

## Phase 1 — Fix provider config / env fallback

### 1.1  `apps/api/app/core/config.py`

The `Settings` class is missing new provider env vars.  The old SMTP names
(`SMTP_USER`, `SMTP_TLS`, `EMAILS_FROM_EMAIL`) must be kept for back-compat
because `utils.py` and `compose.override.yml` still use them.  Add the new
names as additional fields with defaults that mirror the old ones.

Add the following fields **after** the `EMAILS_FROM_NAME` field:

```python
# --- New provider-layer SMTP fields (used by SmtpEmailAdapter) ---
SMTP_USERNAME: str | None = None          # alias for SMTP_USER
SMTP_FROM_EMAIL: str | None = None        # alias for EMAILS_FROM_EMAIL
SMTP_FROM_NAME: str | None = None         # alias for EMAILS_FROM_NAME
SMTP_USE_TLS: bool = False                # implicit TLS (port 465)
SMTP_USE_STARTTLS: bool = True            # STARTTLS (port 587)

# --- Ollama local LLM ---
OLLAMA_BASE_URL: str = "http://localhost:11434"
OLLAMA_MODEL: str = "llama3.2:1b"

# --- OpenAI-compatible LLM (also used for OpenRouter / Together via base_url) ---
OPENAI_API_KEY: str = ""
OPENAI_BASE_URL: str = "https://api.openai.com/v1"
OPENAI_MODEL: str = "gpt-4o-mini"

# --- Local faster-whisper STT service ---
FASTER_WHISPER_BASE_URL: str = "http://localhost:9000"
FASTER_WHISPER_MODEL: str = "base"
```

Also add a `@model_validator(mode="after")` (or append to the existing
`_enforce_non_default_secrets` validator) that sets these aliases so both old
and new env names resolve correctly:

```python
@model_validator(mode="after")
def _sync_smtp_aliases(self) -> "Settings":
    if self.SMTP_USERNAME is None and self.SMTP_USER is not None:
        self.SMTP_USERNAME = self.SMTP_USER
    if self.SMTP_FROM_EMAIL is None and self.EMAILS_FROM_EMAIL is not None:
        self.SMTP_FROM_EMAIL = str(self.EMAILS_FROM_EMAIL)
    if self.SMTP_FROM_NAME is None and self.EMAILS_FROM_NAME is not None:
        self.SMTP_FROM_NAME = self.EMAILS_FROM_NAME
    return self
```

### 1.2  `apps/api/app/domain/providers/credential_resolver.py`

In `_settings_fallback`, the SMTP section currently calls
`getattr(settings, "SMTP_FROM_EMAIL", "")` and similar `getattr` guards.
Replace those with direct attribute access now that the fields are declared:

```python
if provider == NotificationProvider.smtp:
    return {
        "host": settings.SMTP_HOST or "",
        "port": settings.SMTP_PORT or 587,
        "username": settings.SMTP_USERNAME or settings.SMTP_USER or "",
        "password": settings.SMTP_PASSWORD or "",
        "from_email": settings.SMTP_FROM_EMAIL or str(settings.EMAILS_FROM_EMAIL or ""),
        "from_name": settings.SMTP_FROM_NAME or settings.EMAILS_FROM_NAME or "",
        "use_tls": settings.SMTP_USE_TLS,
        "use_starttls": settings.SMTP_USE_STARTTLS,
    }
```

Also replace the Ollama and OpenAI `getattr` blocks:

```python
if provider == NotificationProvider.ollama_local:
    return {
        "base_url": settings.OLLAMA_BASE_URL,
        "model": settings.OLLAMA_MODEL,
    }

if provider == NotificationProvider.openai:
    return {
        "api_key": settings.OPENAI_API_KEY,
        "base_url": settings.OPENAI_BASE_URL,
        "model": settings.OPENAI_MODEL,
    }
```

Add a new entry for `faster_whisper_local`:

```python
if provider == NotificationProvider.faster_whisper_local:
    return {
        "base_url": settings.FASTER_WHISPER_BASE_URL,
        "model": settings.FASTER_WHISPER_MODEL,
    }
```

### 1.3  Verification

Run:
```
cd apps/api
uv run pytest tests/ -q --no-header
```
All existing tests must still pass (488+ passing, 0 failed).

---

## Phase 2 — Wire SMTP / Mailcatcher as the free email path

### 2.1  `compose.override.yml`

The file already has a `mailcatcher` service and the api service already
overrides `SMTP_HOST` / `SMTP_PORT` / `SMTP_TLS`.  Add the new-name aliases
to the api service's `environment` block so both old and new names resolve:

```yaml
      SMTP_USE_TLS: "false"
      SMTP_USE_STARTTLS: "false"
      SMTP_FROM_EMAIL: noreply@example.com
      SMTP_FROM_NAME: SignalLoop Demo
```

### 2.2  `apps/api/app/infrastructure/providers/registry.py`

In `PROVIDER_CATALOG`, the `email` capability only lists SendGrid and SMTP.
Update the SMTP entry so it clearly signals it is the local dev option:

```python
{
    "provider": NotificationProvider.smtp.value,
    "label": "Generic SMTP / Mailcatcher (local dev, Gmail, SES SMTP, …)",
    "requires_creds": False,   # env-based for local dev
    "free_tier": "Free (local Mailcatcher or bring-your-own relay)",
    "local": True,
},
```

### 2.3  Verification

No code test needed here — just confirm the compose change is syntactically
valid by running:

```powershell
docker compose -f compose.yml -f compose.override.yml config --quiet
```

If that passes, Phase 2 is done.

---

## Phase 3 — Wire Ollama as the free LLM path

### 3.1  `compose.override.yml`

Add an `ollama` service to the override file.  Insert it after `mailcatcher`:

```yaml
  ollama:
    image: ollama/ollama:latest
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama
    restart: "no"
```

Add `ollama_data` to the top-level `volumes:` section if it does not already exist.

Also add to the `api` service's `environment:`:

```yaml
      OLLAMA_BASE_URL: http://ollama:11434
      OLLAMA_MODEL: llama3.2:1b
```

And add `depends_on` for the api and worker services to wait for ollama
only with `condition: service_started` (Ollama has no health-check):

```yaml
      ollama:
        condition: service_started
```

### 3.2  `apps/api/app/infrastructure/providers/registry.py`

In `PROVIDER_CATALOG`, the `llm` section already lists `ollama_local`.  Change
`requires_creds` to `False` to reflect it needs no stored credential in demo
mode:

```python
{
    "provider": NotificationProvider.ollama_local.value,
    "label": "Ollama (self-hosted — zero cost)",
    "requires_creds": False,
    "free_tier": "Free (your hardware)",
    "local": True,
},
```

### 3.3  Verification

```
cd apps/api
uv run pytest tests/ -q --no-header
```

Still 488+ passing.

---

## Phase 4 — Implement `faster_whisper_local` STT adapter

This is the only **new code** file in this task.  Everything else is config or
small edits.

### 4.1  New file: `apps/api/app/infrastructure/providers/whisper_stt.py`

The adapter hits a lightweight local HTTP wrapper service (see 4.2) rather
than embedding the model inside the API process.  This mirrors how
`OllamaLLMAdapter` works: the heavy process is external, the adapter is thin.

```python
"""Local faster-whisper STT adapter.

Talks to a small HTTP microservice (see tooling/stt_service/) that wraps the
faster-whisper library.  The microservice exposes a single endpoint:

    POST /transcribe
    Content-Type: multipart/form-data
    Body: audio=<WAV/MP3 binary>

    Response JSON: {"text": "...", "language": "en", "duration": 1.23}

For the streaming SttAdapter contract required by the voice realtime pipeline,
this adapter buffers audio chunks in memory and flushes them to the HTTP
endpoint on close(), emitting a single final transcript event.  This is
suitable for post-call transcription (postcall_worker) and non-streaming STT
use cases.  Real-time streaming (voice calls) should continue to use Deepgram
until a streaming-capable local alternative is available.
"""
from __future__ import annotations

import asyncio
import io
import logging
from collections.abc import AsyncGenerator
from typing import Any

import httpx

from app.infrastructure.providers.base import SttAdapter
from app.infrastructure.providers.errors import ProviderConfigurationError

logger = logging.getLogger(__name__)

_DEFAULT_BASE_URL = "http://localhost:9000"
_DEFAULT_MODEL = "base"
_WHISPER_TIMEOUT = httpx.Timeout(120.0, connect=5.0)


class FasterWhisperLocalAdapter(SttAdapter):
    """STT via a local faster-whisper HTTP microservice.

    Audio is buffered in memory during the session and transcribed in one
    batch call when close() is called.  Use this adapter for post-call
    transcription, not real-time voice.
    """

    def __init__(
        self,
        *,
        base_url: str | None = None,
        model: str | None = None,
    ) -> None:
        url = (base_url or _DEFAULT_BASE_URL).rstrip("/")
        if not url:
            raise ProviderConfigurationError(
                "faster_whisper base_url is not configured"
            )
        self._base_url = url
        self._model = model or _DEFAULT_MODEL
        self._buffer: list[bytes] = []
        self._final_transcript: str = ""
        self._closed = False

    # ------------------------------------------------------------------
    # SttAdapter contract
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """No persistent connection; just reset the buffer."""
        self._buffer = []
        self._final_transcript = ""
        self._closed = False

    async def send_audio(self, audio_bytes: bytes) -> None:
        """Buffer incoming audio for batch transcription."""
        if not self._closed:
            self._buffer.append(audio_bytes)

    async def receive_loop(self) -> AsyncGenerator[dict[str, Any], None]:  # type: ignore[override]
        """Yield the final transcript after close() has been called.

        Callers should call close() first, then iterate receive_loop().
        """
        # Wait until the close() coroutine has completed transcription.
        for _ in range(120):  # max 120 * 0.5 s = 60 s
            if self._closed:
                break
            await asyncio.sleep(0.5)

        if self._final_transcript:
            yield {
                "type": "transcript",
                "is_final": True,
                "text": self._final_transcript,
            }

    async def close(self) -> None:
        """Flush buffered audio to the local STT service and store the transcript."""
        if not self._buffer:
            self._closed = True
            return

        audio_blob = b"".join(self._buffer)
        self._buffer = []

        try:
            async with httpx.AsyncClient(timeout=_WHISPER_TIMEOUT) as client:
                resp = await client.post(
                    f"{self._base_url}/transcribe",
                    files={"audio": ("audio.raw", io.BytesIO(audio_blob), "application/octet-stream")},
                    data={"model": self._model},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    self._final_transcript = data.get("text", "").strip()
                    logger.info(
                        "FasterWhisper transcribed %d bytes → %d chars",
                        len(audio_blob),
                        len(self._final_transcript),
                    )
                else:
                    logger.error(
                        "FasterWhisper service error: status=%d body=%s",
                        resp.status_code,
                        resp.text[:200],
                    )
        except httpx.HTTPError:
            logger.exception("FasterWhisper HTTP request failed")
        finally:
            self._closed = True
```

### 4.2  New file: `tooling/stt_service/main.py`

A minimal FastAPI service that loads `faster-whisper` once at startup and
exposes `POST /transcribe`.  This runs as a separate process / container.

```python
"""Local STT microservice — wraps faster-whisper.

Usage:
    pip install fastapi "uvicorn[standard]" faster-whisper
    uvicorn tooling.stt_service.main:app --host 0.0.0.0 --port 9000

Or via docker (see tooling/stt_service/Dockerfile).
"""
from __future__ import annotations

import io
import logging
import os
import tempfile

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)

MODEL_SIZE = os.getenv("WHISPER_MODEL", "base")
DEVICE = os.getenv("WHISPER_DEVICE", "cpu")
COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")

logger.info("Loading faster-whisper model=%s device=%s compute=%s", MODEL_SIZE, DEVICE, COMPUTE_TYPE)
_model = WhisperModel(MODEL_SIZE, device=DEVICE, compute_type=COMPUTE_TYPE)
logger.info("Model loaded.")

app = FastAPI(title="Local STT Service", version="1.0.0")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "model": MODEL_SIZE}


@app.post("/transcribe")
async def transcribe(
    audio: UploadFile = File(...),
    model: str = Form(default=""),
) -> dict:
    """Transcribe uploaded audio file.  Returns {text, language, duration}."""
    data = await audio.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty audio file")

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp.write(data)
        tmp_path = tmp.name

    try:
        segments, info = _model.transcribe(tmp_path, beam_size=5)
        text = " ".join(seg.text.strip() for seg in segments)
        return {
            "text": text,
            "language": info.language,
            "duration": round(info.duration, 2),
        }
    except Exception as exc:
        logger.exception("Transcription failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        import os as _os
        _os.unlink(tmp_path)
```

### 4.3  New file: `tooling/stt_service/Dockerfile`

```dockerfile
FROM python:3.11-slim

WORKDIR /app
RUN pip install --no-cache-dir fastapi "uvicorn[standard]" faster-whisper

COPY main.py .

ENV WHISPER_MODEL=base
ENV WHISPER_DEVICE=cpu
ENV WHISPER_COMPUTE_TYPE=int8

EXPOSE 9000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "9000"]
```

### 4.4  New file: `tooling/stt_service/requirements.txt`

```
fastapi>=0.111,<1
uvicorn[standard]>=0.29,<1
faster-whisper>=1.0,<2
```

### 4.5  Register adapter in `apps/api/app/infrastructure/providers/registry.py`

**Import** — add after the existing imports at the top:

```python
from app.infrastructure.providers.whisper_stt import FasterWhisperLocalAdapter
```

**Factory** — add after `_deepgram_tts_factory`:

```python
def _faster_whisper_factory(creds: dict[str, Any]) -> SttAdapter:
    return FasterWhisperLocalAdapter(
        base_url=creds.get("base_url") or None,
        model=creds.get("model") or None,
    )
```

**Provider map** — add after the deepgram STT entry:

```python
(NotificationProvider.faster_whisper_local, ProviderCapability.stt): _faster_whisper_factory,
```

**Catalog** — add to the `stt` capability list:

```python
{
    "provider": NotificationProvider.faster_whisper_local.value,
    "label": "Faster Whisper Local (zero cost, CPU/GPU)",
    "requires_creds": False,
    "free_tier": "Free (your hardware)",
    "local": True,
},
```

### 4.6  `compose.override.yml`  — add STT service (optional but recommended)

Add an `stt` service after `ollama`:

```yaml
  stt:
    build:
      context: ./tooling/stt_service
      dockerfile: Dockerfile
    ports:
      - "9000:9000"
    environment:
      WHISPER_MODEL: base
      WHISPER_DEVICE: cpu
      WHISPER_COMPUTE_TYPE: int8
    restart: "no"
```

Add to the api service's `environment:`:

```yaml
      FASTER_WHISPER_BASE_URL: http://stt:9000
      FASTER_WHISPER_MODEL: base
```

### 4.7  Verification

Write a new pytest unit test file
`apps/api/tests/infrastructure/providers/test_whisper_stt.py` covering:

1. `FasterWhisperLocalAdapter` raises `ProviderConfigurationError` when
   `base_url=""`.
2. `connect()` then `close()` with no audio sets `_final_transcript=""` and
   `_closed=True`.
3. `connect()` → `send_audio(b"fake")` × 3 → `close()` with mocked httpx
   returning `{"text": "hello world", "language": "en", "duration": 1.0}`:
   - `_final_transcript == "hello world"`.
   - `POST /transcribe` was called once.
4. `close()` with httpx raising `httpx.ConnectError` logs the error and sets
   `_closed=True` without raising.
5. `receive_loop()` yields one event with `is_final=True` and
   `text="hello world"` after a successful `close()`.

Pattern to follow:
- Use `monkeypatch.setattr` on `httpx.AsyncClient` or mock the `post` call
  directly — same pattern as `test_ollama_llm.py` in the same directory.
- Keep the test file free of real network calls.

Run:
```
cd apps/api
uv run pytest tests/infrastructure/providers/test_whisper_stt.py -q
uv run pytest tests/ -q --no-header
```

All tests must pass.

---

## Phase 5 — Demo orchestration script + provider seed

### 5.1  New file: `tooling/seed_demo_providers.py`

A standalone Python script that logs in to the API as the first superuser and
creates `WorkspaceProviderSelection` rows for the three zero-cost providers.
Requires `FIRST_SUPERUSER` / `FIRST_SUPERUSER_PASSWORD` / `API_BASE_URL` to
be in the environment or `.env`.

```python
#!/usr/bin/env python3
"""Seed workspace provider selections for the near-zero demo stack.

Usage (from repo root):
    uv run python tooling/seed_demo_providers.py

Override workspace:
    DEMO_WORKSPACE_ID=my-ws uv run python tooling/seed_demo_providers.py
"""
from __future__ import annotations

import os
import sys
import httpx

API_BASE = os.getenv("API_BASE_URL", "http://localhost:8001")
WS_ID = os.getenv("DEMO_WORKSPACE_ID", "default")
LOGIN_URL = f"{API_BASE}/api/v1/login/access-token"
SELECTION_URL = f"{API_BASE}/api/v1/workspaces/{WS_ID}/provider-selection"

SUPERUSER_EMAIL = os.environ["FIRST_SUPERUSER"]
SUPERUSER_PASSWORD = os.environ["FIRST_SUPERUSER_PASSWORD"]

SELECTIONS = [
    {"capability": "email", "provider": "smtp"},
    {"capability": "llm",   "provider": "ollama_local"},
    {"capability": "stt",   "provider": "faster_whisper_local"},
]


def get_token() -> str:
    resp = httpx.post(
        LOGIN_URL,
        data={"username": SUPERUSER_EMAIL, "password": SUPERUSER_PASSWORD},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def seed(token: str) -> None:
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Workspace-Id": WS_ID,
        "Content-Type": "application/json",
    }
    for sel in SELECTIONS:
        resp = httpx.put(SELECTION_URL, json=sel, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            print(f"  ✓  {data['capability']:8} → {data['provider']}")
        else:
            print(f"  ✗  {sel['capability']} → {sel['provider']}  ({resp.status_code}: {resp.text[:120]})")
            sys.exit(1)


if __name__ == "__main__":
    print(f"Seeding provider selections for workspace '{WS_ID}' at {API_BASE}")
    token = get_token()
    seed(token)
    print("Done. Restart workers for changes to take effect.")
```

### 5.2  New file: `tooling/demo-up.ps1`

PowerShell convenience script that starts the full local demo stack:

```powershell
#!/usr/bin/env pwsh
# demo-up.ps1  —  Start the near-zero-cost local demo stack
# Usage: .\tooling\demo-up.ps1

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Write-Host "`n=== Starting near-zero demo stack ===" -ForegroundColor Cyan

# 1. Bring up all services defined in both compose files
docker compose -f compose.yml -f compose.override.yml up -d --build

Write-Host "`n=== Waiting for API to be healthy ===" -ForegroundColor Cyan
$maxWait = 60
$waited = 0
do {
    Start-Sleep -Seconds 3
    $waited += 3
    $status = docker compose -f compose.yml -f compose.override.yml ps --format json api 2>$null | ConvertFrom-Json
    $health = if ($status) { $status[0].Health } else { "" }
} while ($health -ne "healthy" -and $waited -lt $maxWait)

if ($health -ne "healthy") {
    Write-Warning "API did not become healthy within ${maxWait}s — check logs with: docker compose logs api"
    exit 1
}

Write-Host "`n=== Seeding demo provider selections ===" -ForegroundColor Cyan
& uv run python tooling/seed_demo_providers.py

Write-Host "`n=== Done ===" -ForegroundColor Green
Write-Host "Mailcatcher UI : http://localhost:1080"
Write-Host "API            : http://localhost:8001/docs"
Write-Host "Web            : http://localhost:5173"
Write-Host "Ollama         : http://localhost:11434  (first run pulls model)"
Write-Host "STT service    : http://localhost:9000/health"
```

### 5.3  Verification

Run the unit tests again — no new failures expected here:

```
cd apps/api
uv run pytest tests/ -q --no-header
```

---

## Phase 6 — Frontend Provider Setup page

### Overview

Add a read/write admin page at the route `/settings/providers` under
`apps/web/src/`.  Scan the existing web app structure first (look for how
other admin settings pages are structured, e.g. the runtime config page or
workspace settings) and follow those conventions exactly.

The page must:

1. Call `GET /api/v1/workspaces/{ws}/provider-options` to get the capability catalog.
2. Call `GET /api/v1/workspaces/{ws}/provider-selection` to get the current selections.
3. Render one section per capability: `email`, `llm`, `stt`.
   - Show the currently selected provider.
   - Show a dropdown with all available providers for that capability.
   - On change: call `PUT /api/v1/workspaces/{ws}/provider-selection` and
     refresh the selection state.
4. For each capability show a status badge:
   - **Local** (green) if the selected provider has `local: true`.
   - **Managed** (blue) otherwise.
   - **Not configured** (yellow) if there is no selection yet.
5. Per selected provider, if `requires_creds: true`, show a short inline note:
   "Add credentials via API: `POST /workspaces/{ws}/provider-credentials`"
   (no in-page credential form required in this phase).
6. Show a "Test" button per capability that calls
   `GET /api/v1/workspaces/{ws}/provider-options` again (just to confirm the
   API is responding); a real credential-test button is Phase 7.
7. The page must be accessible only to users with admin role (same guard as
   all other admin pages in the app).

### Files to create/modify

Discover the exact paths by reading the existing routing and component
structure in `apps/web/src/`.  Do NOT hard-code paths; read the router config
and follow existing patterns.

Minimum new files:
- `ProviderSetupPage.tsx` (or `.svelte`, `.vue` — match the framework in use)
- API client function(s) for the three provider endpoints
- A route entry in the router config
- A nav link in the admin sidebar/menu (same pattern as other admin links)
- A unit test file for the page component covering:
  - Renders one section per capability returned by the catalog.
  - Selecting a new provider from the dropdown calls the PUT endpoint.
  - Shows "Local" badge for `local: true` providers.

---

## Completion criteria

The task is done when:

1. `cd apps/api && uv run pytest tests/ -q` passes with 0 failures (≥ 488 tests).
2. `docker compose -f compose.yml -f compose.override.yml config --quiet` exits 0.
3. `tooling/stt_service/main.py` exists and is syntactically valid Python.
4. `apps/api/app/infrastructure/providers/whisper_stt.py` exists.
5. `tooling/seed_demo_providers.py` exists.
6. `tooling/demo-up.ps1` exists.
7. The frontend Provider Setup page component file and route registration exist.
8. Running `tooling/demo-up.ps1` (with Docker available) starts all services
   without error.

---

## Constraints / rules the agent must follow

- **Never remove** the existing `SMTP_TLS`, `SMTP_USER`, or `EMAILS_FROM_EMAIL`
  settings fields — `utils.py` and legacy compose configs still use them.
- **Never remove** the top-level imports of `SendGridAdapter` and
  `TwilioVoiceAdapter` in any worker file — existing tests patch them there.
- **Never** print or log decrypted secrets.
- All new Python files must be importable with `from __future__ import annotations`.
- All new production code must have a matching test or be wired into an existing
  test.  No orphan modules.
- `uv run alembic upgrade head` must still succeed (no schema changes needed
  in this task).
- Follow the test pattern already established in
  `apps/api/tests/infrastructure/providers/test_ollama_llm.py`:
  monkeypatch httpx, no real network calls, no real DB.
