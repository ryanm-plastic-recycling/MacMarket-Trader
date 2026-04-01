# AGENTS.md

## Repo charter

Read `README.md` first. Treat it as the canonical architecture charter.
Do not shrink the root README into a status page.
Do not remove or dilute the HACO/HACOLT policy.

## Product rules

- MacMarket-Trader is a research-first, event-driven trading system.
- LLMs extract/explain; deterministic rules decide and size.
- HACO/HACOLT are retained as charting/context/research components, not the sole approval engine.
- Security, approval gating, auditability, and deterministic risk are mandatory.

## Working style

- Prefer small, bounded changes.
- Run tests before finishing.
- For frontend changes, ensure `npm install` and `npm run build` succeed.
- For backend changes, run `pytest`.
- Keep docs aligned with implementation.

## Guardrails

- Do not replace real auth with mock auth in production-facing paths.
- Do not point browser code to localhost for hosted deployments.
- Do not delete canonical architecture sections from the root README.
- Do not add cosmetic UI work ahead of operator workflow value.
