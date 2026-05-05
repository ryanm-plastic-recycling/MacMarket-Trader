# MacMarket-Trader Roadmap Reality Audit — 2026-05-05

Audit conducted on the source repository at
`C:\Users\ryanm\OneDrive\Documents\GitHub\MacMarket-Trader`.
Branch `main`, HEAD `a637add3a7fb4896f3f182466fde5e8a55e288c6` ("test"),
working tree clean. The deployed mirror at `C:\Dashboard\MacMarket-Trader`
was **not** examined; all evidence below comes from the source tree.

## 0. Executive Summary

**Overall verdict.** MacMarket-Trader is meaningfully more capable than its
`README.md` "v1 mandate" implies, and most of the recent post-Phase-8
work — index-aware risk calendar, options paper lifecycle, Active Position
Review, expected-range visualization, compliance scaffolding — is **really
implemented in code and exercised by pytest**. However, the project's two
self-tracking documents (`CLAUDE.md` and `docs/roadmap-status.md`) are
dramatically out of date, and several smaller assertions (test counts, a
"poll-alpaca-fills" CLI, a "save_alternative not implemented" gap) are
demonstrably wrong.

**Biggest trust gaps.**

1. CLAUDE.md says pytest is at **271 collected**, vitest at **199**,
   Playwright at **31**. Reality: pytest **469**, vitest ~**243**,
   Playwright **32**. Both files claim "last verified 2026-04-30" yet many
   of the test files added on 2026-05-03/04 (risk calendar index pass,
   options structure review, expiration settlement, indices preview,
   options contract selection metadata) are clearly counted in the new
   numbers. The project's own dashboard is materially under-counting its
   own work.
2. CLAUDE.md says `python -m macmarket_trader.cli poll-alpaca-fills` polls
   Alpaca paper fills. The CLI in `src/macmarket_trader/cli.py` exposes
   only `health`, `generate-sample-recommendation`, `run-sample-replay`,
   `init-db`, `seed-demo-data`, `run-due-strategy-schedules`. The
   advertised command **does not exist**.
3. CLAUDE.md and `docs/roadmap-status.md` both list `save_alternative` as
   "backend action variant not yet implemented (UI button exists,
   disabled)." The promote endpoint **does** accept `action="save_alternative"`,
   the UI button **does** call it, and `tests/test_recommendations_api.py::test_user_ranked_queue_candidate_can_be_saved_as_alternative`
   asserts the full happy path. The doc gap is stale.
4. Roadmap labels "Phases 0–9 complete." Code does match this for the
   *current scoped* paper-first / research-first behavior, but Phase 11
   (compliance/acquisition-readiness) and Phase 12 (model validation)
   appear in the changelog as "complete foundations" while
   `Open Items`/`Current Phase Status` in CLAUDE.md still describe Phase
   10 as "next." There is no consolidated phase ledger; the roadmap is a
   chronological diary, not a status board.
5. The audit-readiness language in `docs/compliance/` is heavier than
   the underlying evidence supports. The directory contains real
   templates, a control matrix, a regulatory-boundary memo, and a
   release-gate. None of it has named owners, signed-off access reviews,
   or restored-from-backup drill evidence committed to the repo.

**Biggest technical gaps.**

- Migrations 0006 (commission_and_net_pnl) and 0010 (option contract
  selection metadata) only target the leg/order *option* tables. The
  `apply_schema_updates()` shim at startup masks any model-vs-DB drift
  for nullable columns. This is convenient but means the Alembic
  migration set alone is **not** a faithful schema description for code
  paths that boot via the FastAPI lifespan. Acquisition-grade diligence
  would flag this.
- `BROKER_PROVIDER=alpaca` mode is wired in `data/providers/broker.py`
  with `place_paper_order` calling `POST /v2/orders`. There is no live
  trading guard *outside* of the `BROKER_PROVIDER` env switch — if that
  switch were flipped, paper orders to Alpaca would actually go out.
  The "no live trading" claim is enforced by configuration, not by an
  affirmative refusal in `paper_broker.py`.
- Options remain paper-only with research-only assignment/exercise/settle
  semantics. The settle-expiration route exists and `tests/test_options_paper_structure_review.py`
  exercises it. The repeated roadmap claim that "expiration settlement
  remains deferred" is therefore **partially overstated**: a deterministic
  settlement endpoint *is* live, even though it remains paper-only and
  manual.

**Documentation overstatements.**

- "271/199/31" test counts in CLAUDE.md.
- "poll-alpaca-fills" CLI in CLAUDE.md.
- "save_alternative not yet implemented" in CLAUDE.md and
  `docs/roadmap-status.md`.
- "Cancel staged order pre-fill, reopen closed position 5-min window"
  documented as fully tested workflow gates — there are 4 e2e tests for
  cancel/reopen and ~9 close-lifecycle tests, but the underlying
  `display_id` collision risk inside the same minute is acknowledged in
  CLAUDE.md and unaddressed in code.
- Phase 11 acquisition-readiness implies acquirer-grade evidence, but
  the supporting docs are templates and the release gate is a script —
  no signed evidence is in-tree.

**Release / audit readiness.** Internal-grade. The release gate runs,
the compliance docs exist as templates, and the operational evidence
script writes JSON+MD reports. Nothing in the tree shows a third party
has reviewed any of it. Suitable for "we are operating responsibly in
private alpha." Not suitable for SOC 2 / ISO / regulator submission and
not yet suitable for acquirer diligence as published.

**Acquisition readiness.** Pre-diligence-grade. The product's *engineering*
discipline (deterministic engines, point-in-time, audit trails, paper-only,
LLM-fenced) is strong and verifiable. The product's *governance*
discipline (model validation, signed reviews, named risk owners, drift
monitoring, signed counsel review) exists only as scaffolding and would
not survive a serious diligence Q&A round.

---

## 1. Audit Scope and Method

- **Repo path:** `C:\Users\ryanm\OneDrive\Documents\GitHub\MacMarket-Trader`
- **Branch:** `main`
- **HEAD:** `a637add3a7fb4896f3f182466fde5e8a55e288c6` ("test")
- **Working tree:** clean at audit start (`git status` empty).
- **Deployed mirror examined?** No — `C:\Dashboard\MacMarket-Trader` was
  intentionally not touched.

Commands run during audit:

- `git status --short`, `git log -n 30 --oneline`, `git rev-parse HEAD`
- `git log -1 --format="%h %ad" --date=short -- <doc>` for each major doc
- `git grep -n -E '<<<<<<<|=======|>>>>>>>'` (no real conflict markers)
- `python -m pytest --collect-only -q` (exit 0, **469 tests collected**)
- Repo-wide Greps for: `BROKER_PROVIDER`, `OpenAI|openai_provider`,
  `expected_range|expected_move`, `apply_schema_updates`,
  `app_role|approval_status`, `paper_max_order_notional`,
  `RTH|regular_hours|RegularHours`, `index_options_data|indices_data|index_context`,
  `IndexContextSummary`, `save_alternative`, `poll-alpaca-fills`,
  `place_paper_order`.
- Module/file size scans (`wc -l`).
- Reads of the FastAPI lifespan/main, security middleware, auth deps,
  CLI, broker provider, openai provider, options modules, index_risk,
  recent migrations, all roadmap-related docs.

Commands intentionally **not run**:

- `pytest` full execution — collect-only is sufficient for inventory and
  avoided possible side effects on local test fixtures and `.tmp/`.
- `cd apps/web && npm run build` / `npx tsc --noEmit` / `npm test --run` —
  not executed in this audit pass to avoid touching `node_modules`,
  `.next`, or generating test artifacts. Frontend test counts were taken
  from `Grep` of `^\s*(test|it)\s*\(` in `apps/web/**/*.test.{ts,tsx}`.
- `python scripts/run_release_gate.py --quick` — would write to
  `.tmp/evidence/` and could affect local state.
- Any Alpaca / Polygon / OpenAI / FRED / Resend live probes.
- Any deployed-mirror validation, deployed UI smoke, or
  `https://macmarket.io` browser session.

**Limitations.** This audit is source-only. It cannot verify deployed
runtime behavior, deployed `.env` contents, Cloudflare Access policy,
Clerk-side approval flow, scheduled-task registration, real email
delivery, real provider responses, or real DB row contents.

---

## 2. Roadmap Inventory

All paths relative to repo root. "Last commit" is from
`git log -1 --format=%h\ %ad --date=short -- <path>`.

| Path | Last commit | Declared scope | Status claims summary | Notes |
|---|---|---|---|---|
| `README.md` | `dc3e3fb` 2026-04-30 | Canonical architecture charter | Mandate, design constraints, market-mode policy, options scope, success criteria | Names current options scope "scoped paper-first" — does not duplicate roadmap-status |
| `docs/roadmap-status.md` | `c1f532c` 2026-05-04 | Chronological roadmap diary, phase-by-phase status | Claims Phases 0–9 complete; Phase 10 is the active planning/polish track; Phase 11 (trust/compliance) and Phase 12 (model validation) listed as "complete foundations" | 2418-line chronological diary. Hard to read as a status board. Inconsistent with CLAUDE.md test counts. |
| `CLAUDE.md` | `4a9da27` 2026-05-01 | Claude Code session context | Phases 0–9 complete; pytest 271 / vitest 199 / Playwright 31 | Tests counts are stale (true: 469/~243/32). Mentions a `poll-alpaca-fills` CLI that does not exist. |
| `docs/architecture.md` | `3de4400` 2026-03-31 | Pipeline / subsystems sketch | Foundational; not phase-tagged | 39 lines. Does not reflect later index/risk-calendar/options work. |
| `docs/options-architecture.md` | `5671b27` 2026-04-30 | Options master plan | Multi-phase plan; defined-risk first; paper-only | Backed by code in `src/macmarket_trader/options/` |
| `docs/options-paper-lifecycle-design.md` | `6f487be` 2026-05-03 | Open/close persistence design | Maps to `paper_option_*` tables, repository, and routes | Code agrees |
| `docs/options-replay-design.md` | `0cfd5c3` 2026-04-29 | Read-only payoff preview design | Non-persisted | Backed by `options/replay_preview.py`, `options/payoff.py` |
| `docs/options-risk-ux-design.md` | `fc3ecae` 2026-04-30 | Operator risk-summary panel | Recommendations options preview | Backed by `apps/web/components/recommendations/options-research-preview.tsx` and tests |
| `docs/options-test-plan.md` | `3f4d897` 2026-04-30 | Phase-8 test matrix | Maps to options tests | Most listed assertions traced to existing tests |
| `docs/active-paper-position-management-design.md` | `aad7e55` 2026-05-03 | Active equity review design | `GET /user/paper-positions/review` | Endpoint exists in `admin.py:4728`; tests in `tests/test_active_paper_position_review.py` |
| `docs/market-risk-calendar-design.md` | `c1f532c` 2026-05-04 | Risk calendar + sit-out gate | Index-aware as of 2026-05-04 | Backed by `risk_calendar/service.py`, `index_risk.py`, `tests/test_risk_calendar.py` (557 lines) |
| `docs/rth-intraday-normalization-design.md` | `1636559` 2026-05-01 | RTH 1H/4H rebucketing | Paper/research-only | Source: `data/providers/market_data.py`, `risk_calendar/service.py`, `domain/enums.py` |
| `docs/symbol-watchlist-design.md` | `dc3e3fb` 2026-04-30 | Future symbol/watchlist design | 10W series checkpoint | Code includes `tests/test_symbol_universe_*` and `alembic/...0008_symbol_universe_schema.py` |
| `docs/alpha-user-welcome.md` | `c1f532c` 2026-05-04 | Welcome guide rendered at `/welcome` | Updated 2026-05-04 | Read by `apps/web/app/(console)/welcome/page.tsx` via `welcome-client.tsx` |
| `docs/scheduled-reports.md` | `e667d26` 2026-04-04 | Recurring strategy report design | Mostly accurate; pre-10W | |
| `docs/private-alpha-operator-runbook.md` | `b08a121` 2026-04-28 | Deployment + day-2 runbook | References scheduled tasks, backup, restore | Does not reflect 10W or risk-calendar index pass |
| `docs/auth-and-approval.md` | `4e13cac` 2026-04-03 | Clerk + local DB policy | Constitutional; matches `api/deps/auth.py` | |
| `docs/provider-architecture.md` | `f7998cb` 2026-04-02 | Provider/fallback truth | Pre-Polygon-hardening |
| `docs/market-data.md` | `4032824` 2026-04-03 | Market data shape | Pre-RTH normalization |
| `docs/compliance/README.md` | `79ced77` 2026-05-03 | Compliance scaffolding index | Lists templates + readiness docs | Templates only |
| `docs/compliance/acquisition-readiness.md` | `c1f532c` 2026-05-04 | Acquirer-facing readiness checklist | Self-attested | No signed evidence |
| `docs/compliance/control-matrix.md` | `2301c6c` 2026-05-03 | SOC2-style control matrix | Self-attested | |
| `docs/compliance/regulatory-boundary-memo.md` | `2301c6c` 2026-05-03 | "Not yet a regulated activity" memo | Self-attested | Not counsel-reviewed |
| `docs/compliance/model-inventory.md` | `ac71ff4` 2026-05-03 | Internal model registry | Foundational | |
| `docs/compliance/model-validation-report-template.md` | `ac71ff4` 2026-05-03 | Validation report template | Template only | |
| `docs/compliance/risk-register.md` | `2301c6c` 2026-05-03 | Risk register | Owners not assigned | |
| `docs/compliance/incident-response-plan.md` / `incident-tabletop-template.md` | `2301c6c` 2026-05-03 | IR scaffolding | No exercise evidence in-tree | |
| `docs/compliance/backup-restore-dr-plan.md` | `2301c6c` 2026-05-03 | DR runbook | No drill evidence in-tree | |
| `docs/compliance/deployed-smoke-testing.md` | `d7d8130` 2026-05-04 | Deployed UI smoke procedure | Backed by `apps/web/tests/e2e/deployed-smoke.spec.ts` and `playwright.deployed-smoke.config.ts` | Skips cleanly when smoke auth not configured |

No `AGENTS.md` is present.

---

## 3. Migration / Schema Inventory

10 Alembic revisions; head is `20260503_0010`. The runtime additionally
runs `apply_schema_updates()` from `src/macmarket_trader/storage/db.py`,
which `ALTER TABLE … ADD COLUMN`s any model column that is missing
(nullable adds bypass formal Alembic).

| Revision | Date | Purpose (inferred) | Tables affected | Tests covering it | Risk / gap |
|---|---|---|---|---|---|
| `20260331_0001` | 2026-03-31 | Initial schema = `Base.metadata.create_all` | All tables defined at the time | Implicit (every test that bootstraps SQLite) | Snapshot-style migration; not granular |
| `20260413_0002` | 2026-04-13 | User lineage workflow tables | `app_users`, lineage / workflow rows | Auth + identity tests, e2e workflow tests | OK |
| `20260414_0003` | 2026-04-14 | Guided lineage columns | Recs / replay / orders | `tests/test_phase1_workflow_hardening.py` | OK |
| `20260414_0004` | 2026-04-14 | Replay source lineage columns | `replay_runs`, `replay_steps` | `tests/test_replay_engine.py`, `tests/test_phase1_workflow_hardening.py` | OK |
| `20260415_0005` | 2026-04-15 | `has_stageable_candidate` + paper portfolio scaffold | `replay_runs`, paper portfolio tables | `tests/test_replay_engine.py` and order/lifecycle tests | OK |
| `20260429_0006` | 2026-04-29 | Commission + net P&L on paper trades | `paper_trades`, `app_users` (commission cols) | `tests/test_close_trade_lifecycle.py`, `tests/test_phase7_fee_previews.py` | OK |
| `20260429_0007` | 2026-04-29 | Options paper lifecycle schema | `paper_option_orders`, `paper_option_order_legs`, `paper_option_positions`, `paper_option_position_legs`, `paper_option_trades`, `paper_option_trade_legs` | `tests/test_options_paper_schema.py`, `tests/test_options_paper_repository.py` | 228-line migration, well covered |
| `20260430_0008` | 2026-04-30 | Symbol universe additive schema | `user_symbol_universe`, `watchlist_symbols` (nullable provider metadata, indexes, uniqueness) | `tests/test_symbol_universe_schema.py`, `tests/test_symbol_universe_repository.py`, `tests/test_symbol_universe_preview.py` | OK; nullable. Production write paths still use legacy `watchlists.symbols` JSON. |
| `20260502_0009` | 2026-05-02 | `paper_max_order_notional` per-user | `app_users` | `tests/test_paper_order_sizing_and_reset.py` | OK |
| `20260503_0010` | 2026-05-03 | Listed option contract selection metadata on leg tables | `paper_option_*_legs` | `tests/test_options_paper_repository.py`, `tests/test_options_paper_close_lifecycle.py`, `tests/test_options_paper_open_lifecycle.py` | OK |

**Drift / risk flags.**

- Models in `src/macmarket_trader/domain/models.py` declare 32 ORM
  classes (`grep -E '^class \w+\(Base\)'`). The 10 migrations do not
  cover every nullable column drift — `apply_schema_updates()` papers
  over the gap at startup. This is documented in `CLAUDE.md` ("nullable
  columns added at startup, no manual Alembic needed") but is **a
  governance gap** for any acquirer-style review of schema versioning.
- No migration is named for the index-risk fields (`IndexRiskSignals`),
  index_data_stale fields, settle-expiration fields, expected-range
  method/status fields. These all flow through Pydantic schemas and
  JSON columns rather than dedicated DB columns, which is reasonable —
  but it means the migration ledger does **not** show the architecture
  evolution.
- All foreign-key-shaped columns I sampled (`user_id`, `recommendation_id`,
  `position_id`, `replay_run_id`) appear as indexed in `domain/models.py`
  via `Index(...)` declarations or `index=True` on the column. No
  explicit missing-index issue surfaced.

---

## 4. Test Inventory

Total backend tests: **469** (verified by `pytest --collect-only -q`).
Total frontend test/it counts: **243** across **43 vitest files**
(verified by `Grep -E '^\s*(test|it)\s*\('`).
Total Playwright e2e `test(...)` calls: **32** across **7 spec files**.

CLAUDE.md still cites 271/199/31. **Documentation lag is significant.**

By domain (counts are `def test_` per file):

| Domain | File(s) | Tests | Claims they prove | What they don't prove |
|---|---|---|---|---|
| Auth / approval / identity | `test_auth_approval_api.py`, `test_user_identity_reconciliation.py` | 30 + 6 | local DB authoritative, Clerk identity merge, invited→Clerk reconciliation | Production Clerk JWT verification under all keying scenarios |
| Security authorization | `test_security_authorization.py`, `test_security_hardening.py` | 6 + 8 | admin route protection, suspended user blocks, owner-scoping | Real Cloudflare Access policy, real CSP enforcement |
| Provider registry / phase 4 | `test_phase4_providers.py`, `test_provider_registry.py` | 29 + 5 | Mock + Polygon adapter behavior, Alpaca paper post-shape | No real Polygon/Alpaca live calls |
| Market data + RTH | `test_market_data_service.py` | 57 | RTH bucket math, intraday normalization, indices snapshot, options snapshot path | No real entitlement responses |
| Charts / HACO | `test_charts_api.py`, `test_indicators_haco.py` | 11 + 2 | HACO/HACOLT indicator math, payload shape | No frontend chart rendering proof |
| Recommendations / queue | `test_recommendations_api.py` | 13 | promote `make_active`/`save_alternative`, ranking provenance, generate flow | No live LLM, no full Polygon |
| Replay | `test_replay_engine.py` | 2 | deterministic replay shape | Limited; replay hardening covered indirectly |
| Equity paper lifecycle | `test_close_trade_lifecycle.py`, `test_paper_equity_lifecycle_integrity.py`, `test_paper_order_sizing_and_reset.py`, `test_oms.py` | 17 + 1 + 5 + 2 | open/close lifecycle, gross/net P&L, max-notional cap, sandbox reset | No real Alpaca |
| Active position review | `test_active_paper_position_review.py` | 10 | `GET /user/paper-positions/review` returns deterministic states (`hold_valid`, `stop_triggered`, etc.) | No live data |
| Options research preview | `test_options_payoff.py`, `test_options_replay_preview.py` | 13 + 6 | payoff math, replay-preview contract, blocked-naked-short | Not live IV/skew |
| Options paper lifecycle | `test_options_paper_schema.py`, `test_options_paper_repository.py`, `test_options_paper_open_lifecycle.py`, `test_options_paper_close_lifecycle.py`, `test_options_paper_positions_list.py`, `test_options_lifecycle_integrity.py` | 2+4+7+9+1+1 | open/close persistence, leg math, contract commissions, integrity audit | No real broker |
| Options structure review (mark-to-market + settlement) | `test_options_paper_structure_review.py` | 23 | mark-method precedence, missing-data, expiration moneyness, settle-expiration endpoint | No live Greeks |
| Risk calendar (incl. index-aware) | `test_risk_calendar.py` | 19 | macro/earnings/vol assessment, sit-out, index-risk signal extraction | No live macro/earnings calendars |
| LLM | `test_llm_integration.py` | 28 | mock + schema validation + provenance + opportunity intelligence | Real OpenAI behavior gated to env |
| Strategy reports + analysis packets | `test_strategy_reports.py`, `test_analysis_packets.py` | 24 + 9 | rank + email payload, packet sanitization, expected-range method gating | Real Resend delivery |
| Symbol universe + watchlists | `test_symbol_universe_schema.py`, `test_symbol_universe_repository.py`, `test_symbol_universe_preview.py`, `test_watchlists.py` | 3+7+8+8 | new normalized model, resolver, preview API, legacy JSON compatibility | Production UI not wired to new tables |
| Compliance / operational evidence | `test_compliance_readiness.py`, `test_operational_evidence.py` | 6 + 12 | doc presence, redaction, archive exclusions, deployed-mode toggles | Not external counsel review |
| Display ID + user settings | `test_display_id_and_user_settings.py` | 22 | `display_id` format, settings round-trip | Same-minute collision risk acknowledged separately |
| Email templates | `test_email_templates.py` | 8 | inlined logo, copy hygiene | Not actual deliverability |
| Misc engines | `test_setup_engine.py`, `test_regime_engine.py`, `test_risk_engine.py`, `test_quality_gates.py`, `test_phase1_workflow_hardening.py`, `test_phase7_fee_previews.py`, `test_market_mode_foundation.py`, `test_storage.py`, `test_e2e_workflows.py`, `test_health.py`, `test_cli.py` | 1+1+5+2+13+2+4+3+5+1+2 | engine math, fee preview, workflow lineage, health, CLI parsing | OK |
| Frontend (vitest) | 43 files | ~243 tests | Component rendering, helper math, route proxy auth, lineage formatting, glossary content, options preview | Not real Clerk session, not real backend |
| E2E (Playwright local) | 7 specs | 32 tests | Guided workflow, lineage threading, cancel-staged + reopen-closed, close lifecycle | Not deployed, not real auth |

**Skipped / xfail / shallow.** No `@pytest.mark.skip`, `xfail`, or `slow`
markers found in `tests/`. Some integrity tests are necessarily
import-and-shape rather than behavior (`test_health.py`,
`test_market_mode_foundation.py`). The deployed Playwright spec
`apps/web/tests/e2e/deployed-smoke.spec.ts` self-skips when smoke auth
is not configured, by design.

---

## 5. Phase-by-Phase Verification

| Phase | Claim | Actual state | Evidence | Verdict |
|---|---|---|---|---|
| Phase 0 — Foundation | FastAPI backend, Next.js frontend, SQLite, Clerk auth, Windows deploy bridge | All present | `src/macmarket_trader/api/main.py`, `apps/web/app/`, `alembic/`, `scripts/deploy_windows.bat` | ✅ matches |
| Phase 1 — Core workflow | Analyze → Recommendation → Replay → Paper Order with deterministic recommendation engine | Present | `src/macmarket_trader/service.py`, `replay/engine.py`, e2e specs `phase1-closeout.spec.ts`, `phase5-guided-lineage.spec.ts`; `tests/test_phase1_workflow_hardening.py` (13) | ✅ matches |
| Phase 2 — Identity + auth | Invite-only, role system, identity reconciliation, branded transactional emails | Present | `api/deps/auth.py`, `data/providers/clerk_profile.py`, `email_templates.py`, `tests/test_auth_approval_api.py` (30), `tests/test_user_identity_reconciliation.py` (6), `tests/test_email_templates.py` (8) | ✅ matches |
| Phase 3 — Market data + providers | Polygon market data, fallback truth, demo fallback, index normalization | Present | `data/providers/market_data.py` (2224 lines), `tests/test_market_data_service.py` (57), `tests/test_provider_registry.py` (5) | ✅ matches |
| Phase 4 — Recommendations + replay | Promote/make-active + save-as-alternative; replay validation gate; ranked queue lineage | Both `make_active` and `save_alternative` implemented (despite docs listing the latter as TODO) | `src/macmarket_trader/api/routes/admin.py` promote handlers; `tests/test_recommendations_api.py::test_user_ranked_queue_candidate_can_be_saved_as_alternative` (lines 383–409); `apps/web/app/(console)/recommendations/page.tsx:682` calls `action: "save_alternative"` | ✅ matches (docs overstate the gap) |
| Phase 5 — Operator console polish | Guided mode, sticky banner, auto-advance CTAs, brand pre-auth, welcome guide | Present | `components/active-trade-banner.tsx`, `components/workflow-banner.tsx`, `components/guided-step-rail.tsx`, `app/(console)/welcome/page.tsx`, `tests/e2e/phase5-guided-lineage.spec.ts` (9 tests), `phase6-auto-advance.spec.ts` | ✅ matches |
| Phase 6 — Close-trade lifecycle + Pass 4 | Open positions list, close ticket, closed-trades blotter, cancel staged + reopen closed (5-min undo), `display_id`, per-user risk dollars | Present | `tests/e2e/phase6-close-lifecycle.spec.ts` (9), `phase6-cancel-reopen.spec.ts` (4), `tests/test_close_trade_lifecycle.py` (17), `tests/test_display_id_and_user_settings.py` (22) | ✅ matches; the `display_id` same-minute collision risk is a known and acknowledged gap |
| Phase 7 — Commission/fee/provider readiness + Active Position Review | 7A–7D commission/fee/provider; 7E review; 7F sizing + sandbox reset | Present | `tests/test_phase7_fee_previews.py` (2), `tests/test_active_paper_position_review.py` (10), `tests/test_paper_order_sizing_and_reset.py` (5), migration 0006 + 0009 | ✅ matches |
| Phase 8 — Options research → paper parity | Read-only research preview, read-only payoff preview, paper-only open/manual-close lifecycle, contract commissions, operator UI | Present | `src/macmarket_trader/options/{payoff,replay_preview,paper_open,paper_close,paper_contracts}.py`; routes at `admin.py:1503/1511/1529/1582/1603`; migration 0007; tests above | ✅ matches |
| Phase 9 — Options operator parity, source/as-of, Expected Range visualization | 9A planning, 9B durable Orders, 9C provider/source/as-of, 9D Expected Range bar | Present | `apps/web/components/options/expected-range-visualization.tsx` + `.test.tsx` (6 tests), `apps/web/components/orders/paper-options-positions-section.tsx` + 6 tests, listing route `admin.py:1603` | ✅ matches |
| Phase 10 — Deferred-work planning + safe polish | 10A1, 10B1, 10C1–10C5, 10W1–10W8D | Mostly present, with caveats | `apps/web/lib/glossary.ts`, `components/ui/metric-help.tsx`, route `/user/symbol-universe/preview` (admin.py:5381), `tests/test_symbol_universe_*` | ⚠️ partial — 10W8D claims a "selector closure audit" that is implemented as a single backend assertion plus docs/test alignment; "broader 10A/10B/10C/10W9-10W10/10G" remains open |
| Phase 11 — Trust, compliance, acquisition readiness foundation | Compliance docs scaffold, release gate, evidence scripts | Present, but template-grade | `docs/compliance/`, `scripts/run_release_gate.py`, `scripts/scan_secrets.py`, `scripts/check_release_artifact.py`, `scripts/generate_release_evidence.py`; `tests/test_compliance_readiness.py` (6) | ⚠️ partial — templates exist, no signed evidence in-tree |
| Phase 11B — Operational evidence automation | Release gate orchestrating scans, tests, npm-audit, archive dry-run | Present | `scripts/run_release_gate.py`, `scripts/run_release_gate.ps1`, `tests/test_operational_evidence.py` (12) | ✅ matches |
| Phase 12 — Model validation foundation | Model inventory, validation report template, local validation script | Present | `docs/compliance/model-inventory.md`, `docs/compliance/model-validation-report-template.md`, `scripts/run_model_validation.py`, `tests/test_model_validation.py` (6) | ⚠️ partial — script writes evidence; no committed evidence; no benchmark validation packets in-tree |
| Index-aware Market Risk Calendar (2026-05-04) | VIX level/spike, SPX/NDX/RUT day changes, NDX/RUT relative strength, dispersion, risk-appetite, stale flags can elevate calendar to caution/restricted | Present | `src/macmarket_trader/index_risk.py` (268 lines), `risk_calendar/service.py` (515 lines), `tests/test_risk_calendar.py` (19 tests, 557 lines) | ✅ matches |
| Indices Starter integration (`indices_data` probe + `IndexContextSummary`) | Provider Health adds `indices_data` and `index_options_data`; Index Context surfaces in dashboard / Analysis Packet / Opportunity Intelligence | Present | `data/providers/market_data.py:1495 indices_data_health(...)`, `admin.py:6235 _indices_data_readiness(...)`, `admin.py:6421 _index_options_data_readiness(...)`, `analysis_packets.py` (1070 lines) uses `IndexContextSummary` | ✅ matches |
| Active paper position management endpoint | `GET /user/paper-positions/review` returns one review per open equity paper position, with hold/stop/time-stop classifications | Implemented | `admin.py:4728`, `apps/web/app/api/user/paper-positions/review/route.ts`, `tests/test_active_paper_position_review.py` (10) | ✅ matches |
| Already-open recommendation awareness | Queue/persisted recs decorate with `already_open`, position id, average entry, review path | Implemented | `tests/test_active_paper_position_review.py`, `apps/web/lib/recommendations.test.ts` covers `already_open` fields | ✅ matches |
| Symbol universe additive schema (`10W4`/`10W5`) | New tables exist but production write paths still use legacy `watchlists.symbols` JSON | Implemented exactly as documented | migration 0008, models 281 (`UserSymbolUniverseModel`)/315 (`WatchlistSymbolModel`), `tests/test_symbol_universe_schema.py`, `tests/test_symbol_universe_repository.py` | ✅ matches |
| Universe selector preview API (`10W8A`–`10W8D`) | Preview-only, user-scoped, no provider calls, no schedule/watchlist mutation, no recommendation submit | Implemented | `admin.py:5381 @user_router.post("/symbol-universe/preview")`; `tests/test_symbol_universe_preview.py` (8) including `test_preview_does_not_create_recommendations_or_mutate_watchlists_or_schedules` | ✅ matches |
| Strict listed-contract options structure validation (2026-05-03) | Iron-condor and verticals require provider-resolved listed contracts; older synthetic structures are unmarkable | Implemented | `src/macmarket_trader/options/paper_contracts.py`, `paper_open.py`; `tests/test_options_paper_open_lifecycle.py` includes provider-not-found and incomplete-chain coverage | ✅ matches |
| Provider-backed options marks for review (2026-05-03) | Mark precedence: bid/ask mid → last trade → prior close (stale fallback) → unavailable; missing/stale data does not fabricate P&L | Implemented | `data/providers/market_data.py` snapshot path; `tests/test_options_paper_structure_review.py` (23 tests, 755 lines) | ✅ matches |
| Options expiration / paper settlement preview (2026-05-03) | Manual settlement endpoint with `SETTLE` confirmation, current-user scope, intrinsic-value math; no auto exercise/assignment | Implemented | `admin.py:1550 ".../settle-expiration"`; `tests/test_options_paper_structure_review.py` covers settlement | ✅ matches (the roadmap's repeated "expiration settlement deferred" wording is now **partly stale** — manual settlement is live; full settlement automation is not) |
| Defensive security pass 2 (2026-05-03) | Origin validation on browser mutations, in-memory rate limits, payload caps, security headers, FastAPI docs disabled in prod, masked admin invite tokens | Implemented | `src/macmarket_trader/api/security.py` (219 lines), `api/main.py:54 security_guardrails(...)` middleware, `apps/web/next.config.ts` security headers, `tests/test_security_hardening.py` (8) | ✅ matches |
| Phase 11B operational evidence | Release gate, secret scan, conflict scan, archive scan, evidence generator | Implemented | `scripts/run_release_gate.py`, `scripts/scan_secrets.py`, `scripts/check_conflict_markers.py`, `scripts/check_release_artifact.py`, `scripts/generate_release_evidence.py`, `.github/workflows/ci.yml` references mock-only env | ✅ matches |
| Phase 12 model validation | `scripts/run_model_validation.py` writes `.tmp/evidence/model-validation-*.json/.md` from local data only | Implemented | `scripts/run_model_validation.py`, `tests/test_model_validation.py` (6) | ⚠️ partial — script real, but no committed evidence; SPY/QQQ baseline reachable only when local `daily_bars` exist |
| OpenAI provider safety (2026-05-03 fix) | Optional, schema-validated, deterministic fallback, sanitized errors, never sets entry/stop/target/sizing/approval/routing | Implemented | `src/macmarket_trader/llm/openai_provider.py` (489 lines), explicit `RECOMMENDATION_GUARDRAIL_FIELDS = ["entry","stop","target","sizing","approval","order_routing"]`, redaction in `_redact(...)`, `tests/test_llm_integration.py` (28) | ✅ matches |
| Deployed browser smoke (2026-05-04) | Cloudflare Access service-token or storage-state path, evidence written under `.tmp/evidence/deployed-ui-smoke-*`, skips cleanly | Implemented; not run in this audit | `apps/web/tests/e2e/deployed-smoke.spec.ts`, `apps/web/playwright.deployed-smoke.config.ts`, `apps/web/tests/deployed-smoke-utils.ts`, `docs/compliance/deployed-smoke-testing.md` | ❓ unverifiable in this audit (would require CF Access service token + a stored test-user auth state) |
| Alpha smoke `scripts/smoke_alpha.py` | Local Playwright-driven smoke against mock-auth DB | Present | `scripts/smoke_alpha.py` | ❓ unverifiable without running |

---

## 6. High-Scrutiny Review: Work Since Phase 8

| Area | Claimed behavior | Verified behavior | Evidence | Remaining gap | Verdict |
|---|---|---|---|---|---|
| Options architecture & module layout | Dedicated `options/` package; payoff math is pure; replay preview separate from equity replay; paper persistence separate from equity persistence | Confirmed: 5 modules (`payoff.py` 528, `replay_preview.py` 343, `paper_contracts.py` 110, `paper_open.py` 40, `paper_close.py` 141) and 6 dedicated `paper_option_*` tables in `models.py:429-547` | `src/macmarket_trader/options/`, `src/macmarket_trader/domain/models.py:429+` | None within the *current* paper-only scope | ✅ matches |
| Options replay / payoff preview | Read-only, non-persisted; rejects naked shorts; iron condor + vertical debit + long single | Confirmed | `tests/test_options_payoff.py` (13), `tests/test_options_replay_preview.py` (6) | No persistence into `replay_runs` (intentionally) | ✅ matches |
| Options paper lifecycle (open/manual close) | Dedicated tables, structured legs, contract-commission accounting, gross/net P&L, idempotent close, cross-user blocked | Confirmed | `tests/test_options_paper_open_lifecycle.py` (7), `tests/test_options_paper_close_lifecycle.py` (9), `tests/test_options_lifecycle_integrity.py` (1) | Partial fills, naked shorts, assignment/exercise = explicitly deferred | ✅ matches |
| Options commissions | `commission_per_contract` per leg per contract; net P&L stored on trade legs | Confirmed | migration 0006 + 0007, `tests/test_options_paper_close_lifecycle.py`, `tests/test_phase7_fee_previews.py` | None | ✅ matches |
| Expected Range (research-only) | `iv_1sigma`, `atm_straddle_mid`, `equity_realized_vol_1sigma`, `equity_atr_projection`, `crypto_realized_vol_1sigma` allowed by schema; `computed`/`blocked`/`omitted` status | Schema confirms it (`domain/schemas.py:679`), `iv_1sigma` is emitted (admin.py:371,382 and `analysis_packets.py`), `atm_straddle_mid` is **not yet emitted** (only consumed/tested via `tests/test_strategy_reports.py:807-818`) | `domain/schemas.py:679`, `tests/test_strategy_reports.py:195` (live emit), `tests/test_strategy_reports.py:807-818` (synthetic ingest) | The "atm_straddle_mid not yet emitted" caveat in CLAUDE.md and `roadmap-status.md` is correct | ⚠️ partial (matches docs) |
| Intraday timeframe correctness + RTH normalization | 1H/4H provider-backed flows fetch 30m, filter 9:30–16:00 ET, re-aggregate; intraday timestamps preserved | Confirmed | `data/providers/market_data.py` (RTH bucket helpers), `risk_calendar/service.py` references session policy, `domain/enums.py` exposes session policy | None | ✅ matches |
| Active equity position review (`/user/paper-positions/review`) | One review per open paper equity position, with `hold_valid`, `stop_triggered`, `target_reached_*`, `time_stop_*`, `scale_in_candidate`, `invalidated`, `review_unavailable` | Confirmed; mark-time fail-closed for epoch-like values implemented in frontend `orders-helpers` | `admin.py:4728`, `tests/test_active_paper_position_review.py` (10), `apps/web/lib/orders-helpers.test.ts` (30) | None | ✅ matches |
| Already-open recommendation handling | Recs and queue decorated with `already_open`, position id, qty, average entry, review path | Confirmed | `tests/test_active_paper_position_review.py`, `apps/web/lib/recommendations.test.ts:275+` includes `already_open` | None | ✅ matches |
| Paper sizing + max paper order notional | Per-user `paper_max_order_notional`, default $1000; sizing remains risk-at-stop; `override_shares` clamped by recommendation size + cap; paper sandbox reset is current-user scoped | Confirmed | migration 0009, `tests/test_paper_order_sizing_and_reset.py` (5), `apps/web/app/(console)/settings/page.tsx`, `tests/test_active_paper_position_review.py` references the field | None | ✅ matches |
| OpenAI LLM provider | Optional, schema-validated, sanitized errors, recommendation guardrails | Confirmed | `src/macmarket_trader/llm/openai_provider.py` (esp. `RECOMMENDATION_GUARDRAIL_FIELDS`, `_redact(...)`, schema-validated responses), `tests/test_llm_integration.py` (28) | None within scope | ✅ matches |
| Opportunity Intelligence | LLM compares only backend-supplied stored recs, schema-validated, no symbol invention, deterministic fallback | Confirmed | `admin.py:1075 recommendation_opportunity_intelligence(...)`, opportunity-related schemas in `domain/schemas.py`, mock fallback in `llm/mock_extractor.py`, `tests/test_llm_integration.py` includes opportunity tests | None | ✅ matches |
| Market Risk Calendar (incl. index-aware) | Deterministic; macro/earnings/volatility + index signals can elevate to caution/restricted; LLM cannot override | Confirmed | `src/macmarket_trader/risk_calendar/service.py` (515), `index_risk.py` (268), `tests/test_risk_calendar.py` (19, 557 lines) | Real macro/earnings calendar feeds remain future provider work (acknowledged) | ✅ matches |
| Options Position Review | Review-only, mark-method precedence honest, missing-data flagged, expiration/moneyness/assignment-risk/exercise-risk surfaced, no auto exits/rolls/adjustments | Confirmed | `tests/test_options_paper_structure_review.py` (23 tests, 755 lines), routes `admin.py:1582` and `:1550` (settle-expiration) | Live exercise/assignment is explicitly outside scope | ✅ matches |
| Provider-backed options marks | Bid/ask mid → last trade → prior close (stale) → unavailable; zero/null/permission-blocked never treated as live | Confirmed | `data/providers/market_data.py` options snapshot path; structure review tests cover stale flag, missing flag, mark-method | None | ✅ matches |
| Listed-contract validation (strict) | Iron condor / verticals require all four legs from provider reference contracts; snap-distance gate; older synthetic structures kept honest | Confirmed | `src/macmarket_trader/options/paper_contracts.py`, `paper_open.py`; `tests/test_options_paper_open_lifecycle.py` | None | ✅ matches |
| SPX / index options scaffolding | Reference-contract uses raw `SPX`, snapshot uses `I:SPX`, payloads carry `underlying_asset_type=index`, `settlement_style=cash_settled`, `deliverable_type=cash_index`; no SPY substitution | Confirmed | `data/providers/market_data.py`, structure review tests for SPX, `tests/test_options_paper_structure_review.py` | Indices Starter entitlement messaging tested through provider readiness probes | ✅ matches |
| Indices Starter integration (`indices_data` + `index_options_data` probes, `IndexContextSummary`) | Provider Health probes for SPX/NDX/RUT/VIX snapshots and SPX option samples; index context fed to dashboard, Analysis Packet, Opportunity Intelligence, model validation | Confirmed | `data/providers/market_data.py:1495`, `admin.py:6235` and `:6421`, `analysis_packets.py` consumes `IndexContextSummary`, `tests/test_market_data_service.py` (57 tests cover indices) | None within scope | ✅ matches |
| Analysis Packet + email/report context | Reusable contract aggregates deterministic fields, provider provenance, paper-only flags, risk calendar, FRED, news, options leg context; redacts secrets | Confirmed | `src/macmarket_trader/analysis_packets.py` (1070 lines), `tests/test_analysis_packets.py` (9), `tests/test_strategy_reports.py` (24) | Real Resend delivery not exercised | ✅ matches |
| Compliance / evidence tooling | Release gate, secret scan, conflict scan, archive dry-run, evidence generator, model-validation script | Confirmed | `scripts/run_release_gate.py`, `scan_secrets.py`, `check_conflict_markers.py`, `create_clean_release_archive.py`, `generate_release_evidence.py`, `run_model_validation.py`, `tests/test_compliance_readiness.py` (6), `tests/test_operational_evidence.py` (12) | No committed signed evidence | ⚠️ partial |
| Deployed UI smoke | Cloudflare Access service-token or storage-state Playwright; skips cleanly; non-mutating by default | Confirmed structurally | `apps/web/tests/e2e/deployed-smoke.spec.ts`, `apps/web/playwright.deployed-smoke.config.ts`, `apps/web/tests/deployed-smoke-utils.ts` (285 lines) | ❓ unverifiable here without running | ❓ unverifiable |

---

## 7. Workflow Coherence Check

I traced the canonical guided path: **Analyze → Recommendation → Replay
→ Paper Order → Active Review → Close/Reset**.

- **URL context threading.** `apps/web/lib/guided-workflow.ts` is the
  canonical helper (`parseGuidedFlowState`, `buildGuidedQuery`).
  `apps/web/lib/guided-workflow.test.ts` (4 tests) exercises the parsing
  and emit, including the `iv_1sigma` expected-range method.
- **Lineage labels.** `display_id` is generated at recommendation
  creation in the format `SYMBOL-STRATEGY-YYYYMMDD-HHMM` and falls back
  to `Rec #shortid` for legacy rows. `apps/web/lib/lineage-format.test.ts`
  (16) covers formatting. The same-minute collision risk is documented
  in CLAUDE.md and is **not** mitigated in code (no suffix logic).
- **Queue promotion lineage.** `make_active` and `save_alternative` both
  store `ranking_provenance.action` and the candidate's `symbol`
  (verified in `tests/test_recommendations_api.py`). Save-alternative is
  fully wired despite docs saying otherwise.
- **Auto-advance CTAs.** `apps/web/tests/e2e/phase6-auto-advance.spec.ts`
  (1 test) and `phase5-guided-lineage.spec.ts` (9) exercise the
  guided-mode advance from promote → replay and replay-with-stageable →
  paper order.
- **Cancel staged + reopen closed.** 4 e2e tests in
  `phase6-cancel-reopen.spec.ts` cover the 5-min undo window and a
  positive cancel-pre-fill case. Backend math is in
  `tests/test_close_trade_lifecycle.py` (17 tests).
- **Active Position Review feeds back into recs.** Confirmed via
  `tests/test_active_paper_position_review.py` (already-open badge,
  warning when open paper position exists for same symbol).
- **Sandbox reset isolation.** `tests/test_paper_order_sizing_and_reset.py`
  (5) confirms the reset deletes only equity paper rows for the current
  user — **and** options-paper rows are explicitly preserved (per
  `tests/test_options_paper_structure_review.py` "equity sandbox reset
  leaves options records intact").
- **Symbol universe selector vs queue submit.** The new selector and
  preview API (`/user/symbol-universe/preview`) are read-only; queue
  submit (`/user/recommendations/queue`) and schedule save still take
  the existing manual `symbols` array. `tests/test_symbol_universe_preview.py`
  asserts no recommendation/schedule/watchlist mutation. **Coherent.**

No fabricated IDs surface in the read paths I sampled. The 5-minute
undo window is enforced server-side per the cancel-reopen test
expectations (UI-only enforcement would be fragile, but the e2e path
plus unit close-lifecycle tests cover both the time window and the
audit log).

---

## 8. Constitution Compliance Spot-Checks

### 8.1 LLM Boundary

- `src/macmarket_trader/llm/openai_provider.py` declares
  `RECOMMENDATION_GUARDRAIL_FIELDS = ["entry", "stop", "target", "sizing", "approval", "order_routing"]`
  and `OPPORTUNITY_GUARDRAIL_FIELDS = ["approved", "side", "entry", "invalidation", "targets", "shares", "sizing", "order_status", "paper_position_status"]`.
- `_schema_for_task(...)` returns strict JSON schemas for
  `summarize_event_text`, `extract_event_fields`,
  `explain_recommendation`, etc.
- Provider output is rejected with `LLMValidationError` if it fails
  Pydantic validation; the registry falls back to deterministic mock.
- `openai_provider.get_last_openai_provider_error()` and `_redact(...)`
  ensure that surfaced errors do not leak the API key (replaced with
  `[redacted]`) or `Authorization` headers.
- `tests/test_llm_integration.py` (28) covers provider mock + schema
  validation + opportunity intelligence.

**Verdict:** ✅ matches the constitution. The LLM cannot set entry,
stop, target, sizing, approval, or order routing.

### 8.2 Options / Crypto Boundary

- Options surfaces are gated to research / paper-only. Open uses a
  separate route (`/user/options/paper-structures/open`), separate
  tables (`paper_option_*`), and does not call any broker.
- Manual settlement endpoint exists but requires explicit `SETTLE`
  confirmation and does **not** route to a broker.
- No assignment/exercise automation. No naked-short support
  (`tests/test_options_payoff.py` confirms naked-short is rejected).
- Crypto: `crypto` market mode appears in schemas
  (`expected_range.method` includes `crypto_realized_vol_1sigma`) but
  no crypto persistence, provider, or runtime path exists.
  `tests/test_strategy_reports.py::test_analysis_setup_returns_functional_setup_for_crypto`
  exercises a crypto-mode setup; it is research-only.

**Verdict:** ✅ matches.

### 8.3 Auth / Role Boundary

- `src/macmarket_trader/api/deps/auth.py` makes the local DB
  authoritative for `app_role` and `approval_status`. Clerk only
  verifies tokens and (optionally) hydrates email/display name.
- `current_user(...)` upserts identity fields but never role/approval
  (`UserRepository.upsert_from_auth(...)`).
- `require_approved_user` and `require_admin` dependencies are used
  across routes (24 mentions of `app_role|approval_status` and 65
  uses of `require_approved_user|current_user|require_admin` in
  `admin.py`).
- `require_admin` additionally enforces `mfa_enabled` when
  `settings.require_mfa_for_admin` is true.
- `tests/test_auth_approval_api.py` (30) and
  `tests/test_user_identity_reconciliation.py` (6) cover invited→
  approved merge, suspended user blocks, role checks.

**Verdict:** ✅ matches.

### 8.4 Provider / Fallback Truth

- `data/providers/market_data.py` (2224 lines) implements explicit
  fallback paths. `WORKFLOW_DEMO_FALLBACK` is honored.
- Provider Health surfaces `config_state` vs `probe_state` separately
  (per 2026-05-02 update; verified in `admin.py` provider-health
  builder around `_indices_data_readiness` / `_index_options_data_readiness`).
- Options marks honor a deterministic precedence and never treat zero/
  null/permission-blocked data as a live mark.
- `tests/test_market_data_service.py` (57) and provider-readiness
  tests cover fallback labeling.

**Verdict:** ✅ matches.

### 8.5 Live Trading / Broker Routing

- `BROKER_PROVIDER=mock` is the production setting per `.env.example`
  and CLAUDE.md. `paper_broker.py` is a thin OMS wrapper that fills
  orders deterministically — **not** a broker.
- `data/providers/broker.py::AlpacaBrokerProvider.place_paper_order(...)`
  exists and would `POST /v2/orders` if `BROKER_PROVIDER=alpaca` were
  set. There is **no** affirmative refusal in `paper_broker.py` to
  block this if the registry chose Alpaca; the boundary is
  configuration-only.
- The CLAUDE.md-advertised `python -m macmarket_trader.cli poll-alpaca-fills`
  command **does not exist** — `cli.py` has no Alpaca integration at
  all.

**Verdict:** ⚠️ partial. The constitution holds in current
deployment, but it depends on `BROKER_PROVIDER` env value, not on a
hard refusal in code paths. CLAUDE.md claims a CLI subcommand that
does not exist.

---

## 9. Runtime Behavior Claims

| Claim | Evidence artifact / script / test | Verified? | Gap |
|---|---|---|---|
| Release gate runs scans + tests + audit + archive + evidence | `scripts/run_release_gate.py`, `scripts/run_release_gate.ps1`, `tests/test_operational_evidence.py` (12) | ✅ structurally; not run live in this audit | No committed evidence in-tree |
| Deployed release gate (`--deployed`) supports non-Git mirrors | Same script | ✅ structurally | Requires running on the deployed host |
| Provider Health probes (auth, email, market data, FRED, news, Alpaca readiness, options_data, index_options_data, indices_data, OpenAI) | `admin.py:6235+` (indices), `admin.py:6421+` (index options), provider-health builder | ✅ structurally | Live probe outcomes depend on real plan/keys |
| OpenAI probe exists and is read-only | `llm/openai_provider.py`, called from provider-health builder | ✅ structurally | Real probe not run here |
| Options data probe prefers discovered sample contract | `data/providers/market_data.py` and provider readiness builder | ✅ structurally | Live discovery not exercised here |
| Index options probe distinguishes ok/warn/degraded/failed_not_entitled/failed_underlying_index_data | `admin.py` index-options readiness | ✅ structurally | |
| FRED + news probes are live-safe single-call probes | Provider-health builder | ✅ structurally | |
| Browser smoke (deployed) writes screenshots + JSON/MD evidence under `.tmp/evidence/deployed-ui-smoke-*` and skips cleanly | `apps/web/tests/e2e/deployed-smoke.spec.ts` | ✅ structurally | ❓ requires CF Access token + Clerk-approved test-user storage state |
| SQLite backup + verify-restore scripts use copies, not source | `scripts/backup_sqlite.py`, `scripts/verify_sqlite_restore.py`, `tests/test_compliance_readiness.py` | ✅ structurally | No restore-drill evidence committed |
| Model validation script writes JSON+MD evidence locally only | `scripts/run_model_validation.py`, `tests/test_model_validation.py` | ✅ structurally | No committed evidence; SPY/QQQ baseline only when `daily_bars` present |
| Clean archive excludes secrets/state/test artifacts/AI worktrees | `scripts/create_clean_release_archive.py`, `scripts/check_release_artifact.py`, `tests/test_compliance_readiness.py` | ✅ structurally | Archive content not inspected here |
| `python -m macmarket_trader.cli poll-alpaca-fills` polls fills | CLAUDE.md only | ❌ **the command does not exist** in `cli.py` | Doc claim is wrong |
| Cloudflare Access invite-only enforces login | Operator runbook + deploy script | ❓ unverifiable | Requires deployed CF Access policy review |
| `MacMarket-Strategy-Reports` vs `MacMarket-StrategyScheduler` task duplication | CLAUDE.md acknowledges; runbook references one | ❓ unverifiable here | Requires Windows Task Scheduler inspection on deployed host |

---

## 10. Schema vs Code Drift

- **`apply_schema_updates()` shim** silently adds nullable columns. This
  is convenient but means migration history is **not** the canonical
  schema definition. Acquisition diligence will request a single source
  of truth.
- **Symbol universe parallel rails.** `user_symbol_universe` and
  `watchlist_symbols` exist (migration 0008, models 281–354). Production
  schedule + recommendation flows still consume `watchlists.symbols`
  JSON. The selector preview API reads either. This is documented as
  intentional, but operators looking at `app_users → watchlists` rows
  would find them authoritative; new rows would not appear in user UI
  until production wiring lands.
- **Options leg metadata.** Migration 0010 adds listed-contract
  selection metadata to leg tables. Older saved synthetic structures
  pre-2026-05-03 have no listed-contract metadata; review surfaces
  honor this with `provider_option_snapshot_not_found` + structure-level
  warning. Code path is correct; data drift is real and acknowledged.
- **Schema fields not in UI / UI fields not in schema.** I did not find
  obvious orphan fields in either direction during this pass. The
  options structure review payload exposes leg-level mark method, IV,
  OI, Greeks, source, as-of — all consumed by
  `apps/web/components/orders/paper-options-positions-section.tsx` and
  `apps/web/components/recommendations/options-research-preview.tsx`.
- **Index risk fields stored where?** `IndexRiskSignals` is a Pydantic
  schema returned from `extract_index_risk_signals(...)`. It does
  **not** persist into the DB; it is computed per request. This is
  fine and matches "deterministic derivation" but means the field is
  not directly queryable historically.

---

## 11. Test Coverage Reality

| Major claim | Tests that prove it | Gaps |
|---|---|---|
| Local DB authoritative for approval / role | `tests/test_auth_approval_api.py`, `tests/test_user_identity_reconciliation.py` | None |
| LLM cannot set trade levels / sizing / approval | `tests/test_llm_integration.py` | Real OpenAI call not exercised in CI |
| Options remain paper-only / research-only | All `tests/test_options_*` plus integrity audit | Real broker not exercised — by design |
| Risk calendar can elevate to caution/restricted on index signals | `tests/test_risk_calendar.py` (19, 557 lines) | Real macro/earnings calendar feeds not exercised |
| RTH 1H/4H buckets | `tests/test_market_data_service.py` (57) | Real provider entitlement variation |
| Active equity position review | `tests/test_active_paper_position_review.py` (10) | Real Polygon feed |
| Already-open badge surfaces in queue + persisted recs | Same | None |
| Options structure review w/ provider-backed marks | `tests/test_options_paper_structure_review.py` (23) | Real options snapshot |
| Settle-expiration endpoint | Same | Real broker (intentionally absent) |
| Cancel staged + 5-min reopen window | `tests/test_close_trade_lifecycle.py`, `tests/e2e/phase6-cancel-reopen.spec.ts` | Real Clerk session |
| Compliance docs/scripts present and behave | `tests/test_compliance_readiness.py`, `tests/test_operational_evidence.py` | No signed evidence |
| Deployed smoke skips cleanly + writes evidence when configured | `apps/web/tests/e2e/deployed-smoke.spec.ts` | Not exercised here; live deployed ❓ |
| `display_id` collision-free (within minute) | Acknowledged risk; **no** mitigation in code | Needs suffix logic |

Frontend coverage is solid for the critical visible surfaces:
`recommendations/options-research-preview.test.tsx` (19 tests),
`orders/paper-options-positions-section.test.tsx` (6),
`expected-range-visualization.test.tsx` (6),
`(console)/recommendations/page.test.ts` (13),
`(console)/schedules/page.test.ts` (14).

---

## 12. Security / Audit Readiness Reality

- **Auth.** Local DB authoritative; admin gate adds MFA enforcement
  when configured. ✅
- **IDOR.** Owner-scoped queries appear consistently in `admin.py`
  user-router routes. `tests/test_security_authorization.py` (6) and
  `tests/test_security_hardening.py` (8) cover the cross-user blocked
  cases I sampled. ✅
- **Rate limits.** `src/macmarket_trader/api/security.py` defines
  `HIGH_COST_ROUTE_LIMITS` for provider/LLM/recommendation/replay
  routes. In-memory; per-process. ✅ for current scale; a real reverse
  proxy / API gateway would supersede.
- **Origin / CSRF.** `validate_mutation_origin(...)` checks Origin/
  Referer on browser-originated mutating requests; allows server-to-
  server / local test calls without Origin. Default allowed-origins
  set is hard-coded to `macmarket.io`, `www.macmarket.io`, localhost
  variants. ✅
- **Headers.** `apps/web/next.config.ts` carries security headers.
  HSTS is correctly delegated to the Cloudflare/edge layer.
- **Secret scanning.** `scripts/scan_secrets.py` runs in the release
  gate; `tests/test_compliance_readiness.py` exercises redaction.
  Provider Health responses redact secrets. ✅
- **Deployment exclusions.** `scripts/create_clean_release_archive.py`
  excludes `.env`, `.tmp`, `.next`, AI worktrees, runtime DBs. ✅
- **Provider-health redaction.** Confirmed in test +
  `openai_provider._redact(...)` is comprehensive (replaces api_key
  with `[redacted]`, strips `Authorization`).
- **Admin invite tokens.** Masked in admin payloads (per Phase 11
  defensive pass 2 and `admin.py`).
- **FastAPI docs in prod.** Disabled when `environment` is
  `prod`/`production` and `api_docs_enabled=False` (verified at
  `api/main.py:29 _api_docs_kwargs`). ✅
- **Dependency audit.** `npm audit` moderate dev-server vulns are
  acknowledged in CLAUDE.md and roadmap-status.

**Remaining P2/P3.**

- `display_id` same-minute collision risk (P2; acknowledged, untested).
- `BROKER_PROVIDER=alpaca` would route real paper orders if env-flipped
  (P2 in current state, P0 if env flip ever happens accidentally; no
  in-code refusal).
- Compliance evidence is template-grade only (P2 for diligence; not a
  user-safety risk).
- npm vitest/vite/esbuild moderate vulns deferred (P3, dev-only).
- `/account` does not embed Clerk `<UserProfile>` for self-service MFA
  (P3, paid-feature dependency).

---

## 13. Model / Performance Validation Reality

- `scripts/run_model_validation.py` writes
  `.tmp/evidence/model-validation-YYYYMMDD-HHMMSS.{json,md}` from
  local data only. SPY/QQQ baseline reachable only when local
  `daily_bars` rows exist.
- No committed evidence file in-tree.
- No walk-forward split definitions, no benchmark capital assumptions
  in code.
- `docs/compliance/model-inventory.md` and
  `docs/compliance/model-validation-report-template.md` exist as
  scaffolding.
- `tests/test_model_validation.py` (6) verifies the validation script
  shape but not actual performance.

**Buyer-grade?** No. The current claim ("preliminary internal
validation evidence only") is honest. Acquirer-grade evidence would
require: dated point-in-time validation set, signed walk-forward split
definitions, benchmark capital assumptions, drift monitoring, and
counsel review. The roadmap acknowledges all of this.

---

## 14. Gaps & Overstatements — Ranked

| # | Title | Severity | Doc claim | Evidence | Blast radius | Recommended correction |
|---|---|---|---|---|---|---|
| 1 | CLI `poll-alpaca-fills` does not exist | P1 | CLAUDE.md "Test and build commands" + "Later execution phase" both mention `python -m macmarket_trader.cli poll-alpaca-fills` | `src/macmarket_trader/cli.py` defines only `health`, `generate-sample-recommendation`, `run-sample-replay`, `init-db`, `seed-demo-data`, `run-due-strategy-schedules` | Operator trust + acquisition diligence | Remove the command from CLAUDE.md until it actually ships |
| 2 | Test counts stale | P1 | CLAUDE.md "Test Counts (last verified 2026-04-30): pytest 271 / vitest 199 / Playwright 31" | Audit measured: pytest 469 / vitest ~243 / Playwright 32 | Operator trust + acquisition diligence | Update counts and the verification date |
| 3 | `save_alternative` listed as not implemented | P2 | CLAUDE.md / roadmap-status.md "save_alternative backend action variant not yet implemented (UI button exists, disabled)" | `tests/test_recommendations_api.py:383-409` proves backend behavior; `apps/web/app/(console)/recommendations/page.tsx:682` proves UI is wired | Operator trust | Remove from "Open Items" / "Still Open" |
| 4 | Phase numbering in CLAUDE.md vs roadmap | P2 | CLAUDE.md says Phases 0–9 complete; roadmap-status.md changelog already references "Phase 11" and "Phase 12" complete foundations | `docs/roadmap-status.md:348` Phase 12 update; `docs/roadmap-status.md:405` Phase 11 update | Operator trust | Add Phase 11/11B/12 explicitly to CLAUDE.md "Current Phase Status" |
| 5 | "Expiration settlement remains deferred" wording is partly stale | P2 | Multiple roadmap entries say expiration settlement is deferred | `admin.py:1550` exposes `POST /user/options/paper-structures/{position_id}/settle-expiration`; `tests/test_options_paper_structure_review.py` exercises it | Operator trust | Reword to: "manual settlement endpoint live; full settlement automation deferred" |
| 6 | Schema source-of-truth is split between Alembic and `apply_schema_updates()` | P2 | CLAUDE.md "apply_schema_updates handles all new columns automatically on startup. No manual Alembic migrations needed for nullable columns." | `src/macmarket_trader/storage/db.py` includes a generic ADD COLUMN shim | Acquisition diligence + audit | Document this clearly in `docs/architecture.md` and prefer Alembic adds for any future column |
| 7 | "Live trading is not active" is configuration-only | P2 | README + roadmap repeatedly say no live trading | `data/providers/broker.py::AlpacaBrokerProvider.place_paper_order(...)` exists; gate is `BROKER_PROVIDER` env value only | User safety / trading correctness | Add an in-code refusal in `paper_broker.py` if `BROKER_PROVIDER != "mock"` and a *separate* explicit kill switch (e.g. `LIVE_TRADING_ALLOWED=false`) |
| 8 | `display_id` same-minute collision unmitigated | P3 | CLAUDE.md "Open Items" acknowledges | No tests for collision; no suffix logic | User trust under bursty rec creation | Add suffix logic + test |
| 9 | `MacMarket-Strategy-Reports` task may duplicate `MacMarket-StrategyScheduler` | P3 | CLAUDE.md and roadmap "Still Open" both flag | Unverifiable in source | Operator confusion | Verify on deployed host, delete the duplicate |
| 10 | Compliance doc set is scaffolding-only | P2 | Phase 11 framing implies acquirer-readiness foundation | All `docs/compliance/*` are templates with no signed evidence in-tree | Acquisition diligence | Soften wording to "scaffolding for future audit" until owners + dated reviews exist |
| 11 | "atm_straddle_mid not yet emitted" is correctly documented but worth confirming | P3 | Doc admits it | `domain/schemas.py:679` allows it; no `method="atm_straddle_mid"` emission found in source | Operator trust | OK as-is; track in a small follow-up |
| 12 | Operator runbook predates several recent passes | P3 | `private-alpha-operator-runbook.md` last updated 2026-04-28 | Subsequent index/options/risk-calendar passes not reflected | Operator misuse | Refresh the runbook |

---

## 15. Recommended Doc Corrections

For each item, I propose the wording change. **Do not apply** without
review.

1. **CLAUDE.md → "Test and build commands"** — Remove:
   > `# Poll Alpaca paper fills (future execution phase — not yet active)`
   > `python -m macmarket_trader.cli poll-alpaca-fills`
   Replace with: `# Poll Alpaca paper fills — CLI not yet implemented; see roadmap-status.md "Later execution / implementation tracks"`

2. **CLAUDE.md → "Current Phase Status"** — Replace the test-count line:
   > `Tests (2026-04-30): pytest 271 collected; …`
   With (use the actual measured numbers as of the verification date):
   > `Tests (2026-05-05): pytest 469 collected; vitest ~243; Playwright 32; tsc clean from latest validation.`

3. **CLAUDE.md → "Open Items"** — Remove:
   > `- save_alternative backend action variant not yet implemented (UI button exists, disabled)`
   Reason: `tests/test_recommendations_api.py::test_user_ranked_queue_candidate_can_be_saved_as_alternative` proves the round-trip works.

4. **`docs/roadmap-status.md` → "Still Open"** — Same edit as above.

5. **`docs/roadmap-status.md` → repeated "expiration settlement remains deferred" passages** — Reword to:
   > "Manual paper-only settle-expiration endpoint is live (`POST /user/options/paper-structures/{position_id}/settle-expiration`, requires explicit `SETTLE` confirmation). Full settlement automation, broker exercise, and assignment automation remain deferred."

6. **CLAUDE.md → "Important implementation constraints"** — Add an
   explicit note about the schema source-of-truth split:
   > `apply_schema_updates() in src/macmarket_trader/storage/db.py is the de facto source of truth for nullable column adds. Alembic remains the source of truth for new tables and non-nullable columns. Future schema diligence should treat both together.`

7. **`docs/architecture.md`** — Refresh to include: market-mode contract,
   options paper lifecycle, risk calendar, index-aware risk, RTH
   normalization, active position review, deployed smoke, compliance/
   evidence layer.

8. **`docs/private-alpha-operator-runbook.md`** — Add: index-aware risk
   calendar interpretation, indices probe failure modes, options
   structure review reading guide.

---

## 16. Recommended Next Work

| Item | Scope | Files likely touched | Tests required | DoD | Priority |
|---|---|---|---|---|---|
| Doc-only correction pass | Apply §15 edits | `CLAUDE.md`, `docs/roadmap-status.md`, `docs/architecture.md`, `docs/private-alpha-operator-runbook.md` | None new; existing tests still green | Reviewers can read CLAUDE.md once and trust counts/CLI/save_alternative claims | P1 |
| In-code live-trading refusal | Hard refusal when broker provider would route real orders | `src/macmarket_trader/execution/paper_broker.py`, `src/macmarket_trader/data/providers/broker.py`, `src/macmarket_trader/data/providers/registry.py` | New `tests/test_live_trading_refusal.py` covering the explicit kill switch | Setting `BROKER_PROVIDER=alpaca` without `LIVE_TRADING_ALLOWED=true` raises and logs; default config is paper-only | P1 |
| `display_id` collision suffix | Add `-N` suffix for same-symbol/same-strategy/same-minute recs | `src/macmarket_trader/api/routes/admin.py` recommendation creation, `tests/test_display_id_and_user_settings.py` | Add collision test | Two recs in same minute have unique `display_id`; legacy fallback unchanged | P2 |
| Verify scheduled task duplication | Operator-only check | none in repo; deployed host inspection | none | One Windows task runs the scheduler; the duplicate is removed | P2 |
| Compliance evidence pass | Sign first access review, vendor review, restore drill, model validation report | `docs/compliance/*-evidence-*.md`, `.tmp/evidence/*` files committed | Existing compliance tests | First end-to-end signed evidence set committed (or deliberately stored off-host with reference) | P2 |
| `atm_straddle_mid` emission | Emit when call/put ATM mids are available | `src/macmarket_trader/api/routes/admin.py` (`_build_options_expected_range`), `src/macmarket_trader/analysis_packets.py` | Extend `tests/test_strategy_reports.py` with a synthetic ATM-mid scenario that exercises the live emit path | Live emit path produces `method="atm_straddle_mid"` when iv missing but ATM mids present | P3 |
| Refresh operator runbook | Add new sections noted in §15.8 | `docs/private-alpha-operator-runbook.md` | none | Runbook reflects 10W, index-aware calendar, indices probe failure modes, settle-expiration | P3 |

---

## 17. Open Questions / Required Manual Evidence

- **Deployed `https://macmarket.io` UI smoke.** Requires Cloudflare
  Access service token *or* a stored Playwright auth state for an
  approved test user. Cannot be run from this audit pass.
- **Real OpenAI / Polygon / FRED / Resend / Alpaca probes.** Not
  exercised here. Provider Health code paths are structurally correct;
  live behavior depends on plan + entitlement.
- **Cloudflare Access policy review.** Whether invite-only enforcement
  is configured correctly cannot be inferred from source.
- **Windows Task Scheduler state.** Whether the suspected
  `MacMarket-Strategy-Reports` task is in fact a duplicate of
  `MacMarket-StrategyScheduler` requires a `schtasks` query on the
  deployed host.
- **DB backup restore drill.** Scripts exist; no committed restore
  evidence. A monthly drill should produce a dated artifact.
- **Counsel review of regulatory boundary memo.** Internal-grade only;
  no signed external review in-tree.
- **Real email sample for scheduled report.** `EMAIL_PROVIDER=console`
  is the dev mode. Production deliverability for invite + scheduled
  reports through Resend should produce a captured sample for
  diligence.
- **Acquirer-grade model validation.** Requires dated point-in-time
  validation dataset, walk-forward split definitions, benchmark
  capital assumptions, and an independent benchmark reviewer.
- **Live securities/legal review.** Especially around any future
  shift toward broker-routing or LLM-influenced trading.

---

*End of audit.*
