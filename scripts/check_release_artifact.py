"""Verify clean release archive exclusions in dry-run mode."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from create_clean_release_archive import create_clean_release_archive  # noqa: E402


REQUIRED_EXCLUSION_CATEGORIES: dict[str, tuple[str, ...]] = {
    "env_files": (".env", ".env.local"),
    "auth_storage": (".auth",),
    "claude": (".claude",),
    "tmp": (".tmp",),
    "node_modules": ("node_modules",),
    "next_build": (".next",),
    "database_files": (".db", ".sqlite", ".sqlite3"),
    "logs": (".log", "logs"),
    "tsbuildinfo": (".tsbuildinfo",),
}


def path_matches_category(path: str, tokens: tuple[str, ...]) -> bool:
    normalized = path.replace("\\", "/")
    parts = normalized.split("/")
    for token in tokens:
        if token.startswith(".") and token in parts:
            return True
        if token in parts:
            return True
        if normalized.endswith(token):
            return True
    return False


def check_release_artifact(source_root: Path) -> dict[str, object]:
    dry_run = create_clean_release_archive(source_root=source_root, dry_run=True)
    included = set(dry_run["included"])
    excluded = {item["path"] for item in dry_run["excluded"]}
    categories: dict[str, dict[str, object]] = {}
    passed = True
    for category, tokens in REQUIRED_EXCLUSION_CATEGORIES.items():
        included_matches = sorted(path for path in included if path_matches_category(path, tokens))
        excluded_matches = sorted(path for path in excluded if path_matches_category(path, tokens))
        status = "not_present"
        if included_matches:
            status = "failed"
            passed = False
        elif excluded_matches:
            status = "excluded"
        categories[category] = {
            "status": status,
            "included_matches": included_matches[:20],
            "excluded_matches": excluded_matches[:20],
        }
    return {
        "passed": passed,
        "archive_path": dry_run["archive_path"],
        "included_count": dry_run["included_count"],
        "excluded_count": dry_run["excluded_count"],
        "categories": categories,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check clean release artifact exclusion policy.")
    parser.add_argument("--source", default=".", help="Repository/source root")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    args = parser.parse_args()
    report = check_release_artifact(Path(args.source))
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"Clean archive dry-run passed: {report['passed']}")
        for category, detail in report["categories"].items():
            print(f"- {category}: {detail['status']}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
