"""Conservative local secret scanner for release evidence gates."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
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
    "htmlcov",
}

EXCLUDED_FILES = {
    ".env",
    ".env.local",
}

MAX_FILE_BYTES = 2 * 1024 * 1024

SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b("
    r"OPENAI_API_KEY|LLM_API_KEY|CLERK_SECRET_KEY|POLYGON_API_KEY|MASSIVE_API_KEY|"
    r"ALPACA_API_SECRET_KEY|ALPACA_SECRET_KEY|RESEND_API_KEY|FRED_API_KEY|"
    r"DATABASE_URL|POSTGRES_URL|JWT_SECRET|SESSION_SECRET"
    r")\b\s*[:=]\s*[\"']?([^\"'\s#]+)"
)

TOKEN_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("openai_key", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{24,}\b")),
    ("clerk_secret_key", re.compile(r"\bsk_(?:test|live)_[A-Za-z0-9]{20,}\b")),
    ("resend_key", re.compile(r"\bre_[A-Za-z0-9]{20,}\b")),
    ("database_url_with_password", re.compile(r"\b(?:postgres|postgresql|mysql)://[^:\s]+:[^@\s]+@[^ \n\r\t]+")),
]

PLACEHOLDER_WORDS = (
    "example",
    "placeholder",
    "redacted",
    "changeme",
    "change-me",
    "dummy",
    "fake",
    "test",
    "your_",
    "your-",
    "none",
    "null",
)


def relative_posix(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def is_placeholder(value: str) -> bool:
    lowered = value.lower()
    return any(word in lowered for word in PLACEHOLDER_WORDS)


def is_code_reference(value: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.]*", value))


def redacted_value(value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8", errors="ignore")).hexdigest()[:8]
    return f"[REDACTED length={len(value)} sha256_8={digest}]"


def redact_text(text: str) -> str:
    redacted = text
    for _, pattern in TOKEN_PATTERNS:
        redacted = pattern.sub(lambda match: redacted_value(match.group(0)), redacted)
    redacted = SECRET_ASSIGNMENT_RE.sub(
        lambda match: f"{match.group(1)}={redacted_value(match.group(2))}",
        redacted,
    )
    return redacted


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
            if filename in EXCLUDED_FILES or filename.startswith(".env."):
                continue
            path = Path(dirpath) / filename
            try:
                if path.stat().st_size > MAX_FILE_BYTES:
                    continue
            except OSError:
                continue
            files.append(path)
    return files


def scan_line(line: str) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for match in SECRET_ASSIGNMENT_RE.finditer(line):
        value = match.group(2)
        if is_placeholder(value) or is_code_reference(value) or len(value) < 12:
            continue
        findings.append(
            {
                "rule": "secret_assignment",
                "key": match.group(1),
                "redacted": redacted_value(value),
            }
        )
    for rule, pattern in TOKEN_PATTERNS:
        for match in pattern.finditer(line):
            value = match.group(0)
            if is_placeholder(value):
                continue
            findings.append({"rule": rule, "key": "", "redacted": redacted_value(value)})
    return findings


def scan_secrets(root: Path) -> list[dict[str, object]]:
    resolved = root.resolve()
    findings: list[dict[str, object]] = []
    for path in iter_candidate_files(resolved):
        try:
            with path.open("r", encoding="utf-8") as handle:
                for line_number, line in enumerate(handle, start=1):
                    for finding in scan_line(line):
                        findings.append(
                            {
                                "path": relative_posix(path, resolved),
                                "line": line_number,
                                "rule": finding["rule"],
                                "key": finding["key"],
                                "redacted": finding["redacted"],
                            }
                        )
        except UnicodeDecodeError:
            continue
        except OSError as exc:
            findings.append(
                {
                    "path": relative_posix(path, resolved),
                    "line": None,
                    "rule": "read_error",
                    "key": "",
                    "redacted": "",
                    "error": exc.__class__.__name__,
                }
            )
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan source files for common secret patterns.")
    parser.add_argument("--root", default=".", help="Repository root")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    args = parser.parse_args()
    findings = scan_secrets(Path(args.root))
    payload = {"passed": not findings, "finding_count": len(findings), "findings": findings}
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif findings:
        print(f"Found {len(findings)} possible secret finding(s). Values are redacted.")
        for finding in findings:
            print(f"{finding['path']}:{finding['line']} {finding['rule']} {finding['redacted']}")
    else:
        print("No secret patterns found.")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
