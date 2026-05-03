"""Create a sanitized shareable source archive."""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import zipfile
from datetime import UTC, datetime
from pathlib import Path


EXCLUDED_DIRS = {
    ".git",
    ".venv",
    "node_modules",
    ".next",
    "logs",
    "backups",
    "release",
    ".claude",
    ".pytest-tmp",
    ".pytest_cache",
    ".tmp",
    "test-results",
    "playwright-report",
    "coverage",
    "htmlcov",
    "dist",
    "out",
    "build",
    "__pycache__",
    "screenshots",
    "smoke-artifacts",
    "uploads",
    "storage",
    "data",
}

EXCLUDED_FILE_PATTERNS = [
    ".env",
    ".env.*",
    "*.db",
    "*.sqlite",
    "*.sqlite3",
    "*.sqlite-journal",
    "*.db-journal",
    "*.log",
    "*.pid",
    "*.pyc",
    "*.pyo",
    "*.tsbuildinfo",
    "*.pem",
    "*.key",
    "*.crt",
    "*secret*",
    "*secrets*",
    "Desktop.ini",
    "Thumbs.db",
    ".alpha_*.log",
    ".alpha_smoke_pids",
]


def relative_posix(path: Path, *, source_root: Path) -> str:
    return path.relative_to(source_root).as_posix()


def should_exclude(path: Path, *, source_root: Path) -> tuple[bool, str]:
    rel = path.relative_to(source_root)
    parts = set(rel.parts[:-1] if path.is_file() else rel.parts)
    blocked = parts.intersection(EXCLUDED_DIRS)
    if blocked:
        return True, f"excluded_dir:{sorted(blocked)[0]}"
    name = path.name
    for pattern in EXCLUDED_FILE_PATTERNS:
        if fnmatch.fnmatch(name.lower(), pattern.lower()):
            return True, f"excluded_file:{pattern}"
    return False, ""


def collect_archive_entries(source_root: Path) -> tuple[list[Path], list[dict[str, str]]]:
    root = source_root.resolve()
    included: list[Path] = []
    excluded: list[dict[str, str]] = []
    for dirpath, dirnames, filenames in os.walk(root):
        current_dir = Path(dirpath)
        kept_dirs: list[str] = []
        for dirname in sorted(dirnames):
            path = current_dir / dirname
            exclude, reason = should_exclude(path, source_root=root)
            if exclude:
                excluded.append({"path": relative_posix(path, source_root=root), "reason": reason})
            else:
                kept_dirs.append(dirname)
        dirnames[:] = kept_dirs

        for filename in sorted(filenames):
            path = current_dir / filename
            exclude, reason = should_exclude(path, source_root=root)
            if exclude:
                excluded.append({"path": relative_posix(path, source_root=root), "reason": reason})
                continue
            included.append(path)
    return included, excluded


def create_clean_release_archive(
    *,
    source_root: Path,
    output: Path | None = None,
    dry_run: bool = False,
) -> dict[str, object]:
    root = source_root.resolve()
    stamp = datetime.now(tz=UTC).strftime("%Y%m%d-%H%M%S")
    archive_path = output.resolve() if output else root.parent / f"{root.name}-clean-release-{stamp}.zip"
    included, excluded = collect_archive_entries(root)
    report: dict[str, object] = {
        "timestamp": datetime.now(tz=UTC).isoformat(),
        "source_root": str(root),
        "archive_path": str(archive_path),
        "dry_run": dry_run,
        "included_count": len(included),
        "excluded_count": len(excluded),
        "included": [relative_posix(path, source_root=root) for path in included],
        "excluded": excluded,
    }
    if dry_run:
        return report

    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in included:
            archive.write(path, arcname=relative_posix(path, source_root=root))
    report["archive_bytes"] = archive_path.stat().st_size
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a clean shareable release archive.")
    parser.add_argument("--source", default=".", help="Repository/source root")
    parser.add_argument("--output", default="", help="Output zip path")
    parser.add_argument("--dry-run", action="store_true", help="List included/excluded files without writing zip")
    parser.add_argument("--json", action="store_true", help="Print JSON report")
    args = parser.parse_args()
    report = create_clean_release_archive(
        source_root=Path(args.source),
        output=Path(args.output) if args.output else None,
        dry_run=args.dry_run,
    )
    if args.json or args.dry_run:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"Created {report['archive_path']} with {report['included_count']} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
