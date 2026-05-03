# Incident Tabletop Template

This template supports lightweight operational exercises. It does not replace
a real incident response process.

## Exercise Metadata

- Scenario:
- Date:
- Facilitator:
- Participants:
- Systems in scope:
- Evidence location:

## Required Scenarios

- OpenAI malformed output.
- Provider stale market data.
- IDOR/authorization bug.
- Secret exposure.
- Database restore.
- Paper lifecycle data corruption.

## Exercise Notes

| prompt | response |
|---|---|
| How was the incident detected? | TBD |
| What severity was assigned? | TBD |
| Who was incident commander? | TBD |
| What evidence was preserved? | TBD |
| What systems or credentials were isolated? | TBD |
| What user/operator communications were needed? | TBD |
| What rollback, restore, or disablement action was considered? | TBD |
| What was the recovery validation? | TBD |
| What controls failed or need improvement? | TBD |

## Scenario-Specific Checks

### OpenAI Malformed Output

- Confirm LLM output cannot change approval, entry, stop, target, sizing, risk
  gate, order creation, or paper position action classification.
- Capture prompt/model/provenance without secrets.

### Provider Stale Market Data

- Confirm source/fallback/staleness labels are visible.
- Confirm no silent fabricated marks are shown in provider-backed mode.

### IDOR/Authorization Bug

- Confirm affected route, object type, and ownership check.
- Preserve request ids/logs without exposing tokens.

### Secret Exposure

- Identify secret type, exposure location, and rotation owner.
- Remove artifact from distribution and document rotation evidence.

### Database Restore

- Restore only to a temp copy or replacement environment.
- Run integrity/schema checks and preserve restore evidence.

### Paper Lifecycle Data Corruption

- Preserve affected order/fill/position/trade/recommendation lineage.
- Run lifecycle audit tests before declaring recovery complete.

## Post-Exercise Review

- Lessons learned:
- Control updates:
- Open actions:
- Owners:
- Due dates:
