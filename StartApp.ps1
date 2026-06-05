param(
    [switch]$Workers   # pass -Workers to also start the three delivery workers
)

$root   = $PSScriptRoot
$apiDir = Join-Path $root "apps\api"
$webDir = Join-Path $root "apps\web"

function Open-Window($title, $workDir, $cmd) {
    Start-Process powershell `
        -ArgumentList "-NoExit","-Command","cd '$workDir'; `$host.UI.RawUI.WindowTitle='$title'; $cmd" `
        -WindowStyle Normal
}

Write-Host "Starting API..."
Open-Window "API  :8001"  $apiDir  "uv run fastapi dev app/main.py --port 8001"

Write-Host "Starting Web..."
Open-Window "Web  :5173"  $webDir  "`$env:VITE_API_URL='http://localhost:8001'; npm run dev"

if ($Workers) {
    Write-Host "Starting workers..."
    Open-Window "Worker: sequence"  $apiDir  "uv run python -m app.workers.sequence_worker"
    Open-Window "Worker: call"      $apiDir  "uv run python -m app.workers.call_worker"
    Open-Window "Worker: postcall"  $apiDir  "uv run python -m app.workers.postcall_worker"
}

Write-Host ""
Write-Host "  API   -> http://localhost:8001   (Swagger: http://localhost:8001/docs)"
Write-Host "  Web   -> http://localhost:5173"
if ($Workers) {
    Write-Host "  Workers: sequence / call / postcall"
}
Write-Host ""
Write-Host "  Tip: use .\StopApp.ps1 to kill all app processes."
Write-Host ""
