[CmdletBinding()]
param(
  [switch]$SkipPlaywright,
  [switch]$SkipWebBuild
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$ApiDir = Join-Path $RepoRoot "apps/api"
$WebDir = Join-Path $RepoRoot "apps/web"

function Invoke-CheckedStep {
  param(
    [Parameter(Mandatory = $true)]
    [string]$Name,

    [Parameter(Mandatory = $true)]
    [string]$WorkingDirectory,

    [Parameter(Mandatory = $true)]
    [string]$Command,

    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Arguments
  )

  Write-Host ""
  Write-Host "==> $Name"
  Push-Location $WorkingDirectory
  try {
    & $Command @Arguments
    if ($LASTEXITCODE -ne 0) {
      throw "$Name failed with exit code $LASTEXITCODE"
    }
  }
  finally {
    Pop-Location
  }
}

function Test-AlembicSingleHead {
  Write-Host ""
  Write-Host "==> Alembic single-head check"
  Push-Location $ApiDir
  try {
    $heads = & uv run alembic heads 2>&1
    $exitCode = $LASTEXITCODE
    $heads | ForEach-Object { Write-Host $_ }
    if ($exitCode -ne 0) {
      throw "Alembic heads failed with exit code $exitCode"
    }

    $headCount = @($heads | Select-String -Pattern "\(head\)").Count
    if ($headCount -ne 1) {
      throw "Expected exactly one Alembic head, found $headCount"
    }
  }
  finally {
    Pop-Location
  }
}

Invoke-CheckedStep `
  -Name "API ruff check" `
  -WorkingDirectory $ApiDir `
  -Command "uv" `
  run ruff check app/domain/engagement_intelligence tests/unit/test_engagement_intelligence.py

Invoke-CheckedStep `
  -Name "API ruff format check" `
  -WorkingDirectory $ApiDir `
  -Command "uv" `
  run ruff format --check app/domain/engagement_intelligence tests/unit/test_engagement_intelligence.py

Invoke-CheckedStep `
  -Name "API targeted tests" `
  -WorkingDirectory $ApiDir `
  -Command "uv" `
  run pytest tests/unit/test_engagement_intelligence.py tests/unit/test_call_manual_actions.py -q

Test-AlembicSingleHead

Invoke-CheckedStep `
  -Name "Web biome check" `
  -WorkingDirectory $WebDir `
  -Command "npx" `
  biome check --no-errors-on-unmatched --files-ignore-unknown=true src/features/engagehub-ai/api.ts src/features/engagehub-ai/EngageHubAiPage.tsx tests/engagehub-ai.spec.ts

if (-not $SkipPlaywright) {
  Invoke-CheckedStep `
    -Name "Web EngageHub AI Playwright smoke" `
    -WorkingDirectory $WebDir `
    -Command "npx" `
    playwright test tests/engagehub-ai.spec.ts --project=chromium --workers=1 --no-deps
}

if (-not $SkipWebBuild) {
  Invoke-CheckedStep `
    -Name "Web production build" `
    -WorkingDirectory $WebDir `
    -Command "npm" `
    run build
}

Invoke-CheckedStep `
  -Name "Git whitespace check" `
  -WorkingDirectory $RepoRoot `
  -Command "git" `
  diff --check

Write-Host ""
Write-Host "EngageHub release check completed."
