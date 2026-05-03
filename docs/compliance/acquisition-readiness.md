# Acquisition Readiness

This page describes evidence a technical buyer, bank partner, or external
auditor may request. It is a readiness index, not a representation of
certification.

## Ready Or Started

- Canonical architecture charter in `README.md`.
- Roadmap/status tracker in `docs/roadmap-status.md`.
- Auth/approval model documented and tested.
- Provider Health separates configuration and probe state.
- LLM explanation-only boundary documented and tested.
- Paper equity lifecycle integrity test exists.
- Defensive security hardening tests exist.
- Clean release archive generator excludes local secrets/state.
- Release evidence generator creates redacted JSON/Markdown evidence.
- Backup/restore scripts create local evidence reports.

## Buyer Evidence Packet Checklist

- Current architecture and data-flow overview.
- Control matrix.
- Risk register.
- Vendor inventory.
- Security test evidence.
- Release evidence for latest build.
- Backup and restore drill evidence.
- Incident response plan.
- Regulatory boundary memo.
- Model risk management memo.
- Clean source archive produced by `scripts/create_clean_release_archive.py`.

## Not Yet Audit-Ready

- No third-party SOC/ISO audit.
- No formal vendor DPAs/SOC report collection.
- No recurring restore drill history.
- No production SLO or monitoring history.
- No independent model validation report.
- No legal memo from securities counsel.

## Acquisition Diligence Notes

- Keep `.env`, DB files, logs, screenshots, `.tmp`, `.claude`, and generated
  build artifacts out of buyer archives.
- Provide sanitized evidence first; share runtime data only under a diligence
  data-room process.
- Clearly label paper-only and no broker-routing scope in every product demo.
