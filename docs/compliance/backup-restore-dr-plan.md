# Backup, Restore, And DR Plan

This plan covers the current local/private-alpha SQLite runtime. It does not
represent an enterprise DR program yet.

## Backup Expectations

- Daily SQLite backup for active alpha runtime.
- Store at least one copy off the primary runtime disk.
- Do not print or copy `.env` secrets into evidence reports.
- Keep backup evidence under `.tmp/evidence/` locally, then move sanitized
  evidence to the chosen evidence archive if needed.

Run:

```powershell
python scripts/backup_sqlite.py --database .\macmarket_trader.db
```

PowerShell wrapper:

```powershell
.\scripts\backup_sqlite.ps1 -Database .\macmarket_trader.db
```

Windows Scheduled Task dry-run helper:

```powershell
.\scripts\schedule_backup_windows_task.ps1
```

The helper prints the scheduled task action by default and does not register
anything unless `-Apply` is passed. Use the dry-run output as review evidence
before enabling unattended backups.

## Restore Drill Expectations

- Monthly restore drill.
- Verify against a temp copy, never overwrite production DB.
- Run SQLite `PRAGMA integrity_check` and schema/table checks.
- Record output evidence JSON/Markdown.

Run:

```powershell
python scripts/verify_sqlite_restore.py --database .\macmarket_trader.db
```

PowerShell wrapper:

```powershell
.\scripts\verify_sqlite_restore.ps1 -Database .\macmarket_trader.db
```

## Disaster Recovery Gaps

- Backup scheduling is now scriptable, but production registration and run
  history evidence remain manual until the task is enabled and reviewed.
- No documented off-site retention location yet.
- No recovery time objective or recovery point objective formally approved.
- No restore drill history until scripts are run on a cadence.
