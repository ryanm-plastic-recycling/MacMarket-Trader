from __future__ import annotations

import importlib.util
import json
import sqlite3
import zipfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_script(name: str):
    path = REPO_ROOT / "scripts" / name
    spec = importlib.util.spec_from_file_location(name.replace(".py", ""), path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_compliance_docs_exist_and_include_required_headings() -> None:
    required = {
        "README.md": ["Evidence Set", "Current Gaps"],
        "control-matrix.md": ["Access control", "LLM governance", "Paper-order lifecycle integrity"],
        "risk-register.md": ["unauthorized admin access", "SQLite data loss", "CSRF"],
        "vendor-inventory.md": ["Clerk", "OpenAI", "Massive/Polygon", "Cloudflare/Caddy"],
        "data-classification-retention.md": ["LLM prompts/responses/provenance", "screenshots/smoke artifacts"],
        "incident-response-plan.md": ["Severity Levels", "Post-Incident Review Template"],
        "change-release-management.md": ["Release Gates", "Rollback Plan Template"],
        "backup-restore-dr-plan.md": ["Backup Expectations", "Restore Drill Expectations"],
        "model-risk-management.md": ["LLM Boundary", "Validation Evidence Needed"],
        "model-inventory.md": ["Setup Engines", "LLM Explanation Boundary", "Current Versioning Gaps"],
        "model-validation-report-template.md": ["Objective", "Baseline Comparison", "Approval / Signoff"],
        "regulatory-boundary-memo.md": ["Current Boundary", "Required Review Before Expansion"],
        "acquisition-readiness.md": ["Buyer Evidence Packet Checklist", "Not Yet Audit-Ready"],
    }
    base = REPO_ROOT / "docs" / "compliance"
    for filename, snippets in required.items():
        path = base / filename
        assert path.exists(), f"missing compliance doc: {filename}"
        text = path.read_text(encoding="utf-8")
        assert text.startswith("# "), f"{filename} needs a top-level heading"
        normalized = text.lower()
        for snippet in snippets:
            assert snippet.lower() in normalized, f"{filename} missing {snippet!r}"


def test_regulatory_boundary_memo_preserves_no_execution_boundary() -> None:
    text = (REPO_ROOT / "docs" / "compliance" / "regulatory-boundary-memo.md").read_text(
        encoding="utf-8"
    ).lower()
    assert "does not perform live trading" in text
    assert "does not provide broker routing" in text
    assert "not legal advice" in text
    forbidden_claims = [
        "soc 2 compliant",
        "iso certified",
        "live trading enabled",
        "broker routing enabled",
        "is a registered investment adviser",
        "acts as a registered investment adviser",
    ]
    for claim in forbidden_claims:
        assert claim not in text


def test_control_matrix_covers_required_audit_areas() -> None:
    text = (REPO_ROOT / "docs" / "compliance" / "control-matrix.md").read_text(encoding="utf-8")
    for required in [
        "Access control",
        "LLM governance",
        "Market-data integrity",
        "Paper-order lifecycle integrity",
        "Backup/restore",
        "Model risk management",
        "Regulatory boundary",
    ]:
        assert required in text


def test_clean_release_archive_excludes_local_state_and_secret_files(tmp_path: Path) -> None:
    module = _load_script("create_clean_release_archive.py")
    source = tmp_path / "repo"
    source.mkdir()
    (source / "README.md").write_text("# ok\n", encoding="utf-8")
    (source / ".env").write_text("OPENAI_API_KEY=secret\n", encoding="utf-8")
    (source / "macmarket.db").write_text("db", encoding="utf-8")
    (source / "debug.log").write_text("log", encoding="utf-8")
    (source / "apps").mkdir()
    (source / "apps" / "web").mkdir(parents=True, exist_ok=True)
    (source / "apps" / "web" / "tsconfig.tsbuildinfo").write_text("{}", encoding="utf-8")
    (source / ".auth").mkdir()
    (source / ".auth" / "macmarket-smoke.json").write_text("{}", encoding="utf-8")
    (source / ".claude").mkdir()
    (source / ".claude" / "note.txt").write_text("local", encoding="utf-8")
    (source / ".tmp").mkdir()
    (source / ".tmp" / "evidence.json").write_text("{}", encoding="utf-8")
    (source / "test-results").mkdir()
    (source / "test-results" / "result.txt").write_text("x", encoding="utf-8")

    dry = module.create_clean_release_archive(source_root=source, dry_run=True)
    included = set(dry["included"])
    excluded = {item["path"] for item in dry["excluded"]}
    assert "README.md" in included
    for path in [
        ".env",
        "macmarket.db",
        "debug.log",
        "apps/web/tsconfig.tsbuildinfo",
        ".auth",
        ".claude",
        ".tmp",
        "test-results",
    ]:
        assert path in excluded

    archive_path = tmp_path / "clean.zip"
    report = module.create_clean_release_archive(source_root=source, output=archive_path)
    assert archive_path.exists()
    with zipfile.ZipFile(archive_path) as archive:
        names = set(archive.namelist())
    assert names == {"README.md"}
    assert report["included_count"] == 1


def test_release_evidence_generator_redacts_secrets(tmp_path: Path, monkeypatch) -> None:
    module = _load_script("generate_release_evidence.py")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-proj-super-secret")
    evidence_dir = tmp_path / "evidence"

    report = module.generate_release_evidence(
        repo_root=REPO_ROOT,
        evidence_dir=evidence_dir,
        screenshot_path="screenshots/smoke",
        skip_npm_audit=True,
    )

    payload = json.loads(Path(report["evidence_json"]).read_text(encoding="utf-8"))
    serialized = json.dumps(payload)
    assert "sk-proj-super-secret" not in serialized
    assert payload["secrets_redacted"] is True
    assert isinstance(payload["provider_config"].get("openai_api_key_present"), bool)
    assert payload["npm_audit"]["invoked"] is False
    assert Path(report["evidence_markdown"]).exists()


def test_backup_and_restore_verification_use_copies_without_overwriting_source(tmp_path: Path) -> None:
    backup_module = _load_script("backup_sqlite.py")
    restore_module = _load_script("verify_sqlite_restore.py")
    database = tmp_path / "source.sqlite3"
    with sqlite3.connect(database) as conn:
        conn.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute("INSERT INTO sample (name) VALUES ('alpha')")
        conn.commit()
    before_bytes = database.read_bytes()
    evidence_dir = tmp_path / "evidence"

    backup_report = backup_module.backup_sqlite_database(database, evidence_dir=evidence_dir)
    assert backup_report["sqlite"]["integrity_check"] == "ok"
    assert Path(backup_report["backup_path"]).exists()
    assert database.read_bytes() == before_bytes
    assert backup_report["overwrote_source"] is False

    restore_report = restore_module.verify_sqlite_restore(database, evidence_dir=evidence_dir)
    assert restore_report["integrity_check"] == "ok"
    assert restore_report["quick_check"] == "ok"
    assert restore_report["source_mtime_unchanged"] is True
    assert restore_report["source_size_unchanged"] is True
    assert restore_report["overwrote_source"] is False
    assert database.read_bytes() == before_bytes
    assert Path(restore_report["evidence_json"]).exists()
