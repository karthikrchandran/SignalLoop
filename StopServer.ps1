$pgData = "$env:USERPROFILE\scoop\apps\postgresql\current\data"

Write-Host "Stopping Postgres..."
pg_ctl -D $pgData stop

Write-Host "Stopping Redis..."
Get-Process -Name "redis-server" -ErrorAction SilentlyContinue | Stop-Process -Force

Write-Host "Stopping Mailpit..."
Get-Process -Name "mailpit" -ErrorAction SilentlyContinue | Stop-Process -Force

Write-Host ""
Write-Host "  All services stopped."
Write-Host ""
