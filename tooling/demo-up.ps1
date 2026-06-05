#!/usr/bin/env pwsh
# Start the local demo stack without Docker.
# Usage: .\tooling\demo-up.ps1

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$apiDir = Join-Path $root "apps\api"
$webDir = Join-Path $root "apps\web"
$svcDir = Join-Path $env:USERPROFILE ".local-services"
New-Item -ItemType Directory -Force -Path $svcDir | Out-Null

function Test-Port($port) {
    return Test-NetConnection localhost -Port $port -InformationLevel Quiet
}

function Wait-Http($url, $seconds) {
    $elapsed = 0
    do {
        try {
            Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 3 | Out-Null
            return $true
        } catch {
            Start-Sleep -Seconds 2
            $elapsed += 2
        }
    } while ($elapsed -lt $seconds)
    return $false
}

function Start-HiddenPowerShell($name, $workDir, $command, $stdout, $stderr) {
    Write-Host "Starting $name..."
    Start-Process powershell `
        -ArgumentList "-NoProfile", "-Command", "Set-Location '$workDir'; $command" `
        -WindowStyle Hidden `
        -RedirectStandardOutput $stdout `
        -RedirectStandardError $stderr
}

Write-Host ""
Write-Host "=== Starting local demo stack ===" -ForegroundColor Cyan

& (Join-Path $root "tooling\mailpit-up.ps1")

if (-not (Test-Port 11434)) {
    $ollama = Get-Command ollama -ErrorAction SilentlyContinue
    if ($ollama) {
        Write-Host "Starting Ollama..."
        Start-Process -FilePath $ollama.Source `
            -ArgumentList "serve" `
            -WindowStyle Hidden `
            -RedirectStandardOutput "$svcDir\ollama.log" `
            -RedirectStandardError "$svcDir\ollama.err.log"
        Start-Sleep -Seconds 3
    } else {
        Write-Warning "Ollama is not installed. Install it from https://ollama.com and pull llama3.2:1b for local LLM demos."
    }
} else {
    Write-Host "Ollama is already listening on :11434."
}
Write-Host "Ollama model    : llama3.2:1b (run 'ollama pull llama3.2:1b' once before LLM demos)"

if (-not (Test-Port 9000)) {
    $sttCommand = "uv run --with-requirements tooling/stt_service/requirements.txt uvicorn tooling.stt_service.main:app --host 0.0.0.0 --port 9000"
    Start-HiddenPowerShell `
        "STT service" `
        $root `
        $sttCommand `
        "$svcDir\stt.log" `
        "$svcDir\stt.err.log"
}

if (-not (Test-Port 8001)) {
    $apiCommand = @"
`$env:SMTP_HOST='localhost';
`$env:SMTP_PORT='1025';
`$env:SMTP_TLS='false';
`$env:SMTP_USE_TLS='false';
`$env:SMTP_USE_STARTTLS='false';
`$env:EMAILS_FROM_EMAIL='noreply@example.com';
`$env:SMTP_FROM_EMAIL='noreply@example.com';
`$env:SMTP_FROM_NAME='EngageHub Demo';
`$env:OLLAMA_BASE_URL='http://localhost:11434';
`$env:OLLAMA_MODEL='llama3.2:1b';
`$env:FASTER_WHISPER_BASE_URL='http://localhost:9000';
`$env:FASTER_WHISPER_MODEL='base';
uv run fastapi dev app/main.py --port 8001
"@
    Start-HiddenPowerShell `
        "API" `
        $apiDir `
        $apiCommand `
        "$svcDir\api.log" `
        "$svcDir\api.err.log"
}

if (-not (Test-Port 5173)) {
    $webCommand = "`$env:VITE_API_URL='http://localhost:8001'; npm run dev"
    Start-HiddenPowerShell `
        "Web" `
        $webDir `
        $webCommand `
        "$svcDir\web.log" `
        "$svcDir\web.err.log"
}

Write-Host ""
Write-Host "=== Waiting for API ===" -ForegroundColor Cyan
if (-not (Wait-Http "http://localhost:8001/api/v1/utils/health-check/" 60)) {
    Write-Warning "API did not become healthy within 60 seconds. Check $svcDir\api.err.log"
    exit 1
}

Write-Host ""
Write-Host "=== Seeding provider selections ===" -ForegroundColor Cyan
& uv run python tooling/seed_demo_providers.py

Write-Host ""
Write-Host "=== Done ===" -ForegroundColor Green
Write-Host "Mailpit inbox : http://localhost:8025"
Write-Host "API docs      : http://localhost:8001/docs"
Write-Host "Web           : http://localhost:5173"
Write-Host "Ollama        : http://localhost:11434"
Write-Host "STT service   : http://localhost:9000/health"
Write-Host "Logs          : $svcDir"
Write-Host ""
