# EngageHub Web

React/Vite operator console for EngageHub.

## Requirements

- [Bun](https://bun.sh/) for frontend package management
- EngageHub API running at `http://localhost:8001`

The backend is managed separately with `uv`; see `apps/api/README.md`.

## Quick Start

From `apps/web`:

```powershell
bun install
bun run dev
```

Open `http://localhost:5173`.

The default API URL is set in `.env` as:

```env
VITE_API_URL=http://localhost:8001
```

## Scripts

```powershell
bun run build
bun run lint
bun run generate-client
bun run test
bun run test:ui
```

## Generate Client

When the backend OpenAPI schema changes, run the API on `http://localhost:8001`, then regenerate the client:

```powershell
bun run generate-client
```

Commit generated client changes with the backend API change.

## Playwright

Start the native local services, API, and web app first:

```powershell
# repo root
.\StartServer.ps1
.\StartApp.ps1
```

Then run Playwright from `apps/web`:

```powershell
bunx playwright test
```

For UI mode:

```powershell
bunx playwright test --ui
```

Playwright uses the repo `.env`, so keep `VITE_API_URL` pointed at `http://localhost:8001`.