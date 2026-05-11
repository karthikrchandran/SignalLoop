# EngageHub API

FastAPI backend for EngageHub campaign orchestration, authentication, governance, provider adapters, and background workers.

## Requirements

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) for Python package and environment management
- Local Postgres and Redis started through the repo root scripts or equivalent native services

Docker Compose is optional and is not the default local workflow for this workspace.

## Local Setup

From `apps/api`:

```powershell
uv sync
uv run alembic upgrade head
uv run python -m app.initial_data
uv run fastapi dev app/main.py --port 8001
```

The API is available at `http://localhost:8001`. The health check is:

```text
http://localhost:8001/api/v1/utils/health-check/
```

## Workers

Run workers from `apps/api` in separate terminals when testing delivery flows:

```powershell
uv run python -m app.workers.sequence_worker
uv run python -m app.workers.call_worker
uv run python -m app.workers.postcall_worker
```

The root `StartApp.ps1 -Workers` script runs the same worker commands for you.

## Tests

Run backend tests with pytest through `uv`:

```powershell
uv run pytest
```

Focused examples:

```powershell
uv run pytest tests/unit/test_config.py
uv run pytest tests/api/routes/test_contacts.py
```

## Migrations

Apply migrations:

```powershell
uv run alembic upgrade head
```

Create a new migration after model changes:

```powershell
uv run alembic revision --autogenerate -m "describe change"
```

## Email Templates

Email templates live under `app/email-templates`. Source templates go in `src`; built HTML templates go in `build`.