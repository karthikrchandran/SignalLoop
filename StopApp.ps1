$targets = @("fastapi", "bun", "uvicorn")

foreach ($name in $targets) {
    $procs = Get-Process -Name $name -ErrorAction SilentlyContinue
    if ($procs) {
        $procs | Stop-Process -Force
        Write-Host "  Stopped: $name"
    }
}

# Stop local Vite/npm frontend processes launched from this workspace.
Get-CimInstance Win32_Process |
    Where-Object {
        $_.Name -eq "node.exe" -and
        $_.CommandLine -like "*eMailVoice*" -and
        ($_.CommandLine -like "*vite*" -or $_.CommandLine -like "*apps*web*")
    } |
    ForEach-Object {
        Stop-Process -Id $_.ProcessId -Force
        Write-Host "  Stopped: node frontend"
    }

# Also stop any uv-spawned Python worker processes
Get-Process -Name "python" -ErrorAction SilentlyContinue |
    Where-Object { $_.MainWindowTitle -match "Worker" } |
    Stop-Process -Force

Write-Host ""
Write-Host "  All app processes stopped."
Write-Host "  (Infrastructure still running - use .\StopServer.ps1 to stop Postgres/Redis/Mailpit)"
Write-Host ""
