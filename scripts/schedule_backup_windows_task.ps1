param(
  [string]$TaskName = "MacMarket-SQLite-Backup",
  [string]$RepoRoot = (Resolve-Path ".").Path,
  [string]$Database = "macmarket_trader.db",
  [string]$EvidenceDir = ".tmp/evidence",
  [string]$At = "02:15",
  [switch]$Apply
)

$ErrorActionPreference = "Stop"

$backupScript = Join-Path $RepoRoot "scripts\backup_sqlite.ps1"
$arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$backupScript`" -Database `"$Database`" -EvidenceDir `"$EvidenceDir`""

Write-Host "Task name: $TaskName"
Write-Host "Working directory: $RepoRoot"
Write-Host "Program: powershell.exe"
Write-Host "Arguments: $arguments"
Write-Host "Schedule: daily at $At"

if (-not $Apply) {
  Write-Host "Dry run only. Re-run with -Apply to register or update the scheduled task."
  exit 0
}

$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $arguments -WorkingDirectory $RepoRoot
$trigger = New-ScheduledTaskTrigger -Daily -At $At
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Description "MacMarket SQLite backup evidence task" -Force | Out-Null
Write-Host "Scheduled task registered: $TaskName"
