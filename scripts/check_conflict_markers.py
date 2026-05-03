"""Scan source files for unresolved merge conflict markers."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


EXCLUDED_DIRS = {
    ".git",
    ".venv",
    "node_modules",
    ".next",
    ".tmp",
    ".pytest-tmp",
    ".pytest_cache",
    ".claude",
    "__pycache__",
    "logs",
    "backups",
    "test-results",
    "playwright-report",
    "coverage",
}

CONFLICT_MARKERS = ("<<<<<<<", "=======", ">>>>>>>")


def relative_posix(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def iter_candidate_files(root: Path) -> list[Path]:
    resolved = root.resolve()
    files: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(resolved):
        kept_dirs: list[str] = []
        for dirname in sorted(dirnames):
            if dirname in EXCLUDED_DIRS:
                continue
            kept_dirs.append(dirname)
        dirnames[:] = kept_dirs
        for filename in sorted(filenames):
            files.append(Path(dirpath) / filename)
    return files


def scan_conflict_markers(root: Path) -> list[dict[str, object]]:
    resolved = root.resolve()
    findings: list[dict[str, object]] = []
    for path in iter_candidate_files(resolved):
        try:
            with path.open("r", encoding="utf-8") as handle:
                for line_number, line in enumerate(handle, start=1):
                    stripped = line.rstrip("\r\n")
                    if stripped.startswith(CONFLICT_MARKERS):
                        findings.append(
                            {
                                "path": relative_posix(path, resolved),
                                "line": line_number,
                                "marker": stripped[:12],
                            }
                        )
        except UnicodeDecodeError:
            continue
        except OSError as exc:
            findings.append(
                {
                    "path": relative_posix(path, resolved),
                    "line": None,
                    "marker": "read_error",
                    "error": exc.__class__.__name__,
                }
            )
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan files for unresolved merge conflict markers.")
    parser.add_argument("--root", default=".", help="Repository root")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    args = parser.parse_args()
    findings = scan_conflict_markers(Path(args.root))
    payload = {"passed": not findings, "finding_count": len(findings), "findings": findings}
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif findings:
        print(f"Found {len(findings)} conflict marker finding(s).")
        for finding in findings:
            print(f"{finding['path']}:{finding['line']} {finding['marker']}")
    else:
        print("No conflict markers found.")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
