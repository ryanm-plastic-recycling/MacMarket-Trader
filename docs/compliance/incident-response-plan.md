# Incident Response Plan

This is a lightweight operational plan for private-alpha readiness. It is not
a substitute for legal, cyber insurance, or regulatory notification advice.

## Severity Levels

- SEV-0 Critical: confirmed secret exposure, unauthorized admin access, cross-user data access, production data loss, or live-trading boundary breach.
- SEV-1 High: suspected auth/IDOR issue, provider data integrity incident, restore failure, or material LLM/system misinformation.
- SEV-2 Medium: degraded provider/LLM/email service, high-cost endpoint abuse, non-sensitive release artifact issue.
- SEV-3 Low: documentation gap, false positive, or contained local-only issue.

## Suspected Secret Exposure

1. Preserve evidence without printing the secret.
2. Identify affected secret class and scope.
3. Rotate the secret in the provider console.
4. Re-deploy/restart affected runtime.
5. Search tracked history and release artifacts for exposure.
6. Record timeline, affected systems, and rotation confirmation.

## Auth Or IDOR Incident

1. Disable or suspend affected account(s) if needed.
2. Capture request path, timestamp, user id, object id, and response status.
3. Preserve logs and DB snapshot copy.
4. Add failing regression test before or with the fix.
5. Review adjacent routes for the same ownership pattern.

## Provider Outage Or Stale Data

1. Check `/admin/provider-health`.
2. Confirm whether workflows are provider, demo fallback, or blocked.
3. Communicate that recommendations/replay/orders are paper-only and source-labeled.
4. If stale/incorrect data was used, mark affected recommendations/runs as suspect in incident notes.

## LLM Bad-Output Incident

1. Confirm deterministic fields were not altered by LLM output.
2. Preserve prompt/provenance if privacy review allows.
3. Disable OpenAI provider or fall back to mock explanations if needed.
4. Add validation/prompt-injection regression if relevant.

## Paper Lifecycle Data Corruption

1. Stop new paper lifecycle mutations if corruption is active.
2. Copy DB for forensic review.
3. Run lifecycle integrity tests and targeted DB queries.
4. Restore from verified backup only after impact analysis.

## Data Loss Or Restore Incident

1. Preserve remaining DB/log evidence.
2. Run `scripts/verify_sqlite_restore.py` against the latest backup copy.
3. Document recovery point and records lost.
4. Restore only to a new temp/staging path first.

## User Notification Placeholder

Notification decision owner: TBD. Notice should state what happened, what data
may be affected, paper-only scope, mitigations taken, and recommended user
actions. Legal review required before external notification.

## Evidence Preservation

- Do not overwrite source DB during triage.
- Store incident artifacts under `.tmp/evidence/incidents/<incident-id>/`.
- Redact secrets in summaries.
- Keep command outputs and screenshots only when they do not expose secrets.

## Post-Incident Review Template

- Incident id:
- Severity:
- Start/end time:
- Detection source:
- Affected users/data/workflows:
- Root cause:
- What worked:
- What failed:
- Fixes shipped:
- Tests/evidence added:
- Follow-up owner/date:
