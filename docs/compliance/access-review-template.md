# Access Review Template

Use this template for periodic private-alpha access review evidence. It is a
readiness artifact, not a certification attestation.

## Review Metadata

- Review period:
- Reviewer:
- Review date:
- Source systems reviewed:
- Evidence location:

## User And Admin Review

| user/email | role | approval status | MFA expectation | last seen/authenticated | reviewer decision | exceptions | remediation |
|---|---|---|---|---|---|---|---|
| TBD | user/admin | approved/pending/suspended/rejected | enabled/required/unknown | TBD | retain/remove/change | TBD | TBD |

## Checks

- Admin users still require `app_role=admin` and `approval_status=approved`.
- Suspended/rejected users cannot access console APIs.
- Pending users cannot access protected workflow APIs.
- Force-password-reset and role/approval changes remain admin-only.
- Any exception has an owner and due date.

## Sign-Off

- Reviewer:
- Date:
- Exceptions accepted:
- Remediation due date:
