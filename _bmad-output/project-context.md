---
project_name: 'SignalLoop'
user_name: 'K.Ramachandran'
date: '2026-05-28'
sections_completed: ['technology_stack', 'language_rules', 'framework_rules', 'testing_rules', 'quality_rules', 'workflow_rules', 'anti_patterns']
existing_patterns_found: 34
status: 'complete'
rule_count: 80
optimized_for_llm: true
---

# Project Context for AI Agents

_Critical rules and patterns AI agents MUST follow when implementing code in SignalLoop. Focus on unobvious details — assume agents already know general best practices._

---

## Technology Stack & Versions

**Monorepo layout**

- npm workspaces: `apps/web`, `apps/mobile`, `packages/*`
- uv workspace: `apps/api`, `apps/workers`
- Root scripts proxy to `frontend` workspace (`apps/web`). Do NOT add Python scripts to root `package.json`.

**Backend (`apps/api`)** — Python `>=3.10,<4.0`

- FastAPI `>=0.114,<1.0` (with `[standard]` extras), Pydantic `>2.0`, pydantic-settings `>=2.2`
- SQLModel `>=0.0.21`, Alembic `>=1.12`, psycopg `[binary] >=3.1`
- Redis `[hiredis] >=6.4,<7.0`, slowapi `>=0.1.9`, websockets `>=13,<14`
- Auth: pwdlib `[argon2,bcrypt]`, PyJWT `>=2.8`
- Misc: httpx, jinja2, emails, tenacity, cryptography `>=44,<45`, chardet, sentry-sdk `[fastapi] >=2,<3`

**Workers (`apps/workers`)** — uv workspace member; shares Python toolchain with `apps/api`.

**Frontend (`apps/web`)** — Node, TypeScript `^5.9`, React `^19.1`, Vite `^7.3`

- TanStack: react-router `^1.163`, react-query `^5.90`, react-table `^8.21`
- UI: Radix primitives, Tailwind `^4.2` (via `@tailwindcss/vite`), lucide-react, sonner, recharts
- Forms: react-hook-form `^7.68` + zod `^4.3` + `@hookform/resolvers`
- HTTP: axios `1.13.5` (pinned); API client generated via `@hey-api/openapi-ts ^0.73`
- Test: `@playwright/test 1.58.2` (pinned)

**Tooling**

- Python: `uv` (NOT pip/poetry), ruff `>=0.2`, mypy `>=1.8` (`strict = true`), pytest `>=7.4`, coverage `>=7.4`, prek pre-commit
- JS: Biome `^2.3` (lint + format; replaces eslint/prettier)
- Providers (per architecture): SendGrid, Twilio Voice + Media Streams, Deepgram Nova-2 STT / Aura TTS, Groq (Llama 3.1 8B)
- Local services: native Postgres 18, Redis 8, Mailpit (NOT Docker by default)

---

## Critical Implementation Rules

### Language-Specific Rules

**Python (apps/api, apps/workers)**

- `mypy` is `strict = true` — every function needs full type annotations, including return types. `alembic/` is excluded; nothing else is.
- `ruff` selects `T201` → **never use `print()`**. Use the project logger.
- `ruff` selects `ARG001` → no unused function arguments. Prefix with `_` only if mandated by an interface.
- `ruff.target-version = "py310"` and `pyupgrade.keep-runtime-typing = true` — keep `Optional`/`Union` runtime types where used; do NOT rewrite to PEP 604 `X | Y` in code that needs runtime introspection (e.g., SQLModel/Pydantic fields).
- Use `psycopg` v3 APIs (NOT psycopg2). DB driver string is `postgresql+psycopg`.
- Async-first: FastAPI endpoints and worker tasks are `async def`; use `httpx.AsyncClient`, `redis.asyncio`, `websockets`.
- DB sessions: use `AsyncSession` / async engine in async paths. **Never** mix sync `Session` into async code (causes deadlocks under load).
- Money: use `Decimal` end-to-end; SQLModel/Alembic columns are `Numeric(12, 2)`. Never use `float` for monetary values. Money fields in Pydantic schemas are typed `Decimal` (not `float`); never `float(amount)` in domain/crud — convert at the schema boundary.
- Time: `datetime` values are always timezone-aware (`timezone.utc`); Alembic columns are `TIMESTAMP WITH TIME ZONE`. Never persist naive datetimes.
- Exceptions: ruff ignores `B904`, so raising `HTTPException` without `from e` is acceptable; for domain errors still chain with `raise ... from e`.

**TypeScript (apps/web)**

- React **19** + Vite **7** — use the new React APIs (`use`, actions). No `React.FC`; type props inline.
- Module type: `"type": "module"` — all imports are ESM. No `require()`.
- TanStack Router uses **file-based routing** under `src/routes/`. `routeTree.gen.ts` is auto-generated — **never edit by hand**.
- Generated API client lives under `src/client/` (`@hey-api/openapi-ts`). **Never hand-edit** files in `src/client/`; regenerate via `npm run generate-client`. Customizations (axios interceptors, auth headers, error mappers) belong in `src/lib/api-client.ts` wrapper around the generated client — never inside `src/client/`.
- Forms: always `react-hook-form` + `zod` schema + `@hookform/resolvers/zod`. No ad-hoc validation.
- Data fetching: TanStack Query (`useQuery`/`useMutation`) wrapping the generated client. Do NOT call axios directly from components.
- After any backend route/schema change, regenerate the client (`npm run generate-client` in `apps/web`) and commit the updated `src/client/**` in the **same PR**. A PR with backend route changes but no client regen is incomplete.

### Framework-Specific Rules

**FastAPI / Backend layering (`apps/api/app/`)**

- Layer boundaries:
  - `api/` — routers, request/response schemas, dependency-injected services. No business logic.
  - `domain/`, `domain_models.py` — pure business logic and domain types. No FastAPI/SQLModel imports.
  - `crud.py`, `models.py` — persistence (SQLModel tables + repository functions).
  - `infrastructure/` — provider adapters (SendGrid/Twilio/Deepgram/Groq/Redis). One adapter per provider; routers/domain code import the adapter interface, not the SDK directly.
  - `core/` — config, security, logging, dependencies.
  - `workers/` — in-process worker entrypoints; long-running workers live under `apps/workers/worker_app/`.
- Settings via `pydantic-settings` only. Do NOT read `os.environ` directly in app code.
- Rate limiting via `slowapi`. Apply at router level, not inside business logic.
- Sentry is initialized in `main.py`; do not re-init. The `before_send` hook MUST scrub PII (prospect emails, phone numbers, call transcripts, JWTs, API keys). Add new sensitive fields to the scrubber when introduced.
- Webhook endpoints (Twilio, SendGrid Event Webhook) MUST verify provider signatures at the router boundary before any side-effect: Twilio `X-Twilio-Signature` HMAC, SendGrid ECDSA. Reject with 403 on mismatch. Signature alone is NOT replay protection — also dedupe by provider event ID (Twilio `CallSid`+event, SendGrid `sg_event_id`) in Redis/DB before processing.
- Sentry PII scrubbing requires BOTH `before_send` (events) AND `before_breadcrumb` (HTTP/log breadcrumbs). Scrub `Authorization`, `X-API-Key`, and query-string secrets from outbound request breadcrumbs.

**Alembic / Database**

- Every model change requires an Alembic migration. Generate with `uv run alembic revision --autogenerate -m "..."`, then **hand-review** for SQLModel-specific quirks.
- `SQLModel.metadata.create_all(...)` is used in tests and can drift the shared local DB from Alembic history. If `upgrade head` fails with duplicate tables that already exist, verify `alembic current` and `stamp` the matching head rather than dropping tables.
- After any schema/model change: run `uv run alembic upgrade head` from `apps/api` **before** running focused pytest.
- **Never edit or squash an already-applied migration.** Add a new corrective revision instead — shared local/CI/staging DBs all track history by revision id.
- After any SQLModel change, run `uv run alembic revision --autogenerate -m "..."` and verify the generated diff is empty (no drift) or intentional. CI must fail if `alembic revision --autogenerate` produces uncommitted changes.

**React / TanStack**

- Routes are defined by file location in `src/routes/`; use `createFileRoute`. Loaders should call generated client functions, not axios.
- Feature code lives in `src/features/<feature>/`; shared components in `src/components/`. Do NOT colocate feature-specific components in `src/components/`.
- UI primitives are Radix + Tailwind (shadcn-style). Add new primitives via `components.json`/the shadcn CLI rather than hand-rolling.
- Theming via `next-themes`. Use Tailwind v4 CSS-first config (`@theme` in `index.css`), NOT a `tailwind.config.js`.

**Provider Adapter Pattern (voice/email)**

- All external provider calls go through `infrastructure/<provider>_adapter.py`. Domain/sequence engine code must depend on the adapter interface, never the vendor SDK.
- Voice pipeline budget: <500ms round-trip per exchange. New code in the STT→LLM→TTS path must justify any added latency.
- Voice hot path = `apps/api/app/voice/**` (Twilio Media Streams → STT → LLM → TTS → response). Forbidden inside the hot path: synchronous I/O, DB writes, blocking logs, JSON serialization >1KB. Defer audit/analytics writes to background tasks or the worker queue.
- Audio sample rates and Twilio Media Streams chunk sizes (160 bytes / ~20ms) are provider-mandated; the port-policy ban on `8000` does NOT apply to Deepgram `sample_rate=8000`.

**Idempotency & exactly-once**

- Every email send and voice call MUST be idempotent: persist intent (with idempotency key) BEFORE the side-effect; record outcome AFTER.
- Workers must use Redis session locks / DB advisory locks to dedupe concurrent picks of the same `ContactSequenceState` row.
- Every send/call/branching decision MUST emit a structured audit event with a reason code.
- `tenacity` retries apply only to **idempotent** provider calls (GETs, or POSTs carrying a dedup/idempotency key). Use exponential backoff with a hard cap. NEVER wrap retries around a block that holds an open DB transaction.

### Testing Rules

- Run tests with `uv run pytest` from `apps/api` or `apps/workers` (NOT bare `pytest`).
- Tests use the **persistent local Postgres** (`signalloop` DB), not an ephemeral one. Always run `uv run alembic upgrade head` after model changes before focused pytest.
- Set `PYTHONDONTWRITEBYTECODE=1` for any Python run to avoid noisy tracked `__pycache__` changes.
- Coverage config lives in `apps/api/pyproject.toml`; use `uv run coverage run -m pytest && uv run coverage report`. The `_runcov.ps1` helper at repo root is the canonical entry.
- E2E web tests: Playwright (`npm run test` / `test:ui` in `apps/web`). Pinned to `1.58.2` — do NOT bump casually; browser binaries must match.
- Mock provider adapters (SendGrid/Twilio/Deepgram/Groq) at the adapter interface boundary — never patch vendor SDKs deep in tests.
- All provider adapters are mocked by default. Live calls only run under `@pytest.mark.live` AND guarded by env vars (e.g. `RUN_LIVE_TESTS=1` plus the provider credentials). Default `pytest` runs MUST NOT hit real providers.
- Fixture isolation: each test self-cleans the rows it creates (transactional fixtures or explicit teardown). Do NOT add global `TRUNCATE`-everything fixtures — they wipe seed data other tests depend on.
- Playwright parallel workers isolate by tenant/workspace ID derived from `process.env.TEST_WORKER_INDEX`. No worker may read or write another worker's namespace. Never share fixture data across workers.
- Suppress the slowapi asyncio DeprecationWarning via the existing `filterwarnings` entry; do not add broad warning ignores.

### Code Quality & Style Rules

- **Python format/lint:** `uv run ruff format` + `uv run ruff check --fix`. Respect `ignore = [E501, B008, W191, B904]` — line length is not enforced.
- **JS/TS format/lint:** `npm run lint` (`biome check --write --unsafe`). Biome is the single source of truth — do NOT add eslint/prettier configs.
- **Naming:**
  - Python files: `snake_case.py`; classes `PascalCase`; functions/vars `snake_case`.
  - TS/React: components `PascalCase.tsx`; hooks `useThing.ts`; route files match TanStack convention; utilities `camelCase.ts`.
  - DB tables/columns: `snake_case`; Alembic revision messages in imperative mood.
- **Imports:** ruff `I` enforces isort order in Python. In TS, prefer named imports; default-import only for React components and route modules.
- **No dead code / commented-out blocks.** Delete or land behind a feature flag.
- **Logging:** structured JSON with correlation IDs; never log secrets, raw email bodies, or full call transcripts at INFO level.

### Development Workflow Rules

- **Ports (hard constraint):** API → `8001`, web → `5173`. **Forbidden:** `8000`, `3000`, `3001` for app processes. (`8000` is allowed only as a non-port value like Deepgram `sample_rate`.)
- **Local services:** use native Postgres/Redis/Mailpit (scoop-installed). Mailpit SMTP `localhost:1025`, UI `http://localhost:8025`. `.env` must have `SMTP_HOST=localhost`, `SMTP_PORT=1025`, `SMTP_TLS=false` for local.
- **Postgres auth:** local host auth is `scram-sha-256`; the default `changethis` password will be rejected. Use the password set in `.env`.
- **Start/stop:** prefer the root scripts (`StartApp.ps1`/`StopApp.ps1`, `StartServer.ps1`/`StopServer.ps1`) over ad-hoc commands.
- **PowerShell:** use `;` to chain, NEVER `&&`. When writing JSON consumed by Python, write via `[System.IO.File]::WriteAllText(..., [System.Text.UTF8Encoding]::new($false))` to avoid BOM.
- **uv commands:** prefer absolute `uv --project <path>` and `--output-file <path>` because persistent terminal cwd can drift.
- **Search tools:** `rg` may be unavailable on this Windows workspace; use the workspace `grep_search`/`file_search` tools.
- **BMAD artifacts:** planning artifacts in `_bmad-output/planning-artifacts/`, implementation artifacts in `_bmad-output/implementation-artifacts/`. Do not write generated docs to `docs/` without explicit instruction.

### Critical Don't-Miss Rules

- Do NOT use `print()` anywhere in Python code — ruff `T201` will fail CI.
- Do NOT edit `apps/web/src/client/**` or `routeTree.gen.ts` by hand. Regenerate.
- Do NOT call vendor SDKs (SendGrid/Twilio/Deepgram/Groq) outside `apps/api/app/infrastructure/`.
- Do NOT read `os.environ` outside `core/config.py` — go through pydantic-settings.
- Do NOT send an email or place a call without first persisting an idempotency record + audit event.
- Do NOT bind to ports `8000`, `3000`, or `3001`.
- Do NOT introduce MongoDB, pycasbin, or approval-workflow code — these were explicitly removed (see implementation artifacts `1-1`, `1-2`, `1-3`).
- Do NOT use `pip` / `poetry` / `pipenv`; use `uv`. Do NOT use `npx eslint` / `prettier`; use Biome.
- Do NOT drop/recreate local Postgres tables to "fix" alembic drift — `stamp` the correct head instead.
- Do NOT call axios directly from React components or routes — go through the generated client wrapped in TanStack Query.
- Do NOT add latency to the voice STT→LLM→TTS hot path without an explicit budget justification (<500ms total).
- Do NOT mix sync SQLAlchemy `Session` into async paths.
- Do NOT use `float` for monetary values or store naive (tz-less) datetimes.
- Do NOT edit or squash an already-applied Alembic migration — add a corrective revision instead.
- Do NOT accept a Twilio or SendGrid webhook without signature verification.
- Do NOT wrap `tenacity` retries around code that holds an open DB transaction; retry only idempotent provider calls.
- Do NOT merge backend route changes without regenerating and committing `apps/web/src/client/**` in the same PR.
- Do NOT add global `TRUNCATE` fixtures or let tests hit real providers by default — gate live calls behind `@pytest.mark.live` + env vars.
- Edge case: SQLModel `create_all` in tests can shadow Alembic; always run `alembic upgrade head` before focused tests after model changes.
- Security: argon2 (pwdlib) for password hashing — never re-introduce bcrypt-only or plain SHA. Never log JWTs, recordings, or transcripts at INFO. Sentry `before_send` AND `before_breadcrumb` MUST scrub prospect PII (emails, phones, transcripts, secrets, Authorization headers, query-string keys).
- Do NOT process a webhook on signature alone — always dedupe by provider event ID to defeat replay.
- Do NOT type money fields as `float` in Pydantic schemas; use `Decimal` from the boundary inward.
- Do NOT add DB writes, sync I/O, or large JSON serialization inside `apps/api/app/voice/**` — defer to background.
- Do NOT place axios interceptors or auth customizations inside `src/client/**`; put them in `src/lib/api-client.ts`.
- Do NOT merge SQLModel changes without verifying `alembic revision --autogenerate` produces an empty (or intentional) diff.

---

## Usage Guidelines

**For AI Agents:**

- Read this file before implementing any code in SignalLoop.
- Follow ALL rules exactly as documented. When in doubt, prefer the more restrictive option.
- If a rule conflicts with a user instruction, surface the conflict before acting.
- Update this file when new non-obvious patterns emerge (PR a change, do not edit silently).

**For Humans:**

- Keep this file lean — it is loaded into agent context on every task.
- Update when the technology stack, port policy, provider list, or layering changes.
- Review after each epic retrospective; remove rules that became obvious or that the linter now enforces.
- Source-of-truth references: `_bmad-output/planning-artifacts/architecture.md`, `_bmad/bmm/config.yaml`, `/memories/repo/port-policy.md`, `/memories/repo/local-services.md`.

Last Updated: 2026-05-28
