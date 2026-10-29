Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$svcDir  = "$env:USERPROFILE\.local-services"
New-Item -ItemType Directory -Force -Path $svcDir | Out-Null

Write-Host "Starting Postgres..."
& (Join-Path $PSScriptRoot "StartDatabase.ps1")

Write-Host "Starting Redis..."
if (-not (Test-NetConnection 127.0.0.1 -Port 6379 -InformationLevel Quiet -WarningAction SilentlyContinue)) {
    Start-Process -FilePath "redis-server" `
        -ArgumentList "--bind","127.0.0.1","--appendonly","yes","--dir","`"$svcDir`"" `
        -WindowStyle Hidden `
        -RedirectStandardOutput "$svcDir\redis.log" `
        -RedirectStandardError  "$svcDir\redis.err.log"
}

Write-Host "Starting Mailpit..."
if (-not (Test-NetConnection 127.0.0.1 -Port 1025 -InformationLevel Quiet -WarningAction SilentlyContinue)) {
    Start-Process -FilePath "mailpit" `
        -ArgumentList "--smtp","127.0.0.1:1025","--listen","127.0.0.1:8025" `
        -WindowStyle Hidden `
        -RedirectStandardOutput "$svcDir\mailpit.log" `
        -RedirectStandardError  "$svcDir\mailpit.err.log"
}

Start-Sleep -Seconds 2

$pg   = (Test-NetConnection 127.0.0.1 -Port 5432 -InformationLevel Quiet)
$rd   = (Test-NetConnection 127.0.0.1 -Port 6379 -InformationLevel Quiet)
$mp   = (Test-NetConnection 127.0.0.1 -Port 1025 -InformationLevel Quiet)

Write-Host ""
if (-not ($pg -and $rd -and $mp)) {
    throw "One or more local infrastructure services are unavailable. Inspect logs in $svcDir."
}
$redisReply = & redis-cli -h 127.0.0.1 -p 6379 ping
if ($LASTEXITCODE -ne 0 -or "$redisReply".Trim() -ne "PONG") {
    throw "Redis did not respond to PING on 127.0.0.1:6379."
}
$mailpitReady = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:8025/readyz" -TimeoutSec 5
if ($mailpitReady.StatusCode -ne 200) {
    throw "Mailpit is not ready on 127.0.0.1:8025."
}
Write-Host "  Postgres  :5432  -> $(if ($pg) { 'UP' } else { 'DOWN' })"
Write-Host "  Redis     :6379  -> $(if ($rd) { 'UP' } else { 'DOWN' })"
Write-Host "  Mailpit   :1025  -> $(if ($mp) { 'UP' } else { 'DOWN' })  (UI: http://localhost:8025)"
Write-Host ""
