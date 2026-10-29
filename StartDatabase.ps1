[CmdletBinding()]
param(
    [string]$DataDirectory = "$env:USERPROFILE\scoop\persist\postgresql\data",
    [string]$PostgresBin = "$env:USERPROFILE\scoop\apps\postgresql\current\bin",
    [ValidateRange(1, 65535)]
    [int]$Port = 5432
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$pgCtl = Join-Path $PostgresBin "pg_ctl.exe"
$pgReady = Join-Path $PostgresBin "pg_isready.exe"
$versionFile = Join-Path $DataDirectory "PG_VERSION"
foreach ($path in @($pgCtl, $pgReady, $versionFile)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Required PostgreSQL file not found: $path. No database was initialized or replaced."
    }
}

$dataVersion = (Get-Content -LiteralPath $versionFile -Raw).Trim()
$binaryVersion = & $pgCtl --version
if ($LASTEXITCODE -ne 0 -or $dataVersion -ne "18" -or $binaryVersion -notmatch '\b18\.') {
    throw "PostgreSQL 18 binaries and a version-18 data directory are required. Back up and plan any major-version migration separately."
}

$status = & $pgCtl status -D $DataDirectory 2>&1
$statusCode = $LASTEXITCODE
if ($statusCode -eq 3) {
    $logDirectory = Join-Path $env:USERPROFILE ".local-services"
    New-Item -ItemType Directory -Force -Path $logDirectory | Out-Null
    $previousErrorPreference = $ErrorActionPreference
    try {
        # Windows PowerShell treats pg_ctl's stale-PID warning as a terminating error.
        $ErrorActionPreference = "Continue"
        & $pgCtl -D $DataDirectory -l (Join-Path $logDirectory "postgresql.log") -w -t 90 -o "-h 127.0.0.1 -p $Port" start 2>&1 |
            ForEach-Object { Write-Host "$_" }
        $startCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousErrorPreference
    }
    if ($startCode -ne 0) {
        throw "PostgreSQL failed to start. Inspect $logDirectory\postgresql.log."
    }
} elseif ($statusCode -ne 0) {
    throw "PostgreSQL status check failed with exit code $statusCode."
}

$pidFile = Join-Path $DataDirectory "postmaster.pid"
$serverPort = (Get-Content -LiteralPath $pidFile)[3].Trim()
if ($serverPort -ne "$Port") {
    throw "This PostgreSQL cluster is running on port $serverPort, not requested port $Port. It was not restarted."
}
& $pgReady -h 127.0.0.1 -p $Port -t 5
if ($LASTEXITCODE -ne 0) {
    throw "PostgreSQL is not ready on port $Port."
}
Write-Host "Native PostgreSQL 18 is ready on 127.0.0.1:$Port. Existing databases were preserved."
