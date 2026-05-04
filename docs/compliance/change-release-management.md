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

Deployed-copy quick gate for non-git runtime folders:

```powershell
python scripts/run_release_gate.py --quick --deployed
```

The release gate writes JSON and Markdown evidence under `.tmp/evidence/` and
returns nonzero on hard failures. It prints progress before each major step
and records elapsed time per step. Moderate `npm audit` findings are
report-only by default in the full gate; high or critical findings fail unless
the operator changes the configured threshold for a documented exception.
When `--deployed`/`--no-git` is passed from a non-git deployment folder, the
gate still runs file scans and archive/evidence checks, but git-only evidence
such as `git diff --check`, branch, and commit is marked not applicable. If the
path is not the source repo root and `--deployed` is omitted, the gate fails
with a clear source-vs-deployed path message instead of dumping raw git usage
output. Quick deployed mode also marks source-only targeted pytest checks not
applicable, because deployed runtime folders may intentionally omit the test
suite.

The operational evidence regression tests are deploy-mode aware. When the same
tests run from the non-git Windows mirror, dry-run/mock gate checks that are
expected to pass call the release gate in deployed mode, while dedicated tests
still prove that non-git folders without `--deployed` fail clearly and that a
real Git source fixture runs `git diff --check`.

The Windows deployment script creates an ignored `.tmp/` folder in the runtime
mirror and runs backend pytest with `--basetemp .tmp\pytest-deploy` so deploy
tests do not depend on source checkout temp folders or machine-wide pytest
temp directories.

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
- Release gate backend test steps use ignored timestamped
  `.tmp/release-gate-pytest-*` temp directories so evidence runs are not
  blocked by stale local `.pytest-tmp` or prior release-gate workspace
  artifacts.
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
