$pgData  = "$env:USERPROFILE\scoop\apps\postgresql\current\data"
$pgLog   = "$env:USERPROFILE\postgres.log"
$svcDir  = "$env:USERPROFILE\.local-services"
New-Item -ItemType Directory -Force -Path $svcDir | Out-Null

Write-Host "Starting Postgres..."
pg_ctl -D $pgData -l $pgLog start

Write-Host "Starting Redis..."
Start-Process -FilePath "redis-server" `
    -ArgumentList "--appendonly","yes","--dir",$svcDir `
    -WindowStyle Hidden `
    -RedirectStandardOutput "$svcDir\redis.log" `
    -RedirectStandardError  "$svcDir\redis.err.log"

Write-Host "Starting Mailpit..."
Start-Process -FilePath "mailpit" `
    -ArgumentList "--smtp","0.0.0.0:1025","--listen","0.0.0.0:8025" `
    -WindowStyle Hidden `
    -RedirectStandardOutput "$svcDir\mailpit.log" `
    -RedirectStandardError  "$svcDir\mailpit.err.log"

Start-Sleep -Seconds 2

$pg   = (Test-NetConnection localhost -Port 5432 -InformationLevel Quiet)
$rd   = (Test-NetConnection localhost -Port 6379 -InformationLevel Quiet)
$mp   = (Test-NetConnection localhost -Port 1025 -InformationLevel Quiet)

Write-Host ""
Write-Host "  Postgres  :5432  -> $(if ($pg) { 'UP' } else { 'DOWN' })"
Write-Host "  Redis     :6379  -> $(if ($rd) { 'UP' } else { 'DOWN' })"
Write-Host "  Mailpit   :1025  -> $(if ($mp) { 'UP' } else { 'DOWN' })  (UI: http://localhost:8025)"
Write-Host ""
