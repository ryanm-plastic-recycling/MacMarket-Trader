"""Create a local SQLite backup plus sanitized evidence report."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
from datetime import UTC, datetime
from pathlib import Path


DEFAULT_EVIDENCE_DIR = Path(".tmp") / "evidence"


def timestamp() -> str:
    return datetime.now(tz=UTC).strftime("%Y%m%d-%H%M%S")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sqlite_summary(path: Path) -> dict[str, object]:
    conn = sqlite3.connect(path)
    try:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
    finally:
        conn.close()
    return {
        "integrity_check": integrity[0] if integrity else "unknown",
        "table_count": len(tables),
        "tables": [row[0] for row in tables],
    }


def write_reports(report: dict[str, object], *, evidence_dir: Path, stem: str) -> dict[str, Path]:
    evidence_dir.mkdir(parents=True, exist_ok=True)
    json_path = evidence_dir / f"{stem}.json"
    md_path = evidence_dir / f"{stem}.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(
        "\n".join(
            [
                f"# SQLite Backup Evidence {report['timestamp']}",
                "",
                f"- Source: `{report['source_database']}`",
                f"- Backup: `{report['backup_path']}`",
                f"- Integrity check: `{report['sqlite']['integrity_check']}`",
                f"- Tables: `{report['sqlite']['table_count']}`",
                f"- Source bytes: `{report['source_bytes']}`",
                f"- Backup SHA-256: `{report['backup_sha256']}`",
                "",
                "Secrets and environment files are not read or written by this backup evidence script.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return {"json": json_path, "markdown": md_path}


def backup_sqlite_database(
    database: Path,
    *,
    evidence_dir: Path = DEFAULT_EVIDENCE_DIR,
    backup_dir: Path | None = None,
) -> dict[str, object]:
    source = database.resolve()
    if not source.exists():
        raise FileNotFoundError(f"SQLite database not found: {source}")
    if not source.is_file():
        raise ValueError(f"SQLite database path is not a file: {source}")

    stamp = timestamp()
    backup_root = (backup_dir or (evidence_dir / "backups")).resolve()
    backup_root.mkdir(parents=True, exist_ok=True)
    backup_path = backup_root / f"{source.stem}-{stamp}.sqlite3"
    shutil.copy2(source, backup_path)

    report: dict[str, object] = {
        "timestamp": datetime.now(tz=UTC).isoformat(),
        "source_database": str(source),
        "backup_path": str(backup_path),
        "source_bytes": source.stat().st_size,
        "backup_bytes": backup_path.stat().st_size,
        "backup_sha256": sha256_file(backup_path),
        "sqlite": sqlite_summary(backup_path),
        "overwrote_source": False,
        "secrets_included": False,
    }
    report_paths = write_reports(report, evidence_dir=evidence_dir, stem=f"sqlite-backup-{stamp}")
    report["evidence_json"] = str(report_paths["json"])
    report["evidence_markdown"] = str(report_paths["markdown"])
    report_paths["json"].write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Back up a SQLite DB and write evidence reports.")
    parser.add_argument("--database", default="macmarket_trader.db", help="SQLite database path")
    parser.add_argument("--evidence-dir", default=str(DEFAULT_EVIDENCE_DIR), help="Evidence output directory")
    parser.add_argument("--backup-dir", default=None, help="Optional backup output directory")
    args = parser.parse_args()

    report = backup_sqlite_database(
        Path(args.database),
        evidence_dir=Path(args.evidence_dir),
        backup_dir=Path(args.backup_dir) if args.backup_dir else None,
    )
    print(json.dumps({"status": "ok", "evidence_json": report["evidence_json"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
