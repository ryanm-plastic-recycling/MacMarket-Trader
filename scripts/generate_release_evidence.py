"""Generate sanitized local release evidence artifacts."""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


DEFAULT_EVIDENCE_DIR = Path(".tmp") / "evidence"
SECRET_KEYWORDS = ("KEY", "SECRET", "TOKEN", "PASSWORD", "PASS", "PRIVATE", "CREDENTIAL")


def timestamp() -> str:
    return datetime.now(tz=UTC).strftime("%Y%m%d-%H%M%S")


def run_command(args: list[str], *, cwd: Path | None = None, timeout: int = 20) -> dict[str, object]:
    try:
        completed = subprocess.run(
            args,
            cwd=str(cwd) if cwd else None,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"available": False, "error": exc.__class__.__name__, "returncode": None}
    return {
        "available": True,
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip()[-4000:],
        "stderr": completed.stderr.strip()[-2000:],
    }


def redact_value(key: str, value: Any) -> Any:
    if key == "secrets_redacted":
        return value
    if isinstance(value, bool) and key.lower().endswith("_present"):
        return value
    if any(word in key.upper() for word in SECRET_KEYWORDS):
        return "[REDACTED]" if value else ""
    if isinstance(value, dict):
        return {item_key: redact_value(item_key, item_value) for item_key, item_value in value.items()}
    if isinstance(value, list):
        return [redact_value(key, item) for item in value]
    if isinstance(value, str) and any(marker in value.lower() for marker in ("sk-", "api_key", "secret", "token=")):
        return "[REDACTED]"
    return value


def git_summary(repo_root: Path) -> dict[str, object]:
    branch = run_command(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_root)
    commit = run_command(["git", "rev-parse", "HEAD"], cwd=repo_root)
    status = run_command(["git", "status", "--short"], cwd=repo_root)
    dirty_lines = []
    if status.get("available") and isinstance(status.get("stdout"), str) and status["stdout"]:
        dirty_lines = str(status["stdout"]).splitlines()
    return {
        "branch": branch.get("stdout") if branch.get("returncode") == 0 else None,
        "commit": commit.get("stdout") if commit.get("returncode") == 0 else None,
        "dirty": bool(dirty_lines),
        "dirty_summary": dirty_lines[:100],
    }


def dependency_snapshot(repo_root: Path) -> dict[str, object]:
    pyproject = repo_root / "pyproject.toml"
    package_json = repo_root / "apps" / "web" / "package.json"
    snapshot: dict[str, object] = {}
    if pyproject.exists():
        snapshot["pyproject_toml_present"] = True
        snapshot["pyproject_bytes"] = pyproject.stat().st_size
    if package_json.exists():
        package = json.loads(package_json.read_text(encoding="utf-8"))
        snapshot["package_json_present"] = True
        snapshot["dependencies"] = sorted((package.get("dependencies") or {}).keys())
        snapshot["dev_dependencies"] = sorted((package.get("devDependencies") or {}).keys())
    return snapshot


def npm_audit_summary(repo_root: Path, *, skip: bool) -> dict[str, object]:
    if skip:
        return {"invoked": False, "summary": "not invoked"}
    app_dir = repo_root / "apps" / "web"
    result = run_command(["npm", "audit", "--json"], cwd=app_dir, timeout=60)
    if not result.get("available") or not result.get("stdout"):
        return {"invoked": True, "available": False, "returncode": result.get("returncode")}
    try:
        payload = json.loads(str(result["stdout"]))
    except json.JSONDecodeError:
        return {"invoked": True, "available": False, "returncode": result.get("returncode"), "parse_error": True}
    metadata = payload.get("metadata", {}) if isinstance(payload, dict) else {}
    vulnerabilities = metadata.get("vulnerabilities", {}) if isinstance(metadata, dict) else {}
    return {
        "invoked": True,
        "available": True,
        "returncode": result.get("returncode"),
        "vulnerabilities": vulnerabilities,
    }


def provider_config_summary() -> dict[str, object]:
    try:
        from macmarket_trader.config import settings
    except Exception as exc:  # noqa: BLE001 - evidence should degrade gracefully
        return {"available": False, "error": exc.__class__.__name__}
    return {
        "available": True,
        "environment": settings.environment,
        "auth_provider": settings.auth_provider,
        "email_provider": settings.email_provider,
        "market_data_provider": settings.market_data_provider,
        "market_data_enabled": settings.market_data_enabled,
        "polygon_enabled": settings.polygon_enabled,
        "polygon_api_key_present": bool(settings.polygon_api_key.strip()),
        "llm_enabled": settings.llm_enabled,
        "llm_provider": settings.llm_provider,
        "llm_model": settings.llm_model,
        "openai_api_key_present": bool(settings.openai_api_key.strip() or settings.llm_api_key.strip()),
        "broker_provider": settings.broker_provider,
        "alpaca_key_present": bool(settings.alpaca_api_key_id.strip()),
        "resend_key_present": bool(settings.resend_api_key.strip()),
        "fred_key_present": bool(settings.fred_api_key.strip()),
        "api_docs_enabled": settings.api_docs_enabled,
        "security_origin_check_enabled": settings.security_origin_check_enabled,
        "security_rate_limit_enabled": settings.security_rate_limit_enabled,
    }


def generate_release_evidence(
    *,
    repo_root: Path,
    evidence_dir: Path = DEFAULT_EVIDENCE_DIR,
    screenshot_path: str | None = None,
    skip_npm_audit: bool = False,
) -> dict[str, object]:
    stamp = timestamp()
    report: dict[str, object] = {
        "timestamp": datetime.now(tz=UTC).isoformat(),
        "repo_root": str(repo_root.resolve()),
        "git": git_summary(repo_root),
        "runtime": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "node": run_command(["node", "--version"], cwd=repo_root).get("stdout"),
            "npm": run_command(["npm", "--version"], cwd=repo_root).get("stdout"),
        },
        "test_results": {
            "conflict_marker_check": {"invoked": False, "status": "placeholder"},
            "git_diff_check": {"invoked": False, "status": "placeholder"},
            "pytest": {"invoked": False, "status": "placeholder"},
            "npm_test": {"invoked": False, "status": "placeholder"},
            "tsc": {"invoked": False, "status": "placeholder"},
        },
        "dependencies": dependency_snapshot(repo_root),
        "npm_audit": npm_audit_summary(repo_root, skip=skip_npm_audit),
        "provider_config": provider_config_summary(),
        "browser_smoke_screenshots": screenshot_path or "",
        "secrets_redacted": True,
    }
    report = redact_value("root", report)

    evidence_dir.mkdir(parents=True, exist_ok=True)
    json_path = evidence_dir / f"release-evidence-{stamp}.json"
    md_path = evidence_dir / f"release-evidence-{stamp}.md"
    report["evidence_json"] = str(json_path)
    report["evidence_markdown"] = str(md_path)
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(
        "\n".join(
            [
                f"# Release Evidence {report['timestamp']}",
                "",
                f"- Branch: `{report['git'].get('branch')}`",
                f"- Commit: `{report['git'].get('commit')}`",
                f"- Dirty: `{report['git'].get('dirty')}`",
                f"- Python: `{report['runtime'].get('python')}`",
                f"- Node: `{report['runtime'].get('node')}`",
                f"- npm: `{report['runtime'].get('npm')}`",
                f"- npm audit invoked: `{report['npm_audit'].get('invoked')}`",
                f"- Screenshots: `{report['browser_smoke_screenshots']}`",
                "",
                "Secrets are redacted; provider credentials are represented only as present/not present booleans.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate sanitized release evidence.")
    parser.add_argument("--repo-root", default=".", help="Repository root")
    parser.add_argument("--evidence-dir", default=str(DEFAULT_EVIDENCE_DIR), help="Evidence output directory")
    parser.add_argument("--screenshots", default="", help="Optional browser smoke screenshot directory/path")
    parser.add_argument("--skip-npm-audit", action="store_true", help="Do not run npm audit")
    args = parser.parse_args()
    report = generate_release_evidence(
        repo_root=Path(args.repo_root),
        evidence_dir=Path(args.evidence_dir),
        screenshot_path=args.screenshots,
        skip_npm_audit=args.skip_npm_audit,
    )
    print(json.dumps({"status": "ok", "evidence_json": report["evidence_json"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
