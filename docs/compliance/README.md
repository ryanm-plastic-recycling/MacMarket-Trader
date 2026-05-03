# Compliance Readiness Evidence Index

This directory is an internal readiness and evidence layer for MacMarket-Trader.
It does not claim SOC 2, ISO 27001, SEC, FINRA, or banking compliance.

MacMarket-Trader's current product boundary remains:

- paper/research-only
- no live trading
- no broker routing
- no automated exits
- no discretionary account management
- LLMs explain and summarize; deterministic systems own trade fields and risk gates

## Evidence Set

- [Control Matrix](control-matrix.md)
- [Risk Register](risk-register.md)
- [Vendor Inventory](vendor-inventory.md)
- [Data Classification And Retention](data-classification-retention.md)
- [Incident Response Plan](incident-response-plan.md)
- [Change And Release Management](change-release-management.md)
- [Backup, Restore, And DR Plan](backup-restore-dr-plan.md)
- [Model Risk Management](model-risk-management.md)
- [Model Inventory](model-inventory.md)
- [Model Validation Report Template](model-validation-report-template.md)
- [Regulatory Boundary Memo](regulatory-boundary-memo.md)
- [Acquisition Readiness](acquisition-readiness.md)
- [Evidence Manifest Template](evidence-manifest-template.md)
- [Access Review Template](access-review-template.md)
- [Vendor Review Template](vendor-review-template.md)
- [Incident Tabletop Template](incident-tabletop-template.md)

## Evidence Generation

Local evidence artifacts should be written under `.tmp/evidence/`, which is
ignored by git and excluded from deployment/shareable archives.

Run the repeatable release gate:

```powershell
python scripts/run_release_gate.py
```

Fast dry-run for CI/test evidence wiring:

```powershell
python scripts/run_release_gate.py --dry-run --mock-commands
```

Useful commands:

```powershell
python scripts/check_conflict_markers.py --root .
python scripts/scan_secrets.py --root .
python scripts/check_release_artifact.py --source .
python scripts/run_model_validation.py --database .\macmarket_trader.db
python scripts/generate_release_evidence.py
python scripts/backup_sqlite.py --database .\macmarket_trader.db
python scripts/verify_sqlite_restore.py --database .\macmarket_trader.db
python scripts/create_clean_release_archive.py --dry-run
```

Runtime release gate output includes:

- `.tmp/evidence/release-gate-YYYYMMDD-HHMMSS.json`
- `.tmp/evidence/release-gate-YYYYMMDD-HHMMSS.md`
- `.tmp/evidence/evidence-manifest.json`

## Current Gaps

- These documents are readiness artifacts, not third-party attestations.
- Backup and restore drills need recurring dated evidence.
- Access, vendor, and incident tabletop templates still require human review
  and sign-off.
- Vendor contract, SLA, DPA, and security reviews are placeholders until formal review.
- Model validation evidence is preliminary and test/replay based.
- Legal review is required before public/commercial investment-advice use.
