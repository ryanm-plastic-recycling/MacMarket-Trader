from __future__ import annotations

import importlib.util
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_script(name: str):
    path = REPO_ROOT / "scripts" / name
    spec = importlib.util.spec_from_file_location(name.replace(".py", ""), path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_release_gate_produces_json_markdown_and_manifest_in_dry_run(tmp_path: Path) -> None:
    module = _load_script("run_release_gate.py")
    evidence_dir = tmp_path / "evidence"

    result = module.run_release_gate(
        repo_root=REPO_ROOT,
        evidence_dir=evidence_dir,
        dry_run=True,
        mock_commands=True,
    )

    assert result["status"] == "passed"
    assert Path(result["evidence_json"]).exists()
    assert Path(result["evidence_markdown"]).exists()
    assert Path(result["evidence_manifest"]).exists()
    step_names = {step["name"] for step in result["steps"]}
    assert {
        "conflict_marker_scan",
        "secret_scan",
        "backend_pytest",
        "frontend_npm_test",
        "frontend_tsc",
        "npm_audit_report_only",
        "compliance_docs_presence",
        "clean_release_archive_dry_run",
        "release_evidence_generation",
    }.issubset(step_names)

    manifest = json.loads(Path(result["evidence_manifest"]).read_text(encoding="utf-8"))
    assert "release_evidence" in manifest["evidence"]
    assert manifest["responsible_owner_placeholder"] == "TBD"


def test_release_gate_resolves_command_shims(monkeypatch) -> None:
    module = _load_script("run_release_gate.py")

    def fake_which(name: str) -> str | None:
        if name == "npm":
            return r"C:\Program Files\nodejs\npm.cmd"
        return None

    monkeypatch.setattr(module.shutil, "which", fake_which)

    assert module.resolve_command_args(["npm", "test"]) == [
        r"C:\Program Files\nodejs\npm.cmd",
        "test",
    ]
    assert module.resolve_command_args(["definitely-missing", "--version"]) == [
        "definitely-missing",
        "--version",
    ]


def test_secret_scan_redacts_values(tmp_path: Path) -> None:
    module = _load_script("scan_secrets.py")
    secret = "sk-proj-" + ("a" * 32)
    source = tmp_path / "repo"
    source.mkdir()
    (source / "settings.py").write_text(f'OPENAI_API_KEY="{secret}"\n', encoding="utf-8")

    findings = module.scan_secrets(source)
    serialized = json.dumps(findings)

    assert findings
    assert findings[0]["rule"] in {"secret_assignment", "openai_key"}
    assert secret not in serialized
    assert "[REDACTED" in serialized


def test_release_artifact_check_excludes_required_paths(tmp_path: Path) -> None:
    module = _load_script("check_release_artifact.py")
    source = tmp_path / "repo"
    source.mkdir()
    (source / "README.md").write_text("# ok\n", encoding="utf-8")
    (source / ".env.local").write_text("SECRET=do-not-package\n", encoding="utf-8")
    (source / ".claude").mkdir()
    (source / ".tmp").mkdir()
    (source / "logs").mkdir()
    (source / "logs" / "app.log").write_text("log\n", encoding="utf-8")
    (source / "app.sqlite3").write_text("db\n", encoding="utf-8")
    (source / "apps" / "web" / "node_modules" / "pkg").mkdir(parents=True)
    (source / "apps" / "web" / "node_modules" / "pkg" / "index.js").write_text("", encoding="utf-8")
    (source / "apps" / "web" / ".next").mkdir(parents=True)
    (source / "apps" / "web" / "tsconfig.tsbuildinfo").write_text("{}", encoding="utf-8")

    report = module.check_release_artifact(source)

    assert report["passed"] is True
    for category in [
        "env_files",
        "claude",
        "tmp",
        "node_modules",
        "next_build",
        "database_files",
        "logs",
        "tsbuildinfo",
    ]:
        assert report["categories"][category]["status"] == "excluded"


def test_compliance_templates_and_ci_workflow_exist() -> None:
    for filename in [
        "evidence-manifest-template.md",
        "access-review-template.md",
        "vendor-review-template.md",
        "incident-tabletop-template.md",
    ]:
        path = REPO_ROOT / "docs" / "compliance" / filename
        assert path.exists()
        assert path.read_text(encoding="utf-8").startswith("# ")

    workflow = REPO_ROOT / ".github" / "workflows" / "ci.yml"
    assert workflow.exists()
    workflow_text = workflow.read_text(encoding="utf-8")
    assert "scripts/scan_secrets.py" in workflow_text
    assert "scripts/run_release_gate.py" in workflow_text
    assert "npm audit --json || true" in workflow_text


def test_backup_schedule_helper_defaults_to_dry_run() -> None:
    script = (REPO_ROOT / "scripts" / "schedule_backup_windows_task.ps1").read_text(encoding="utf-8")
    assert "[switch]$Apply" in script
    assert "if (-not $Apply)" in script
    assert "Dry run only" in script
    assert script.index("if (-not $Apply)") < script.index("Register-ScheduledTask")


def test_release_gate_fails_on_conflict_marker_fixture(tmp_path: Path) -> None:
    module = _load_script("run_release_gate.py")
    source = tmp_path / "repo"
    source.mkdir()
    (source / "bad.txt").write_text("<<<<<<< ours\nx\n=======\ny\n>>>>>>> theirs\n", encoding="utf-8")

    result = module.run_release_gate(
        repo_root=source,
        evidence_dir=tmp_path / "evidence",
        dry_run=True,
        mock_commands=True,
    )

    assert result["status"] == "failed"
    conflict_step = next(step for step in result["steps"] if step["name"] == "conflict_marker_scan")
    assert conflict_step["hard_failure"] is True
    assert conflict_step["details"]["finding_count"] == 3


def test_release_gate_reports_npm_audit_summary_without_auto_fixing(tmp_path: Path) -> None:
    module = _load_script("run_release_gate.py")
    result = module.run_release_gate(
        repo_root=REPO_ROOT,
        evidence_dir=tmp_path / "evidence",
        dry_run=True,
        mock_commands=True,
    )

    audit_step = next(step for step in result["steps"] if step["name"] == "npm_audit_report_only")
    assert audit_step["status"] == "warning"
    assert audit_step["hard_failure"] is False
    assert audit_step["details"]["auto_fix_invoked"] is False
    assert audit_step["details"]["command"] == ["npm", "audit", "--json"]
    assert audit_step["details"]["vulnerabilities"]["moderate"] == 1


def test_release_gate_progress_output_and_quick_mode(tmp_path: Path, capsys) -> None:
    module = _load_script("run_release_gate.py")
    result = module.run_release_gate(
        repo_root=REPO_ROOT,
        evidence_dir=tmp_path / "evidence",
        dry_run=True,
        quick=True,
        mock_commands=True,
        progress=True,
    )

    output = capsys.readouterr().out
    assert "[release-gate] starting conflict_marker_scan" in output
    assert "[release-gate] starting targeted_compliance_pytest" in output
    assert "[release-gate] finished release_evidence_generation" in output
    assert " in " in output
    assert result["quick"] is True
    step_names = {step["name"] for step in result["steps"]}
    assert "targeted_compliance_pytest" in step_names
    assert "backend_pytest" not in step_names
    assert "frontend_npm_test" not in step_names
    audit_step = next(step for step in result["steps"] if step["name"] == "npm_audit_report_only")
    assert audit_step["status"] == "skipped"
    assert audit_step["details"]["skipped_reason"] == "quick_mode"
