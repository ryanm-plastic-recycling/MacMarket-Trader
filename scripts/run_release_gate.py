"""Run the local release evidence gate and write sanitized reports."""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from check_conflict_markers import scan_conflict_markers  # noqa: E402
from check_release_artifact import check_release_artifact  # noqa: E402
from generate_release_evidence import generate_release_evidence, timestamp  # noqa: E402
from scan_secrets import redact_text, scan_secrets  # noqa: E402


DEFAULT_EVIDENCE_DIR = Path(".tmp") / "evidence"
COMPLIANCE_REQUIRED_DOCS = [
    "README.md",
    "control-matrix.md",
    "risk-register.md",
    "vendor-inventory.md",
    "data-classification-retention.md",
    "incident-response-plan.md",
    "change-release-management.md",
    "backup-restore-dr-plan.md",
    "model-risk-management.md",
    "regulatory-boundary-memo.md",
    "acquisition-readiness.md",
    "evidence-manifest-template.md",
    "access-review-template.md",
    "vendor-review-template.md",
    "incident-tabletop-template.md",
]

AUDIT_LEVELS = ("info", "low", "moderate", "high", "critical")


def now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def redact_payload(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: redact_payload(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_payload(item) for item in value]
    if isinstance(value, str):
        return redact_text(value)
    return value


def run_command(args: list[str], *, cwd: Path, timeout: int) -> dict[str, object]:
    try:
        completed = subprocess.run(
            args,
            cwd=str(cwd),
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "command": args,
            "available": False,
            "returncode": None,
            "stdout": "",
            "stderr": exc.__class__.__name__,
        }
    return {
        "command": args,
        "available": True,
        "returncode": completed.returncode,
        "stdout": redact_text(completed.stdout.strip()[-6000:]),
        "stderr": redact_text(completed.stderr.strip()[-3000:]),
    }


def step(
    name: str,
    status: str,
    *,
    hard_failure: bool = False,
    details: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "name": name,
        "status": status,
        "hard_failure": hard_failure,
        "details": details or {},
    }


def check_compliance_docs(repo_root: Path) -> dict[str, object]:
    base = repo_root / "docs" / "compliance"
    missing = [filename for filename in COMPLIANCE_REQUIRED_DOCS if not (base / filename).exists()]
    return {
        "passed": not missing,
        "base": str(base),
        "required": COMPLIANCE_REQUIRED_DOCS,
        "missing": missing,
    }


def parse_npm_audit(stdout: str) -> dict[str, object]:
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        return {"available": False, "parse_error": True, "vulnerabilities": {}}
    metadata = payload.get("metadata", {}) if isinstance(payload, dict) else {}
    vulnerabilities = metadata.get("vulnerabilities", {}) if isinstance(metadata, dict) else {}
    return {"available": True, "parse_error": False, "vulnerabilities": vulnerabilities}


def audit_has_hard_failure(vulnerabilities: dict[str, int], fail_level: str) -> bool:
    if fail_level == "none":
        return False
    if fail_level not in AUDIT_LEVELS:
        fail_level = "high"
    threshold = AUDIT_LEVELS.index(fail_level)
    for level in AUDIT_LEVELS[threshold:]:
        if int(vulnerabilities.get(level, 0) or 0) > 0:
            return True
    return False


def mock_audit_result() -> dict[str, object]:
    payload = {
        "metadata": {
            "vulnerabilities": {
                "info": 0,
                "low": 0,
                "moderate": 1,
                "high": 0,
                "critical": 0,
                "total": 1,
            }
        }
    }
    return {
        "command": ["npm", "audit", "--json"],
        "available": True,
        "returncode": 1,
        "stdout": json.dumps(payload),
        "stderr": "",
    }


def write_manifest(
    *,
    evidence_dir: Path,
    gate_json: Path,
    gate_markdown: Path,
    release_evidence: dict[str, object],
    clean_archive: dict[str, object],
    screenshots: str,
) -> Path:
    manifest = {
        "timestamp": now_iso(),
        "responsible_owner_placeholder": "TBD",
        "review_date_placeholder": "TBD",
        "evidence": {
            "release_evidence": release_evidence.get("evidence_json", ""),
            "release_gate_json": str(gate_json),
            "release_gate_markdown": str(gate_markdown),
            "backup_evidence": "TBD - latest sqlite-backup-*.json",
            "restore_evidence": "TBD - latest sqlite-restore-verify-*.json",
            "browser_smoke_screenshots": screenshots or "TBD",
            "security_audit_results": "TBD",
            "lifecycle_audit_results": "pytest tests/test_paper_equity_lifecycle_integrity.py or latest report",
            "provider_health_verification": "TBD - post-deploy provider-health capture",
            "openai_probe_verification": "TBD - post-deploy provider-health LLM probe capture",
            "clean_archive_artifact": clean_archive.get("archive_path", ""),
        },
    }
    path = evidence_dir / "evidence-manifest.json"
    path.write_text(json.dumps(redact_payload(manifest), indent=2, sort_keys=True), encoding="utf-8")
    return path


def write_gate_reports(
    *,
    evidence_dir: Path,
    stamp: str,
    result: dict[str, object],
) -> tuple[Path, Path]:
    evidence_dir.mkdir(parents=True, exist_ok=True)
    json_path = evidence_dir / f"release-gate-{stamp}.json"
    md_path = evidence_dir / f"release-gate-{stamp}.md"
    result["evidence_json"] = str(json_path)
    result["evidence_markdown"] = str(md_path)
    json_path.write_text(json.dumps(redact_payload(result), indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        f"# Release Gate {result['timestamp']}",
        "",
        f"- Overall status: `{result['status']}`",
        f"- Dry run: `{result['dry_run']}`",
        f"- Mock commands: `{result['mock_commands']}`",
        f"- Repository: `{result['repo_root']}`",
        "",
        "## Steps",
    ]
    for item in result["steps"]:
        lines.append(f"- `{item['name']}`: `{item['status']}` hard_failure=`{item['hard_failure']}`")
    lines.extend(
        [
            "",
            "Moderate npm audit findings are report-only unless the gate is configured with a lower fail threshold.",
            "Secrets and token-like values are redacted from machine and markdown evidence.",
        ]
    )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def run_release_gate(
    *,
    repo_root: Path,
    evidence_dir: Path = DEFAULT_EVIDENCE_DIR,
    dry_run: bool = False,
    mock_commands: bool = False,
    audit_fail_level: str = "high",
    screenshots: str = "",
    skip_release_evidence_npm_audit: bool = True,
) -> dict[str, object]:
    root = repo_root.resolve()
    evidence = evidence_dir if evidence_dir.is_absolute() else root / evidence_dir
    evidence.mkdir(parents=True, exist_ok=True)
    stamp = timestamp()
    steps: list[dict[str, object]] = []

    conflict_findings = scan_conflict_markers(root)
    steps.append(
        step(
            "conflict_marker_scan",
            "passed" if not conflict_findings else "failed",
            hard_failure=bool(conflict_findings),
            details={"finding_count": len(conflict_findings), "findings": conflict_findings[:50]},
        )
    )

    secret_findings = scan_secrets(root)
    steps.append(
        step(
            "secret_scan",
            "passed" if not secret_findings else "failed",
            hard_failure=bool(secret_findings),
            details={"finding_count": len(secret_findings), "findings": secret_findings[:50]},
        )
    )

    if dry_run and mock_commands:
        diff_result = {"command": ["git", "diff", "--check"], "returncode": 0, "stdout": "", "stderr": ""}
    else:
        diff_result = run_command(["git", "diff", "--check"], cwd=root, timeout=60)
    steps.append(
        step(
            "git_diff_check",
            "passed" if diff_result.get("returncode") == 0 else "failed",
            hard_failure=diff_result.get("returncode") != 0,
            details=diff_result,
        )
    )

    command_steps = [
        ("backend_pytest", ["python", "-m", "pytest", "--basetemp", ".pytest-tmp"], root, 900),
        ("frontend_npm_test", ["npm", "test"], root / "apps" / "web", 900),
        ("frontend_tsc", ["npx", "tsc", "--noEmit"], root / "apps" / "web", 900),
    ]
    for name, command, cwd, timeout in command_steps:
        if dry_run:
            details = {"command": command, "skipped_reason": "dry_run"}
            if mock_commands:
                details["mocked_returncode"] = 0
                steps.append(step(name, "passed", details=details))
            else:
                steps.append(step(name, "skipped", details=details))
            continue
        command_result = run_command(command, cwd=cwd, timeout=timeout)
        steps.append(
            step(
                name,
                "passed" if command_result.get("returncode") == 0 else "failed",
                hard_failure=command_result.get("returncode") != 0,
                details=command_result,
            )
        )

    if dry_run and mock_commands:
        audit_result = mock_audit_result()
    else:
        audit_result = run_command(["npm", "audit", "--json"], cwd=root / "apps" / "web", timeout=120)
    parsed_audit = parse_npm_audit(str(audit_result.get("stdout") or "{}"))
    vulnerabilities = parsed_audit.get("vulnerabilities", {})
    audit_hard_failure = audit_has_hard_failure(
        vulnerabilities if isinstance(vulnerabilities, dict) else {},
        audit_fail_level,
    )
    audit_status = "failed" if audit_hard_failure else "warning"
    if not parsed_audit.get("available"):
        audit_status = "failed"
        audit_hard_failure = True
    elif int((vulnerabilities or {}).get("total", 0) or 0) == 0:
        audit_status = "passed"
    steps.append(
        step(
            "npm_audit_report_only",
            audit_status,
            hard_failure=audit_hard_failure,
            details={
                "command": audit_result.get("command"),
                "returncode": audit_result.get("returncode"),
                "audit_fail_level": audit_fail_level,
                "vulnerabilities": vulnerabilities,
                "auto_fix_invoked": False,
            },
        )
    )

    docs_report = check_compliance_docs(root)
    steps.append(
        step(
            "compliance_docs_presence",
            "passed" if docs_report["passed"] else "failed",
            hard_failure=not docs_report["passed"],
            details=docs_report,
        )
    )

    archive_report = check_release_artifact(root)
    steps.append(
        step(
            "clean_release_archive_dry_run",
            "passed" if archive_report["passed"] else "failed",
            hard_failure=not archive_report["passed"],
            details=archive_report,
        )
    )

    release_evidence = generate_release_evidence(
        repo_root=root,
        evidence_dir=evidence,
        screenshot_path=screenshots,
        skip_npm_audit=skip_release_evidence_npm_audit,
    )
    steps.append(
        step(
            "release_evidence_generation",
            "passed",
            details={
                "evidence_json": release_evidence.get("evidence_json"),
                "evidence_markdown": release_evidence.get("evidence_markdown"),
            },
        )
    )

    hard_failed = any(bool(item["hard_failure"]) for item in steps)
    result: dict[str, object] = {
        "timestamp": now_iso(),
        "repo_root": str(root),
        "platform": platform.platform(),
        "dry_run": dry_run,
        "mock_commands": mock_commands,
        "status": "failed" if hard_failed else "passed",
        "steps": steps,
    }
    json_path, md_path = write_gate_reports(evidence_dir=evidence, stamp=stamp, result=result)
    manifest_path = write_manifest(
        evidence_dir=evidence,
        gate_json=json_path,
        gate_markdown=md_path,
        release_evidence=release_evidence,
        clean_archive=archive_report,
        screenshots=screenshots,
    )
    result["evidence_json"] = str(json_path)
    result["evidence_markdown"] = str(md_path)
    result["evidence_manifest"] = str(manifest_path)
    json_path.write_text(json.dumps(redact_payload(result), indent=2, sort_keys=True), encoding="utf-8")
    return redact_payload(result)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the MacMarket release evidence gate.")
    parser.add_argument("--repo-root", default=".", help="Repository root")
    parser.add_argument("--evidence-dir", default=str(DEFAULT_EVIDENCE_DIR), help="Evidence output directory")
    parser.add_argument("--dry-run", action="store_true", help="Skip expensive command execution")
    parser.add_argument("--mock-commands", action="store_true", help="Mock command results for tests/CI-safe dry runs")
    parser.add_argument(
        "--audit-fail-level",
        default="high",
        choices=("none", "low", "moderate", "high", "critical"),
        help="Lowest npm audit severity that fails the gate",
    )
    parser.add_argument("--screenshots", default="", help="Optional browser smoke screenshot path")
    parser.add_argument(
        "--include-release-evidence-npm-audit",
        action="store_true",
        help="Let the release evidence generator run npm audit again",
    )
    args = parser.parse_args()
    result = run_release_gate(
        repo_root=Path(args.repo_root),
        evidence_dir=Path(args.evidence_dir),
        dry_run=args.dry_run,
        mock_commands=args.mock_commands,
        audit_fail_level=args.audit_fail_level,
        screenshots=args.screenshots,
        skip_release_evidence_npm_audit=not args.include_release_evidence_npm_audit,
    )
    print(json.dumps({"status": result["status"], "evidence_json": result["evidence_json"]}, indent=2))
    return 1 if result["status"] == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
