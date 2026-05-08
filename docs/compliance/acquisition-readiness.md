# Acquisition Readiness

> **Status: scaffolding / internal evidence index only.**
>
> Everything below is a list of *internal scaffolding and templates*
> the project has produced so that signed external evidence has a
> place to land later. None of it is signed audit evidence, certified
> readiness, or acquirer-grade diligence material.
>
> Specifically, this document is **not**:
>
> - SOC 2, ISO, NIST CSF, or any other formally certified attestation.
> - A counsel-reviewed regulatory or securities-law opinion.
> - A signed model-validation report from an independent reviewer.
> - A buyer-grade diligence package with named owners, dated reviews,
>   restored-from-backup drill artifacts, signed access reviews,
>   signed vendor reviews, or third-party penetration-test results.
> - A representation that any control listed below has been audited
>   by an external party.
>
> This page describes evidence a technical buyer, bank partner, or
> external auditor may eventually request, and the internal scaffolding
> the project has staged toward that future ask. Treat it as a readiness
> index, not a representation of certification.

## Ready Or Started

- Canonical architecture charter in `README.md`.
- Roadmap/status tracker in `docs/roadmap-status.md`.
- Auth/approval model documented and tested.
- Provider Health separates configuration and probe state.
- Provider Health includes options-data readiness for paper review marks.
- Provider Health includes live-safe selected-provider probes for FRED macro
  context, Polygon news context, and Alpaca paper account readiness. The
  Alpaca probe is read-only account status only and does not imply live trading
  or broker routing.
- Analysis Packet context is now available for UI/email/export readiness,
  including provider/source/session provenance, FRED macro summaries, Polygon
  news headlines, paper-only safety flags, already-open context, and
  provider-supplied options mark/IV/OI/Greeks fields where available.
- Market Risk Calendar evidence now includes deterministic SPX/NDX/RUT/VIX
  index-risk signals when index snapshots are available. The signals are
  threshold-backed, auditable, and surfaced in dashboard, analysis packet, and
  scheduled strategy-report context without giving the LLM authority to change
  risk decisions.
- Strategy-report emails include a richer Analysis Packet Context section in
  HTML and plain text while preserving redaction and paper-only/no-routing
  disclaimers.
- Stored recommendation detail now supports on-demand Analysis Packet preview
  and export as sanitized JSON, Markdown, and email-safe HTML. Ad hoc packet
  email remains deferred until a dedicated rate-limited and audit-logged user
  email action exists.
- LLM explanation-only boundary documented and tested.
- Paper equity lifecycle integrity test exists.
- Options position review and options lifecycle integrity tests exist.
- Options paper structures now preserve listed-contract selection provenance
  when provider-backed options data is configured, including original target
  strike, selected listed strike, provider symbol, and snap distance.
- Options contract-readiness evidence now includes strike-snap guardrails and
  premium-source separation: fresh `quote_mid`/`last_trade` marks are required
  for paper-open pricing, while theoretical estimates and prior-close fallback
  marks remain explicitly labeled context.
- SPX/index-options review uses cash-settled/no-share-delivery labeling and
  provider path tests for index reference/snapshot behavior.
- Options expiration review and manual paper settlement evidence exists.
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
- Model inventory.
- Model validation report template and latest model-validation evidence.
- Clean source archive produced by `scripts/create_clean_release_archive.py`.

## Not Yet Audit-Ready

- No third-party SOC/ISO audit.
- No formal vendor DPAs/SOC report collection.
- No recurring restore drill history.
- No production SLO or monitoring history.
- No independent model validation report or buyer-reviewed benchmark packet.
- No legal memo from securities counsel.

## Acquisition Diligence Notes

- Keep `.env`, DB files, logs, screenshots, `.tmp`, `.claude`, and generated
  build artifacts out of buyer archives.
- Provide sanitized evidence first; share runtime data only under a diligence
  data-room process.
- Clearly label paper-only and no broker-routing scope in every product demo.
- Treat `scripts/run_model_validation.py` output as a preliminary internal
  evidence packet, not as live trading performance or a public marketing claim.
- Treat Analysis Packet and email outputs as evidence snapshots of displayed
  context, not as certification or performance validation. Missing macro,
  news, IV, open interest, Greeks, or option marks must remain explicit.
- Treat index-risk signals as readiness evidence for deterministic sit-out
  context, not as validated market-timing performance. Threshold changes should
  be documented as model-risk changes.
- Treat on-demand Analysis Packet exports as operator review artifacts. They
  should not be represented as investment advice, model validation, or live
  execution readiness.
- Label options review evidence as paper-only and provider-mark dependent.
  Current options marks use provider snapshots when plan coverage exists; no
  Black-Scholes model, internally calculated Greeks, live routing, automatic
  exits, rolls, or adjustments are included.
- Label expiration settlement as manual, paper-only lifecycle simulation.
  It is not live exercise, assignment, broker routing, or discretionary
  management.
