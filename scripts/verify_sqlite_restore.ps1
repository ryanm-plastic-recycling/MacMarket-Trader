param(
  [string]$Database = "macmarket_trader.db",
  [string]$EvidenceDir = ".tmp/evidence"
)

$ErrorActionPreference = "Stop"
python "$PSScriptRoot\verify_sqlite_restore.py" --database $Database --evidence-dir $EvidenceDir
