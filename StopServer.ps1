[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [switch]$StopSharedPostgres,
    [string]$DataDirectory = "$env:USERPROFILE\scoop\persist\postgresql\data",
    [string]$PostgresBin = "$env:USERPROFILE\scoop\apps\postgresql\current\bin"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

foreach ($service in @(
    @{ Name = "Redis"; ProcessName = "redis-server"; Port = 6379 },
    @{ Name = "Mailpit"; ProcessName = "mailpit"; Port = 1025 }
)) {
    $listeners = @(Get-NetTCPConnection -LocalPort $service.Port -State Listen -ErrorAction SilentlyContinue)
    if ($listeners.Count -eq 0) {
        Write-Host "$($service.Name) is already stopped."
        continue
    }
    $processIds = @($listeners | Select-Object -ExpandProperty OwningProcess -Unique)
    foreach ($processId in $processIds) {
        $process = Get-Process -Id $processId
        $scoopRoot = Join-Path $env:USERPROFILE "scoop\apps\"
        if ($process.ProcessName -ne $service.ProcessName -or -not $process.Path.StartsWith($scoopRoot, [StringComparison]::OrdinalIgnoreCase)) {
            throw "Port $($service.Port) belongs to an unexpected process ($processId). It was not stopped."
        }
        if ($PSCmdlet.ShouldProcess("$($service.Name) PID $processId on port $($service.Port)", "Stop local service")) {
            if ($service.Name -eq "Redis") {
                & redis-cli -h 127.0.0.1 -p 6379 shutdown
                if ($LASTEXITCODE -ne 0) { throw "Redis shutdown failed." }
            } else {
                Stop-Process -Id $processId
            }
        }
    }
}

if ($StopSharedPostgres) {
    $pgCtl = Join-Path $PostgresBin "pg_ctl.exe"
    $dataVersion = (Get-Content -LiteralPath (Join-Path $DataDirectory "PG_VERSION") -Raw).Trim()
    $binaryVersion = & $pgCtl --version
    if ($LASTEXITCODE -ne 0 -or $dataVersion -ne "18" -or $binaryVersion -notmatch '\b18\.') {
        throw "PostgreSQL 18 binaries and a version-18 data directory are required."
    }
    if ($PSCmdlet.ShouldProcess($DataDirectory, "Stop PostgreSQL shared by eCRM and SignalLoop")) {
        & $pgCtl -D $DataDirectory -w stop
        if ($LASTEXITCODE -ne 0) { throw "Shared PostgreSQL shutdown failed." }
    }
} else {
    Write-Host "Shared PostgreSQL was left running. Use -StopSharedPostgres only after stopping all dependent apps."
}
