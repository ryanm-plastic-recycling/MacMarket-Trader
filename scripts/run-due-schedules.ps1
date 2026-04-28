$ErrorActionPreference = "Stop"
$repo = "C:\Dashboard\MacMarket-Trader"
$venvPython = Join-Path $repo ".venv\Scripts\python.exe"
$logDir = Join-Path $repo "logs"
$logFile = Join-Path $logDir "scheduler.log"

if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Force -Path $logDir | Out-Null }

$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Add-Content -Path $logFile -Value "[$timestamp] running due strategy schedules"

Push-Location $repo
try {
    & $venvPython -m macmarket_trader.cli run-due-strategy-schedules 2>&1 | Add-Content -Path $logFile
} finally {
    Pop-Location
}
