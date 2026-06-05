#!/usr/bin/env pwsh
# Start the local Mailpit SMTP inbox without Docker.
# Usage: .\tooling\mailpit-up.ps1

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$mailpit = Get-Command mailpit -ErrorAction SilentlyContinue
if (-not $mailpit) {
    Write-Error "Mailpit is not installed. Install it with: scoop install mailpit"
    exit 1
}

$svcDir = Join-Path $env:USERPROFILE ".local-services"
New-Item -ItemType Directory -Force -Path $svcDir | Out-Null

$smtpUp = Test-NetConnection localhost -Port 1025 -InformationLevel Quiet
$webUp = Test-NetConnection localhost -Port 8025 -InformationLevel Quiet

if ($smtpUp -and $webUp) {
    Write-Host "Mailpit is already running."
    Write-Host "  SMTP : localhost:1025"
    Write-Host "  UI   : http://localhost:8025"
    exit 0
}

Write-Host "Starting Mailpit..."
Start-Process -FilePath $mailpit.Source `
    -ArgumentList "--smtp", "0.0.0.0:1025", "--listen", "0.0.0.0:8025" `
    -WindowStyle Hidden `
    -RedirectStandardOutput "$svcDir\mailpit.log" `
    -RedirectStandardError "$svcDir\mailpit.err.log"

Start-Sleep -Seconds 2

$smtpUp = Test-NetConnection localhost -Port 1025 -InformationLevel Quiet
$webUp = Test-NetConnection localhost -Port 8025 -InformationLevel Quiet

Write-Host ""
Write-Host "  Mailpit SMTP :1025 -> $(if ($smtpUp) { 'UP' } else { 'DOWN' })"
Write-Host "  Mailpit UI   :8025 -> $(if ($webUp) { 'UP' } else { 'DOWN' })"
Write-Host "  Inbox        : http://localhost:8025"
Write-Host ""

if (-not ($smtpUp -and $webUp)) {
    Write-Warning "Mailpit did not start cleanly. Check $svcDir\mailpit.err.log"
    exit 1
}
