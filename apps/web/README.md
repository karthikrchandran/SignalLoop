# SignalLoop Web

React/Vite operator console for SignalLoop.

## Requirements

- Node.js 20+ and npm for frontend package management
- SignalLoop API running at `http://localhost:8001`

The backend is managed separately with `uv`; see `apps/api/README.md`.

## Quick Start

From `apps/web`:

```powershell
npm install
npm run dev
```

Open `http://localhost:5173`.

Superusers can review local provider choices at `Settings -> Providers` after the API is running. The local demo stack seeds Mailpit, Ollama, and faster-whisper selections with:

```powershell
# repo root
.\tooling\demo-up.ps1
```

The default API URL is set in `.env` as:

```env
VITE_API_URL=http://localhost:8001
```

## Scripts

```powershell
npm run build
npm run lint
npm run generate-client
npm run test
npm run test:ui
```

## Generate Client

When the backend OpenAPI schema changes, regenerate the checked-in OpenAPI
input directly from the FastAPI application. This does not start the API, its
database lifecycle, or any provider connections:

```powershell
npm run export-openapi
npm run generate-client
```

`npm run check-openapi` fails when the checked-in input is missing or stale.
Run it in CI before client generation. Commit `openapi.json` and generated
client changes with the backend API change.

The current generator is pinned in `package-lock.json`. Run it with Node 22
or 24 LTS; Node 25 is not a supported reproducible generation runtime.

## Playwright

Start the native local services, API, and web app first:

```powershell
# repo root
.\StartServer.ps1
.\StartApp.ps1
```

Then run Playwright from `apps/web`:

```powershell
npx playwright test
```

For UI mode:

```powershell
npx playwright test --ui
```

Playwright uses the repo `.env`, so keep `VITE_API_URL` pointed at `http://localhost:8001`.
