# Change And Release Management

MacMarket-Trader releases are readiness-gated, not certification-gated. A
release may proceed only after the operator records the evidence appropriate
for the change scope.

## Release Gates

Preferred local gate:

```powershell
python scripts/run_release_gate.py
```

Quick local gate for non-destructive evidence wiring and archive checks:

```powershell
python scripts/run_release_gate.py --quick
```

CI-safe evidence wiring check:

```powershell
python scripts/run_release_gate.py --dry-run --mock-commands
```

The release gate writes JSON and Markdown evidence under `.tmp/evidence/` and
returns nonzero on hard failures. It prints progress before each major step
and records elapsed time per step. Moderate `npm audit` findings are
report-only by default in the full gate; high or critical findings fail unless
the operator changes the configured threshold for a documented exception.

- Git status reviewed and expected.
- No conflict markers:
  `git grep -n -E '^(<<<<<<<|=======|>>>>>>>)' -- .`
- Conflict marker scanner:
  `python scripts/check_conflict_markers.py --root .`
- Diff hygiene:
  `git diff --check`
- Secret scan of tracked files or release artifact review.
- Secret scanner:
  `python scripts/scan_secrets.py --root .`
- Backend tests:
  `python -m pytest --basetemp .pytest-tmp`
- Frontend tests:
  `npm test`
- TypeScript:
  `npx tsc --noEmit`
- Dependency report only:
  `npm audit --json`
- Clean artifact dry-run:
  `python scripts/check_release_artifact.py --source .`
- Browser smoke audit for UI/runtime changes.
- Lifecycle integrity audit for paper workflow changes.
- Security regression tests for auth, ownership, origin, payload, or rate-limit changes.
- Deploy exclusion review for `.env`, DB, logs, `.tmp`, `.claude`, `.pytest-tmp`, and `*.tsbuildinfo`.
- Provider Health verification after deploy.
- OpenAI probe verification when LLM behavior is in scope.
- Rollback plan identified.

## Release Evidence

Run:

```powershell
python scripts/generate_release_evidence.py
```

Outputs:

- `.tmp/evidence/release-evidence-YYYYMMDD-HHMMSS.json`
- `.tmp/evidence/release-evidence-YYYYMMDD-HHMMSS.md`
- `.tmp/evidence/release-gate-YYYYMMDD-HHMMSS.json`
- `.tmp/evidence/release-gate-YYYYMMDD-HHMMSS.md`
- `.tmp/evidence/evidence-manifest.json`

Before deploy, review the Markdown report and machine-readable JSON for:

- failed hard gates,
- unresolved conflict or secret findings,
- dependency audit severity,
- skipped manual evidence such as browser smoke screenshots,
- explicit exceptions and owners.

## Rollback Plan Template

- Release id/commit:
- Previous known-good commit/artifact:
- DB migration impact:
- Config changes:
- Rollback command/path:
- Smoke checks after rollback:
- Owner:
