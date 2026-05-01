$ErrorActionPreference = "Stop"

if (-not ("MacMarketTrader.ConsoleWindow" -as [type])) {
    Add-Type -Name ConsoleWindow -Namespace MacMarketTrader -MemberDefinition @"
[System.Runtime.InteropServices.DllImport("kernel32.dll")]
public static extern System.IntPtr GetConsoleWindow();
[System.Runtime.InteropServices.DllImport("user32.dll")]
public static extern bool ShowWindow(System.IntPtr hWnd, int nCmdShow);
"@
}
$consoleHandle = [MacMarketTrader.ConsoleWindow]::GetConsoleWindow()
if ($consoleHandle -ne [System.IntPtr]::Zero) {
    [MacMarketTrader.ConsoleWindow]::ShowWindow($consoleHandle, 0) | Out-Null
}

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
