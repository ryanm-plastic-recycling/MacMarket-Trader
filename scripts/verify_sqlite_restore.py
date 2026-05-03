"""Verify a SQLite backup/DB by copying it to a temp path first."""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import tempfile
from datetime import UTC, datetime
from pathlib import Path


DEFAULT_EVIDENCE_DIR = Path(".tmp") / "evidence"


def timestamp() -> str:
    return datetime.now(tz=UTC).strftime("%Y%m%d-%H%M%S")


def verify_sqlite_restore(database: Path, *, evidence_dir: Path = DEFAULT_EVIDENCE_DIR) -> dict[str, object]:
    source = database.resolve()
    if not source.exists():
        raise FileNotFoundError(f"SQLite database not found: {source}")
    before_mtime = source.stat().st_mtime_ns
    before_size = source.stat().st_size
    stamp = timestamp()

    with tempfile.TemporaryDirectory(prefix="macmarket-restore-verify-") as temp_dir:
        temp_path = Path(temp_dir) / source.name
        shutil.copy2(source, temp_path)
        conn = sqlite3.connect(temp_path)
        try:
            integrity = conn.execute("PRAGMA integrity_check").fetchone()
            quick = conn.execute("PRAGMA quick_check").fetchone()
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
            user_version = conn.execute("PRAGMA user_version").fetchone()
        finally:
            conn.close()
        copied_path = str(temp_path)

    after_mtime = source.stat().st_mtime_ns
    after_size = source.stat().st_size
    report: dict[str, object] = {
        "timestamp": datetime.now(tz=UTC).isoformat(),
        "source_database": str(source),
        "verified_temp_copy_path": copied_path,
        "temp_copy_removed": True,
        "source_size_before": before_size,
        "source_size_after": after_size,
        "source_mtime_unchanged": before_mtime == after_mtime,
        "source_size_unchanged": before_size == after_size,
        "overwrote_source": False,
        "integrity_check": integrity[0] if integrity else "unknown",
        "quick_check": quick[0] if quick else "unknown",
        "table_count": len(tables),
        "tables": [row[0] for row in tables],
        "user_version": user_version[0] if user_version else None,
    }

    evidence_dir.mkdir(parents=True, exist_ok=True)
    json_path = evidence_dir / f"sqlite-restore-verify-{stamp}.json"
    md_path = evidence_dir / f"sqlite-restore-verify-{stamp}.md"
    report["evidence_json"] = str(json_path)
    report["evidence_markdown"] = str(md_path)
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(
        "\n".join(
            [
                f"# SQLite Restore Verification {report['timestamp']}",
                "",
                f"- Source: `{report['source_database']}`",
                f"- Integrity check: `{report['integrity_check']}`",
                f"- Quick check: `{report['quick_check']}`",
                f"- Tables: `{report['table_count']}`",
                f"- Source unchanged: `{report['source_mtime_unchanged'] and report['source_size_unchanged']}`",
                "",
                "Verification used a temporary copy and did not overwrite the source database.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify SQLite restore readiness using a temp copy.")
    parser.add_argument("--database", default="macmarket_trader.db", help="SQLite database path")
    parser.add_argument("--evidence-dir", default=str(DEFAULT_EVIDENCE_DIR), help="Evidence output directory")
    args = parser.parse_args()
    report = verify_sqlite_restore(Path(args.database), evidence_dir=Path(args.evidence_dir))
    print(json.dumps({"status": "ok", "evidence_json": report["evidence_json"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
