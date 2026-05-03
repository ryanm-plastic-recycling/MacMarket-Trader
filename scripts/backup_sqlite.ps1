param(
  [string]$Database = "macmarket_trader.db",
  [string]$EvidenceDir = ".tmp/evidence"
)

$ErrorActionPreference = "Stop"
python "$PSScriptRoot\backup_sqlite.py" --database $Database --evidence-dir $EvidenceDir
