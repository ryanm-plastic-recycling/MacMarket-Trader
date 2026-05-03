param(
  [string]$RepoRoot = ".",
  [string]$EvidenceDir = ".tmp/evidence",
  [switch]$DryRun,
  [switch]$MockCommands
)

$ErrorActionPreference = "Stop"
$argsList = @("$PSScriptRoot\run_release_gate.py", "--repo-root", $RepoRoot, "--evidence-dir", $EvidenceDir)
if ($DryRun) {
  $argsList += "--dry-run"
}
if ($MockCommands) {
  $argsList += "--mock-commands"
}
python @argsList
