$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
$apiRoot = Join-Path $repoRoot 'apps/api'
$webRoot = Join-Path $repoRoot 'apps/web'
$workspaceId = if ($env:PLAYWRIGHT_WORKSPACE_ID) { $env:PLAYWRIGHT_WORKSPACE_ID } else { 'default' }

$health = Invoke-RestMethod -UseBasicParsing -Uri 'http://127.0.0.1:8001/api/v1/utils/health-check/'
if (-not $health.api -or -not $health.postgres -or -not $health.redis) {
  throw 'Local API health check failed. Ensure the backend and local services are running on port 8001.'
}

Push-Location $repoRoot
try {
  $env:PYTHONDONTWRITEBYTECODE = '1'
  uv run seed_db.py | Out-Null
} finally {
  Pop-Location
}

Push-Location $apiRoot
try {
  $tokenOutput = uv run python scripts/issue_playwright_token.py
  if (-not $tokenOutput) {
    throw 'Failed to issue a Playwright access token.'
  }
  $token = $tokenOutput.Trim()
} finally {
  Pop-Location
}

$env:PLAYWRIGHT_ACCESS_TOKEN = $token
$env:PLAYWRIGHT_WORKSPACE_ID = $workspaceId

Push-Location $webRoot
try {
  npx playwright test tests/corrective-live-smoke.spec.ts --project=chromium --workers=1 --no-deps
} finally {
  Pop-Location
}