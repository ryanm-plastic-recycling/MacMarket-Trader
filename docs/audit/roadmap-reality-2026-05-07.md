# MacMarket-Trader Roadmap Reality Audit — 2026-05-07

Independent re-audit of the source repository at
`C:\Users\ryanm\OneDrive\Documents\GitHub\MacMarket-Trader`.
Branch `audit/roadmap-reality-2026-05-05`, HEAD
`fed4b1f9619be70457f9ce008eaf7dc934ffe3b8` ("hmm"), working tree clean.
Deployed mirror at `C:\Dashboard\MacMarket-Trader` was **not** examined;
all evidence below is from the source tree.

This audit follows the previous report
`docs/audit/roadmap-reality-2026-05-05.md` (commit `557346c`). Two
post-audit commits (`d86f398` "updates" and `fed4b1f` "hmm") closed the
top P1/P2 doc-and-safety findings from that run; this report verifies
each fix and re-checks the state of every roadmap claim.

---

## 0. Executive Summary

**Overall verdict.** MacMarket-Trader's *engineering* is healthy. The
post-2026-05-05 audit-fix pass actually landed every safety-critical
fix it claimed: a hard `LIVE_TRADING_ALLOWED` refusal in code (with
defense-in-depth at the provider method), a deterministic `display_id`
collision suffix with frozen-clock test, and explicit doc corrections
in CLAUDE.md and roadmap-status.md. The roadmap's headline claim —
"Phases 0–9 complete for the current paper-first scope; Phase 10
planning/polish active; Phase 11/11B/12 are scaffolding only" — is
accurate.

**Biggest trust gaps (ranked).**

1. **Test counts have already drifted again.** Roadmap-status.md and
   CLAUDE.md state `pytest 469`. Actual `pytest --collect-only -q`
   reports **473 tests collected** (delta +4 since 2026-05-05).
   Vitest file count is **43**; Playwright remains 32.
2. **Schema source-of-truth split is documented but still real.** The
   ORM declares three columns the Alembic ledger never adds —
   `paper_positions.opened_qty`, `paper_positions.remaining_qty`,
   `paper_trades.realized_pnl`. They are auto-added at startup by
   `apply_schema_updates()` (`src/macmarket_trader/storage/db.py`), so
   the migration history is *not* a faithful schema description for
   any code path that boots through the FastAPI lifespan. CLAUDE.md
   acknowledges this; no migration backfills the gap.
3. **Compliance/Phase-11 evidence remains template-grade.** The
   compliance directory now correctly self-labels as "scaffolding /
   foundation" rather than "audit-ready," but no signed evidence,
   dated owner reviews, or restored-from-backup drill artifacts are
   in-tree.
4. **`/account` Clerk MFA still not embedded** (paid Clerk feature,
   acknowledged P3). Documented Open Item, no code change.
5. **`atm_straddle_mid` expected-range method is allowed by schema
   but never emitted.** Acknowledged Open Item; the gap is real and
   unchanged since the previous audit.

**Biggest technical gaps.**

- Index gap on lineage keys: `paper_positions.replay_run_id`,
  `paper_trades.replay_run_id`, and `paper_trades.position_id` are
  declared as columns but lack explicit indexes. Not a correctness
  bug; a query-performance/diligence flag.
- Live brokerage routing remains *paper-only* by configuration **and**
  by code refusal (`LIVE_TRADING_ALLOWED=false` is the in-process kill
  switch, with `LiveTradingDisabledError` raised at registry build and
  again at `AlpacaBrokerProvider.place_paper_order`). This was the
  P2/P1 finding from the prior audit and is now ✅ **closed**.
- Manual paper-only `settle-expiration` endpoint is live and tested,
  matching the corrected wording in roadmap-status.md.

**Documentation overstatements (still live).**

- "pytest 469" — *now* off by 4. Minor, but the doc is dated and the
  delta is real.
- "Compliance evidence is foundation/scaffolding only, not certified"
  — accurate framing in CLAUDE.md and `docs/compliance/README.md`,
  but `docs/compliance/acquisition-readiness.md` and the control
  matrix still read as substantive readiness in places. Treat as
  **partial overstatement**.

**Release / audit readiness.** Internal-grade. Release gate
(`scripts/run_release_gate.py`) runs scans + tests + archive +
evidence; tests/test_operational_evidence.py (12 tests) cover its
output shape. Nothing in-tree shows a third party has reviewed any of
it. Suitable for "we are operating responsibly in private alpha."
**Not** suitable for SOC 2 / ISO / regulator submission and not yet
suitable for acquirer diligence as published.

**Acquisition readiness.** Pre-diligence-grade. Engineering
discipline (deterministic engines, point-in-time, audit trails,
paper-only, LLM-fenced, in-code live-trading refusal) is verifiable.
Governance discipline (signed model validation, named risk owners,
restored-from-backup drill artifacts, counsel review) exists only as
templates and would not survive a serious diligence Q&A round.

---

## 1. Audit Scope and Method

- **Repo path:** `C:\Users\ryanm\OneDrive\Documents\GitHub\MacMarket-Trader`
- **Branch:** `audit/roadmap-reality-2026-05-05`
- **HEAD:** `fed4b1f9619be70457f9ce008eaf7dc934ffe3b8` ("hmm")
- **Working tree:** clean at audit start (`git status --short` empty).
- **Deployed mirror examined?** No — `C:\Dashboard\MacMarket-Trader`
  was intentionally not touched.
- **This report follows up on:** `docs/audit/roadmap-reality-2026-05-05.md`.

**Commands run during this audit:**

- `git status --short`, `git log --oneline -n 30`, `git rev-parse HEAD`,
  `git rev-parse --abbrev-ref HEAD`
- `git diff 557346c..fed4b1f --stat` (quantify the audit-fix pass)
- `git grep -nE '<<<<<<<|=======|>>>>>>>'` — no real conflict markers
  (matches were in `.gitignore`, `tests/test_operational_evidence.py`
  test-fixture, `scripts/check_conflict_markers.py` constants, and
  prior audit doc)
- `python -m pytest --collect-only -q | tail -5` → **473 tests
  collected**
- `python -m macmarket_trader.cli --help` →
  `health, generate-sample-recommendation, run-sample-replay,
  init-db, seed-demo-data, run-due-strategy-schedules` (no
  `poll-alpaca-fills`)
- Vitest file count via Glob: `apps/web/**/*.test.{ts,tsx}` excluding
  `node_modules` → **43 files**
- Playwright count via Glob: `apps/web/tests/e2e/*.spec.ts` → **7
  files**, **32 `test(` invocations** (already verified in prior
  audit; not re-counted)
- Targeted reads of: `config.py`, `data/providers/registry.py`,
  `data/providers/broker.py`, `storage/repositories.py`, `cli.py`,
  CLAUDE.md, `docs/roadmap-status.md`, all design docs in §0 read-list.
- Targeted greps for: `LIVE_TRADING_ALLOWED`, `LiveTradingDisabledError`,
  `_resolve_display_id_collision`, `atm_straddle_mid`,
  `RECOMMENDATION_GUARDRAIL_FIELDS`, `OPPORTUNITY_GUARDRAIL_FIELDS`,
  `apply_schema_updates`, `paper_max_order_notional`,
  `index_options_data|indices_data|IndexContextSummary`,
  `save_alternative`, `poll-alpaca-fills`, `place_paper_order`.

**Commands intentionally NOT run:**

- `pytest` full execution. Collect-only is sufficient for inventory
  and avoids touching `.tmp/` evidence artifacts.
- `cd apps/web && npm test --run`, `npx tsc --noEmit`, `npm run build`
  — same reason; would also touch `.next/`/cache state.
- `python scripts/run_release_gate.py --quick` — would write evidence
  files under `.tmp/` and could affect local state.
- Any Alpaca / Polygon / OpenAI / FRED / Resend live probes.
- Any deployed-mirror validation, deployed UI smoke
  (`apps/web/tests/e2e/deployed-smoke.spec.ts`), or
  `https://macmarket.io` browser session.

**Limitations.** Source-only. This audit cannot verify deployed
runtime behavior, deployed `.env` contents, Cloudflare Access policy,
Clerk-side approval flow, scheduled-task registration, real email
delivery, real provider responses, or real DB row contents.

---

## 2. Roadmap Inventory

All paths relative to repo root. "Last commit" is the most recent
short SHA touching the file.

| Path | Last commit (HEAD ancestry) | Declared scope | Status claims summary | Notes |
|---|---|---|---|---|
| `README.md` | pre-`d86f398` | Canonical architecture charter | Mandate, market-mode policy, options scope, success criteria | Treats current options as "scoped paper-first" |
| `docs/roadmap-status.md` | `d86f398` 2026-05-05 update added | Chronological roadmap diary | Phases 0–9 complete; Phase 10 active; Phase 11/11B/12 scaffolding only | 2461 lines. Now contains "2026-05-05 Update" closing top prior-audit findings. |
| `CLAUDE.md` | `d86f398` | Claude Code session context | Phases 0–9 complete; tests 469/243/32; Phase 10 next; Phase 11/11B/12 scaffolding only | Counts now off by 4 (actual 473). Save_alternative removed from Open Items. CLI `poll-alpaca-fills` reference removed. |
| `docs/architecture.md` | `d86f398` (extended +124 lines) | Pipeline / subsystems sketch | Now references LLM boundary, deterministic constraints, paper-only | Refresh covers the prior audit recommendation |
| `docs/options-architecture.md` | pre-audit | Options master plan | Defined-risk first; paper-only | Backed by `src/macmarket_trader/options/` |
| `docs/options-paper-lifecycle-design.md` | `6f487be` | Open/close persistence design | Maps to `paper_option_*` tables and routes | Code agrees |
| `docs/options-replay-design.md` | pre-audit | Read-only payoff preview design | Non-persisted | Backed by `options/replay_preview.py`, `options/payoff.py` |
| `docs/options-risk-ux-design.md` | pre-audit | Operator risk-summary panel | Recommendations options preview | Backed by frontend tests |
| `docs/options-test-plan.md` | pre-audit | Phase-8 test matrix | Maps to options tests | OK |
| `docs/active-paper-position-management-design.md` | `aad7e55` | Active equity review design | `GET /user/paper-positions/review` | Endpoint + tests confirm |
| `docs/market-risk-calendar-design.md` | `c1f532c` | Risk calendar + sit-out + index-aware | Index-aware as of 2026-05-04 | Backed by `risk_calendar/service.py`, `index_risk.py`, `tests/test_risk_calendar.py` |
| `docs/rth-intraday-normalization-design.md` | `1636559` | RTH 1H/4H rebucketing | Paper/research-only | Source: `data/providers/market_data.py` |
| `docs/symbol-watchlist-design.md` | pre-audit | Future symbol/watchlist design | 10W series checkpoint | Code includes `tests/test_symbol_universe_*` and migration 0008 |
| `docs/alpha-user-welcome.md` | `c1f532c` | Welcome guide rendered at `/welcome` | Updated 2026-05-04 | Read by `apps/web/app/(console)/welcome/page.tsx` |
| `docs/scheduled-reports.md` | pre-audit | Recurring strategy report design | Pre-10W; mostly accurate | |
| `docs/private-alpha-operator-runbook.md` | `d86f398` (+142 lines) | Deployment + day-2 runbook | Refresh adds index-risk / settle-expiration / options review reading guide | Closes prior audit recommendation |
| `docs/auth-and-approval.md` | pre-audit | Clerk + local DB policy | Constitutional; matches `api/deps/auth.py` | |
| `docs/provider-architecture.md` | pre-audit | Provider/fallback truth | Pre-Polygon-hardening | |
| `docs/market-data.md` | pre-audit | Market data shape | Pre-RTH normalization | |
| `docs/compliance/README.md` | `79ced77` | Compliance scaffolding index | Now self-labels as "foundation" / "templates" | |
| `docs/compliance/acquisition-readiness.md` | `c1f532c` | Acquirer-facing readiness checklist | Self-attested | No signed evidence |
| `docs/compliance/control-matrix.md` | `2301c6c` | SOC2-style control matrix | Self-attested | |
| `docs/compliance/regulatory-boundary-memo.md` | `2301c6c` | "Not yet a regulated activity" memo | Self-attested | Not counsel-reviewed |
| `docs/compliance/model-inventory.md`, `model-validation-report-template.md` | `ac71ff4` | Model registry + report template | Foundational | |
| `docs/compliance/risk-register.md`, `incident-response-plan.md`, `incident-tabletop-template.md`, `backup-restore-dr-plan.md`, `change-release-management.md`, `data-classification-retention.md`, `vendor-inventory.md`, `vendor-review-template.md`, `access-review-template.md`, `model-risk-management.md`, `evidence-manifest-template.md` | mostly `2301c6c`/`ac71ff4` | Compliance scaffolding | Templates only; no signed evidence | |
| `docs/compliance/deployed-smoke-testing.md` | `d7d8130` | Deployed UI smoke procedure | Backed by `apps/web/tests/e2e/deployed-smoke.spec.ts` | Skips cleanly when smoke auth not configured |
| `docs/audit/roadmap-reality-2026-05-05.md` | `557346c` | Prior audit | Findings closed by `d86f398`/`fed4b1f` (this audit verifies) | |

No `AGENTS.md` is present.

---

## 3. Migration / Schema Inventory

10 Alembic revisions; head is `20260503_0010_option_contract_selection_metadata`.
Runtime additionally calls `apply_schema_updates()` from
`src/macmarket_trader/storage/db.py` to add any nullable columns the
ORM declares but the migration set does not.

| Revision | Date | Purpose | Tables affected | Tests | Risk / gap |
|---|---|---|---|---|---|
| `20260331_0001_initial_schema` | 2026-03-31 | Snapshot via `Base.metadata.create_all` | All tables defined at the time | Implicit (all SQLite-bootstrap tests) | Snapshot-style |
| `20260413_0002_user_lineage_workflow_tables` | 2026-04-13 | `app_user_id` added to `recommendations`, `replay_runs`, `orders` | + 3 indexes | `tests/test_phase1_workflow_hardening.py`, `tests/test_auth_approval_api.py` | OK |
| `20260414_0003_guided_lineage_columns` | 2026-04-14 | `recommendations.replay_run_id` cross-link, etc. | recs / replay / orders | `tests/test_phase1_workflow_hardening.py` | OK |
| `20260414_0004_replay_source_lineage_columns` | 2026-04-14 | `source_recommendation_id` etc. | `replay_runs` | `tests/test_replay_engine.py` | OK |
| `20260415_0005_replay_stageable_and_paper_portfolio_scaffold` | 2026-04-15 | `has_stageable_candidate` + paper portfolio scaffold | `replay_runs` + `paper_positions` (11 cols) + `paper_trades` (8 cols) | `tests/test_replay_engine.py`, `tests/test_close_trade_lifecycle.py` | **Drift:** does **not** create `paper_positions.opened_qty`, `paper_positions.remaining_qty`, or `paper_trades.realized_pnl` even though ORM declares them — `apply_schema_updates()` patches at startup |
| `20260429_0006_commission_and_net_pnl` | 2026-04-29 | Commission + gross/net P&L on paper trades | `paper_trades`, `app_users` (commission cols) | `tests/test_close_trade_lifecycle.py`, `tests/test_phase7_fee_previews.py` | OK |
| `20260429_0007_options_paper_lifecycle_schema` | 2026-04-29 | Options paper lifecycle | `paper_option_orders`, `paper_option_order_legs`, `paper_option_positions`, `paper_option_position_legs`, `paper_option_trades`, `paper_option_trade_legs` | `tests/test_options_paper_schema.py`, `tests/test_options_paper_repository.py` | 228-line migration; well covered |
| `20260430_0008_symbol_universe_schema` | 2026-04-30 | `user_symbol_universe`, `watchlist_symbols` (additive, nullable) | + indexes + uniqueness constraints | `tests/test_symbol_universe_schema.py`, `tests/test_symbol_universe_repository.py`, `tests/test_symbol_universe_preview.py` | OK; production write paths still use legacy `watchlists.symbols` JSON |
| `20260502_0009_paper_max_order_notional` | 2026-05-02 | `paper_max_order_notional` per-user | `app_users` | `tests/test_paper_order_sizing_and_reset.py` | OK |
| `20260503_0010_option_contract_selection_metadata` | 2026-05-03 | Listed-contract metadata on leg tables | `paper_option_*_legs` | `tests/test_options_paper_repository.py`, `tests/test_options_paper_close_lifecycle.py`, `tests/test_options_paper_open_lifecycle.py` | OK |

**Drift / risk flags.**

- **ORM-without-migration columns (3):** `paper_positions.opened_qty`,
  `paper_positions.remaining_qty`, `paper_trades.realized_pnl` —
  declared in `domain/models.py:399-400, 418` but never added by an
  Alembic upgrade. `apply_schema_updates()` (`storage/db.py:33-78`)
  ALTER TABLE ADDs them at startup. **Acknowledged in CLAUDE.md as
  "nullable runtime drift only" but should be backfilled by a real
  migration before any acquirer review.**
- **Index gaps on lineage keys:** `paper_positions.replay_run_id`,
  `paper_trades.replay_run_id`, and `paper_trades.position_id` exist
  as columns in `domain/models.py:402, 421, 424` without explicit
  indexes. Not a correctness issue; flagged for diligence.
- **Symbol-universe rails are parallel.** Migration 0008 adds
  `user_symbol_universe` + `watchlist_symbols`; production write
  paths (`watchlists.symbols` JSON) are untouched. Selector preview
  reads either. This is **intentional and documented**, not drift.
- **Index-risk fields are computed-not-persisted.** `IndexRiskSignals`
  is a Pydantic schema returned from `extract_index_risk_signals(...)`
  per request. Fine for derivation; means historical signals are
  not directly queryable.

---

## 4. Test Inventory

Total backend tests: **473** (verified by `pytest --collect-only -q` —
last line: `473 tests collected in 0.70s`). Roadmap-status.md and
CLAUDE.md state **469**; the doc is **off by 4**.

Total frontend vitest test files: **43**; running test count
≈ **243** (already counted in the prior audit; not re-grepped here).

Total Playwright e2e: **7 spec files** under `apps/web/tests/e2e/`;
**32** `test(...)` calls.

Skipped / xfail / shallow: zero `@pytest.mark.skip`, `@pytest.mark.xfail`,
or `slow` markers in `tests/`. The deployed Playwright spec
`apps/web/tests/e2e/deployed-smoke.spec.ts` self-skips when smoke auth
is not configured, by design.

By domain (counts are `def test_` per file unless noted):

| Domain | Files | Tests | What they prove | What they don't prove |
|---|---|---|---|---|
| Auth/identity/admin | `test_auth_approval_api.py`, `test_user_identity_reconciliation.py` | 30 + 6 | Local DB authoritative, Clerk → local merge, suspended-user blocks | Real Clerk JWT under all keying scenarios |
| Security authorization | `test_security_authorization.py`, `test_security_hardening.py` | 6 + 8 | Admin route protection, owner-scoping, origin/CSRF, rate limits | Real CF Access policy, real CSP enforcement |
| Provider registry / Phase 4 | `test_phase4_providers.py`, `test_provider_registry.py` | 33 + 5 | Mock + Polygon adapter, Alpaca paper request shape, **`LIVE_TRADING_ALLOWED` refusal** | No real Polygon/Alpaca live calls |
| Market data + RTH | `test_market_data_service.py` | 57 | RTH bucket math, intraday normalization, indices snapshot, options snapshot path | No real entitlement responses |
| Charts / HACO | `test_charts_api.py`, `test_indicators_haco.py` | 11 + 2 | HACO/HACOLT math, payload shape | No frontend chart rendering |
| Recommendations / queue | `test_recommendations_api.py` | 13 | promote `make_active`/`save_alternative`, ranking provenance, generate flow | No live LLM, no full Polygon |
| Replay | `test_replay_engine.py` | 2 | Deterministic replay shape | Limited; replay hardening covered indirectly |
| Equity paper lifecycle | `test_close_trade_lifecycle.py`, `test_paper_equity_lifecycle_integrity.py`, `test_paper_order_sizing_and_reset.py`, `test_oms.py` | 17 + 1 + 5 + 2 | Open/close lifecycle, gross/net P&L, max-notional cap, sandbox reset | No real Alpaca |
| Active position review | `test_active_paper_position_review.py` | 10 | `GET /user/paper-positions/review` deterministic states (`hold_valid`, `stop_triggered`, etc.) | No live data |
| Options research preview | `test_options_payoff.py`, `test_options_replay_preview.py` | 13 + 6 | Payoff math, replay-preview contract, blocked naked-short | No live IV/skew |
| Options paper lifecycle | `test_options_paper_schema.py`, `test_options_paper_repository.py`, `test_options_paper_open_lifecycle.py`, `test_options_paper_close_lifecycle.py`, `test_options_paper_positions_list.py`, `test_options_lifecycle_integrity.py` | 2+4+7+9+1+1 | Open/close persistence, leg math, contract commissions, integrity audit | No real broker |
| Options structure review (mark-to-market + settlement) | `test_options_paper_structure_review.py` | 23 | Mark-method precedence, missing-data, expiration moneyness, **settle-expiration endpoint** | No live Greeks |
| Risk calendar (incl. index-aware) | `test_risk_calendar.py` | 19 | Macro/earnings/vol/index-risk signal extraction; sit-out gates | No live macro/earnings calendar |
| LLM / Opportunity Intelligence | `test_llm_integration.py` | 28 | Mock + schema validation + provenance + opportunity intelligence + **guardrails (`RECOMMENDATION_GUARDRAIL_FIELDS`)** | Real OpenAI behavior gated to env |
| Strategy reports + Analysis Packets | `test_strategy_reports.py`, `test_analysis_packets.py` | 24 + 9 | Rank + email payload, packet sanitization, expected-range method gating | Real Resend delivery |
| Symbol universe + watchlists | `test_symbol_universe_schema.py`, `test_symbol_universe_repository.py`, `test_symbol_universe_preview.py`, `test_watchlists.py` | 3+7+8+8 | New normalized model, resolver, preview API, legacy JSON compatibility | Production UI not wired to new tables |
| Compliance / operational evidence | `test_compliance_readiness.py`, `test_operational_evidence.py` | 6 + 12 | Doc presence, redaction, archive exclusions, deployed-mode toggles | Not external counsel review |
| Display ID + user settings | `test_display_id_and_user_settings.py` | 22 + **4 new** | `display_id` format, settings round-trip, **collision-suffix logic** (`-2`, `-3`, ...) | OK |
| Email templates | `test_email_templates.py` | 8 | Inlined logo, copy hygiene | Not actual deliverability |
| Misc engines / phase 1 / fee previews / health / cli | various | ≈ 39 | Engine math, fee preview, workflow lineage, health, CLI | OK |

**Behavioral vs. shallow tests.**

- `test_compliance_readiness.py` is mostly source-string assertions
  (file existence + keyword presence). It does *not* prove that
  controls are exercised at runtime. This is acknowledged in the
  prior audit and remains true.
- `test_operational_evidence.py` is behavior-driven (release gate
  output shape, secret redaction, backup-copy semantics).
- `test_model_validation.py` (6) verifies the validation script's
  shape and SQLite traversal — not actual model performance.
- The deployed Playwright spec is structural (skips when auth absent)
  rather than a dependable behavior gate by itself.

---

## 5. Phase-by-Phase Verification

| Phase | Claim | Actual state | Evidence | Verdict |
|---|---|---|---|---|
| Phase 0 — Foundation | FastAPI + Next.js + SQLite + Clerk + Windows deploy bridge | All present | `src/macmarket_trader/api/main.py`, `apps/web/app/`, `alembic/`, `scripts/deploy_windows.bat` | ✅ matches |
| Phase 1 — Core workflow | Analyze → Recommendation → Replay → Paper Order with deterministic engine | Present | `src/macmarket_trader/service.py`, `replay/engine.py`, e2e specs `phase1-closeout.spec.ts`, `phase5-guided-lineage.spec.ts`; `tests/test_phase1_workflow_hardening.py` (13) | ✅ matches |
| Phase 2 — Identity + auth | Invite-only, role system, identity reconciliation | Present | `api/deps/auth.py`, `data/providers/clerk_profile.py`, `email_templates.py`, `tests/test_auth_approval_api.py` (30), `tests/test_user_identity_reconciliation.py` (6), `tests/test_email_templates.py` (8) | ✅ matches |
| Phase 3 — Market data + providers | Polygon market data, fallback truth, demo fallback, index normalization, **RTH 1H/4H** | Present | `data/providers/market_data.py` (~2200 lines), `tests/test_market_data_service.py` (57), `tests/test_provider_registry.py` (5) | ✅ matches |
| Phase 4 — Recommendations + replay | Promote/make-active + save-as-alternative; replay validation gate; ranked queue lineage | Both `make_active` and `save_alternative` implemented and tested | `src/macmarket_trader/api/routes/admin.py` promote handlers; `tests/test_recommendations_api.py::test_user_ranked_queue_candidate_can_be_saved_as_alternative` (lines 383–409); `apps/web/app/(console)/recommendations/page.tsx:682` calls `action: "save_alternative"` | ✅ matches |
| Phase 5 — Operator console polish | Guided mode, sticky banner, auto-advance CTAs, brand pre-auth, welcome guide | Present | `components/active-trade-banner.tsx`, `components/workflow-banner.tsx`, `components/guided-step-rail.tsx`, `app/(console)/welcome/page.tsx`, `tests/e2e/phase5-guided-lineage.spec.ts` (9) | ✅ matches |
| Phase 6 — Close-trade lifecycle + Pass 4 | Open positions list, close ticket, closed-trades blotter, cancel staged + reopen closed (5-min undo), `display_id`, per-user risk dollars | Present; **`display_id` collision suffix now closed** (was P3 in prior audit) | `tests/e2e/phase6-close-lifecycle.spec.ts` (9), `phase6-cancel-reopen.spec.ts` (4), `tests/test_close_trade_lifecycle.py` (17), `tests/test_display_id_and_user_settings.py` (22 + 4 new collision tests). Code: `storage/repositories.py:105-151` `_resolve_display_id_collision()` | ✅ matches |
| Phase 7 — Commission/fee/provider readiness + Active Position Review | 7A–7D commission/fee/provider; 7E review; 7F sizing + sandbox reset | Present | `tests/test_phase7_fee_previews.py` (2), `tests/test_active_paper_position_review.py` (10), `tests/test_paper_order_sizing_and_reset.py` (5), migration 0006 + 0009 | ✅ matches |
| Phase 8 — Options research → paper parity | Read-only research preview, read-only payoff preview, paper-only open/manual-close, contract commissions, operator UI | Present | `src/macmarket_trader/options/{payoff,replay_preview,paper_open,paper_close,paper_contracts}.py`; routes in `admin.py` (open/close/list/review/settle-expiration); migration 0007 | ✅ matches |
| Phase 9 — Options operator parity, source/as-of, Expected Range visualization | 9A planning, 9B durable Orders, 9C provider/source/as-of, 9D Expected Range bar | Present | `apps/web/components/options/expected-range-visualization.tsx` + `.test.tsx`, `apps/web/components/orders/paper-options-positions-section.tsx` + tests; listing route in `admin.py` | ✅ matches |
| Phase 10 — Deferred-work planning + safe polish | 10A1, 10B1, 10C1–10C5, 10W1–10W8D | Mostly present | `apps/web/lib/glossary.ts`, `components/ui/metric-help.tsx`, route `/user/symbol-universe/preview` (`admin.py`), `tests/test_symbol_universe_*` | ⚠️ partial — broader `10A`/`10B`/`10C` reference page work, `10W9-10W10`, and `10G` closure remain open |
| Phase 11 — Trust, compliance, acquisition readiness foundation | Compliance docs scaffold, release gate, evidence scripts | Present, but template-grade | `docs/compliance/`, `scripts/run_release_gate.py`, `scripts/scan_secrets.py`, `scripts/check_release_artifact.py`, `scripts/generate_release_evidence.py`; `tests/test_compliance_readiness.py` (6) | ⚠️ partial — templates + dry-run scripts exist; **no signed evidence in-tree**. CLAUDE.md and roadmap-status.md now correctly self-label as scaffolding. |
| Phase 11B — Operational evidence automation | Release gate orchestrating scans, tests, npm-audit, archive dry-run | Present | `scripts/run_release_gate.py`, `scripts/run_release_gate.ps1`, `tests/test_operational_evidence.py` (12) | ✅ matches |
| Phase 12 — Model validation foundation | Model inventory, validation report template, local validation script | Present | `docs/compliance/model-inventory.md`, `docs/compliance/model-validation-report-template.md`, `scripts/run_model_validation.py`, `tests/test_model_validation.py` (6) | ⚠️ partial — script real, no committed evidence; SPY/QQQ baseline reachable only when local `daily_bars` exists |
| Index-aware Market Risk Calendar | VIX/SPX/NDX/RUT/disper­sion/risk-appetite/stale flags can elevate calendar to caution/restricted | Present | `src/macmarket_trader/index_risk.py`, `risk_calendar/service.py`, `tests/test_risk_calendar.py` (19, 557 lines) | ✅ matches |
| Indices Starter integration (`indices_data` + `index_options_data` probes, `IndexContextSummary`) | Provider Health adds both probes; Index Context surfaces in dashboard / Analysis Packet / Opportunity Intelligence | Present | `data/providers/market_data.py` (`indices_data_health`), `admin.py` provider-health builders, `analysis_packets.py` consumes `IndexContextSummary` | ✅ matches |
| **`LIVE_TRADING_ALLOWED` hard refusal** | Default false; non-mock broker raises `LiveTradingDisabledError` at registry; `place_paper_order` raises before any HTTP request | Implemented and tested | `config.py:119-123` (`live_trading_allowed: bool = False`); `data/providers/registry.py:56-77` (factory raises); `data/providers/broker.py:39-50` (defense-in-depth method-level raise); `tests/test_phase4_providers.py:404-461` (4 new tests; mock path still works; no HTTP attempted) | ✅ matches — **closes prior P1/P2 finding** |
| **`display_id` collision suffix** | Same user/symbol/strategy/minute → deterministic `-2`, `-3`, ... suffix; canonical `recommendation_id` unaffected | Implemented and tested | `storage/repositories.py:105-151` `_resolve_display_id_collision()`; `tests/test_display_id_and_user_settings.py:121-227` `test_display_id_same_minute_gets_unique_suffix` | ✅ matches — **closes prior P3 finding** |
| Active paper position management endpoint | `GET /user/paper-positions/review` returns one review per open paper equity position | Implemented | `admin.py` user-router route, `apps/web/app/api/user/paper-positions/review/route.ts`, `tests/test_active_paper_position_review.py` (10) | ✅ matches |
| Already-open recommendation awareness | Queue/persisted recs decorate with `already_open`, position id/qty/avg entry, review path | Implemented | `tests/test_active_paper_position_review.py`, `apps/web/lib/recommendations.test.ts` covers `already_open` | ✅ matches |
| Symbol universe additive schema (`10W4`/`10W5`) | New tables exist but production write paths still use legacy `watchlists.symbols` JSON | Implemented exactly as documented | Migration 0008, models 281+/315+ (`UserSymbolUniverseModel`/`WatchlistSymbolModel`), `tests/test_symbol_universe_schema.py`, `tests/test_symbol_universe_repository.py` | ✅ matches |
| Universe selector preview API (`10W8A`–`10W8D`) | Preview-only, user-scoped, no provider calls, no schedule/watchlist mutation, no recommendation submit | Implemented | `admin.py` `/symbol-universe/preview`; `tests/test_symbol_universe_preview.py` (8) including `test_preview_does_not_create_recommendations_or_mutate_watchlists_or_schedules` | ✅ matches |
| Strict listed-contract options structure validation | Iron condor / verticals require provider-resolved listed contracts; older synthetic structures kept honest | Implemented | `src/macmarket_trader/options/paper_contracts.py`, `paper_open.py`; `tests/test_options_paper_open_lifecycle.py` includes provider-not-found and incomplete-chain coverage | ✅ matches |
| Provider-backed options marks for review | Mark precedence: bid/ask mid → last trade → prior close (stale fallback) → unavailable; missing/stale data does not fabricate P&L | Implemented | `data/providers/market_data.py` snapshot path; `tests/test_options_paper_structure_review.py` (23) | ✅ matches |
| Manual paper-only `settle-expiration` endpoint | Requires explicit `SETTLE` confirmation; user-scoped; intrinsic-value math; no auto exercise/assignment | Implemented | Route in `admin.py`; `tests/test_options_paper_structure_review.py` covers settlement | ✅ matches (prior audit's "expiration settlement deferred" wording is now corrected in roadmap-status.md and CLAUDE.md) |
| SPX / index options scaffolding | Reference-contract uses raw `SPX`, snapshot uses `I:SPX`, payloads carry `underlying_asset_type=index`, `settlement_style=cash_settled`, `deliverable_type=cash_index`; no SPY substitution | Implemented | `data/providers/market_data.py`, structure review tests for SPX | ✅ matches |
| Defensive security pass 2 | Origin validation on browser mutations, in-memory rate limits, payload caps, security headers, FastAPI docs disabled in prod, masked admin invite tokens | Implemented | `src/macmarket_trader/api/security.py` (~219 lines), `api/main.py:29-43` `_api_docs_kwargs(...)`, `apps/web/next.config.ts` security headers, `tests/test_security_hardening.py` (8) | ✅ matches |
| OpenAI provider safety | Optional, schema-validated, deterministic fallback, sanitized errors, never sets entry/stop/target/sizing/approval/routing | Implemented | `src/macmarket_trader/llm/openai_provider.py`, `RECOMMENDATION_GUARDRAIL_FIELDS = ["entry","stop","target","sizing","approval","order_routing"]`, `_redact(...)`, `tests/test_llm_integration.py` (28) | ✅ matches |
| Deployed UI smoke | Cloudflare Access service-token or storage-state path; evidence under `.tmp/evidence/deployed-ui-smoke-*`; skips cleanly | Implemented; not run in this audit | `apps/web/tests/e2e/deployed-smoke.spec.ts`, `playwright.deployed-smoke.config.ts`, `apps/web/tests/deployed-smoke-utils.ts`, `docs/compliance/deployed-smoke-testing.md` | ❓ unverifiable here (would require CF Access service token + a stored test-user auth state) |

---

## 6. High-Scrutiny Review: Work Since Phase 8

| Area | Claimed behavior | Verified behavior | Evidence | Remaining gap | Verdict |
|---|---|---|---|---|---|
| Options architecture & module layout | Dedicated `options/` package; payoff math pure; replay preview separate from equity replay; paper persistence separate from equity | Confirmed: 5 modules + 6 dedicated `paper_option_*` tables | `src/macmarket_trader/options/`, `src/macmarket_trader/domain/models.py:429+` | None within current paper-only scope | ✅ matches |
| Options replay / payoff preview | Read-only, non-persisted; rejects naked shorts; iron condor + vertical debit + long single | Confirmed | `tests/test_options_payoff.py` (13), `tests/test_options_replay_preview.py` (6) | No persistence into `replay_runs` (intentionally) | ✅ matches |
| Options paper lifecycle (open / manual close / **settle-expiration**) | Dedicated tables, structured legs, contract-commission accounting, gross/net P&L, idempotent close, **manual settlement w/ explicit `SETTLE` confirmation** | Confirmed | `tests/test_options_paper_open_lifecycle.py` (7), `tests/test_options_paper_close_lifecycle.py` (9), `tests/test_options_lifecycle_integrity.py` (1), `tests/test_options_paper_structure_review.py` (23) covers settle-expiration | Partial fills, naked shorts, assignment/exercise = explicitly deferred | ✅ matches |
| Options commissions | `commission_per_contract` per leg per contract; net P&L stored on trade legs | Confirmed | Migration 0006 + 0007, `tests/test_options_paper_close_lifecycle.py`, `tests/test_phase7_fee_previews.py` | None | ✅ matches |
| Expected Range (research-only) | `iv_1sigma`, `atm_straddle_mid`, `equity_realized_vol_1sigma`, `equity_atr_projection`, `crypto_realized_vol_1sigma` allowed by schema; `computed`/`blocked`/`omitted` status | `iv_1sigma` is emitted; `atm_straddle_mid` is allowed by schema but **not yet emitted** by preview/packet code | `domain/schemas.py:679`, `tests/test_strategy_reports.py:807-818` (synthetic ingest only) | "atm_straddle_mid not yet emitted" remains an Open Item; correctly documented | ⚠️ partial (matches docs) |
| Intraday timeframe correctness + RTH normalization | 1H/4H provider-backed flows fetch 30m, filter 9:30–16:00 ET, re-aggregate; intraday timestamps preserved | Confirmed | `data/providers/market_data.py` RTH bucket helpers, `risk_calendar/service.py` references session policy | None | ✅ matches |
| Active equity position review (`/user/paper-positions/review`) | One review per open paper equity position; `hold_valid`, `stop_triggered`, `target_reached_*`, `time_stop_*`, `scale_in_candidate`, `invalidated`, `review_unavailable` | Confirmed | `admin.py` user-router route, `tests/test_active_paper_position_review.py` (10), `apps/web/lib/orders-helpers.test.ts` (mark-time fail-closed) | None | ✅ matches |
| Already-open recommendation handling | Recs and queue decorated with `already_open`, position id, qty, average entry, review path | Confirmed | `tests/test_active_paper_position_review.py`, `apps/web/lib/recommendations.test.ts` | None | ✅ matches |
| Paper sizing + max paper order notional | Per-user `paper_max_order_notional`, default $1000; sizing remains risk-at-stop; `override_shares` clamped by recommendation size + cap; paper sandbox reset is current-user scoped (equity-only; preserves options) | Confirmed | Migration 0009, `tests/test_paper_order_sizing_and_reset.py` (5), Settings page, structure-review test asserts options preserved across equity reset | None | ✅ matches |
| OpenAI LLM provider | Optional, schema-validated, sanitized errors, recommendation guardrails | Confirmed | `src/macmarket_trader/llm/openai_provider.py` (`RECOMMENDATION_GUARDRAIL_FIELDS`, `_redact(...)`, schema validation, system prompt enforcement), `tests/test_llm_integration.py` (28) | None within scope | ✅ matches |
| Opportunity Intelligence | LLM compares only backend-supplied stored recs; schema-validated; no symbol invention; deterministic fallback | Confirmed | `admin.py` `recommendation_opportunity_intelligence(...)`, opportunity schemas in `domain/schemas.py`, mock fallback in `llm/mock_extractor.py`, `tests/test_llm_integration.py` includes opportunity tests | None | ✅ matches |
| Market Risk Calendar (incl. **index-aware**) | Deterministic; macro/earnings/volatility + index signals can elevate to caution/restricted; LLM cannot override | Confirmed | `src/macmarket_trader/risk_calendar/service.py`, `index_risk.py`, `tests/test_risk_calendar.py` (19) | Real macro/earnings calendar feeds remain future provider work (acknowledged) | ✅ matches |
| Options Position Review | Review-only; mark-method precedence honest; missing-data flagged; expiration/moneyness/assignment-risk/exercise-risk surfaced; no auto exits/rolls/adjustments | Confirmed | `tests/test_options_paper_structure_review.py` (23 tests, ~755 lines), routes in `admin.py` (review + settle-expiration) | Live exercise/assignment explicitly outside scope | ✅ matches |
| Provider-backed options marks | Bid/ask mid → last trade → prior close (stale) → unavailable; zero/null/permission-blocked never treated as live | Confirmed | `data/providers/market_data.py` options snapshot path; structure review tests cover stale flag, missing flag, mark-method | None | ✅ matches |
| Listed-contract validation (strict) | Iron condor / verticals require all four legs from provider reference contracts; snap-distance gate; older synthetic structures kept honest | Confirmed | `src/macmarket_trader/options/paper_contracts.py`, `paper_open.py`; `tests/test_options_paper_open_lifecycle.py` | None | ✅ matches |
| SPX / index options scaffolding | Reference-contract uses raw `SPX`, snapshot uses `I:SPX`, payloads carry index settlement metadata; no SPY substitution | Confirmed | `data/providers/market_data.py`, structure review SPX tests | Indices Starter entitlement messaging tested via provider readiness probe | ✅ matches |
| Indices Starter integration | Provider Health probes for SPX/NDX/RUT/VIX snapshots and SPX option samples; index context fed to dashboard, Analysis Packet, Opportunity Intelligence, model validation | Confirmed | `data/providers/market_data.py` `indices_data_health(...)`, `admin.py` `_indices_data_readiness(...)` and `_index_options_data_readiness(...)`, `analysis_packets.py` consumes `IndexContextSummary`, `tests/test_market_data_service.py` (57) | None within scope | ✅ matches |
| Analysis Packet + email/report context | Reusable contract aggregates deterministic fields, provider provenance, paper-only flags, risk calendar, FRED, news, options leg context; redacts secrets | Confirmed | `src/macmarket_trader/analysis_packets.py` (~1070 lines), `tests/test_analysis_packets.py` (9), `tests/test_strategy_reports.py` (24) | Real Resend delivery not exercised | ✅ matches |
| Compliance / evidence tooling | Release gate, secret scan, conflict scan, archive dry-run, evidence generator, model-validation script | Confirmed | `scripts/run_release_gate.py`, `scan_secrets.py`, `check_conflict_markers.py`, `create_clean_release_archive.py`, `generate_release_evidence.py`, `run_model_validation.py`, `tests/test_compliance_readiness.py` (6), `tests/test_operational_evidence.py` (12) | No committed signed evidence | ⚠️ partial |
| Deployed UI smoke | CF Access service-token or storage-state Playwright; skips cleanly; non-mutating by default | Confirmed structurally | `apps/web/tests/e2e/deployed-smoke.spec.ts`, `apps/web/playwright.deployed-smoke.config.ts`, `apps/web/tests/deployed-smoke-utils.ts` | Live behavior unverifiable here (would require CF Access service token + stored test-user auth state) | ❓ unverifiable |

---

## 7. Workflow Coherence Check

Canonical guided path: **Analyze → Recommendation → Replay → Paper Order
→ Active Review → Close/Reset.**

- **URL context threading.** `apps/web/lib/guided-workflow.ts` is the
  canonical helper (`parseGuidedFlowState`, `buildGuidedQuery`). The
  test file exercises parsing/emit including the `iv_1sigma`
  expected-range method.
- **Lineage labels.** `display_id` is generated at recommendation
  creation in the format `SYMBOL-STRATEGY-YYYYMMDD-HHMM` and falls
  back to `Rec #shortid` for legacy rows. Same-minute collisions are
  now resolved by deterministic `-2`, `-3`, ... suffixes
  (`storage/repositories.py:105-151`); the canonical
  `recommendation_id` (`rec_<hex>`) is the unique key everywhere.
- **Queue promotion lineage.** `make_active` and `save_alternative`
  both store `ranking_provenance.action` and the candidate's
  `symbol`. `tests/test_recommendations_api.py:383-409` proves the
  full save-alternative round-trip — **the prior audit's stale
  "save_alternative not yet implemented" doc gap is now closed in
  CLAUDE.md and roadmap-status.md.**
- **Auto-advance CTAs.** `phase6-auto-advance.spec.ts` and
  `phase5-guided-lineage.spec.ts` exercise promote → replay and
  replay-with-stageable → paper order.
- **Cancel staged + reopen closed.** `phase6-cancel-reopen.spec.ts`
  (4 tests) covers the 5-min undo window. Backend math in
  `tests/test_close_trade_lifecycle.py` (17).
- **Active Position Review feeds back into recs.** Confirmed via
  `tests/test_active_paper_position_review.py` (already-open badge,
  warning when open paper position exists for same symbol).
- **Sandbox reset isolation.** `tests/test_paper_order_sizing_and_reset.py`
  (5) confirms reset deletes only equity paper rows for the current
  user. Options-paper rows are preserved (per
  `tests/test_options_paper_structure_review.py`).
- **Symbol universe selector vs queue submit.** The new selector and
  preview API (`/user/symbol-universe/preview`) are read-only; queue
  submit (`/user/recommendations/queue`) and schedule save still take
  the existing manual `symbols` array.
  `tests/test_symbol_universe_preview.py` asserts no
  recommendation/schedule/watchlist mutation.

No fabricated IDs surface in the read paths I sampled. The 5-minute
undo window is enforced server-side per cancel/reopen test
expectations. The previously-flagged `display_id` same-minute
collision risk is now mitigated in code.

---

## 8. Constitution Compliance Spot-Checks

### 8.1 LLM Boundary

- `src/macmarket_trader/llm/openai_provider.py` declares
  `RECOMMENDATION_GUARDRAIL_FIELDS = ["entry", "stop", "target",
  "sizing", "approval", "order_routing"]` and
  `OPPORTUNITY_GUARDRAIL_FIELDS = ["approved", "side", "entry",
  "invalidation", "targets", "shares", "sizing", "order_status",
  "paper_position_status"]`.
- `_with_static_guardrails(...)` overrides any candidate field with
  `deterministic_engine_owns` and `explanation_only=True`, then
  hands the merged payload through Pydantic validation
  (`LLMRecommendationExplanation.model_validate(...)`,
  `OpportunityComparisonMemo.model_validate(...)`).
- System-prompt enforcement explicitly states "explain and extract
  only. Do not choose trades, entries, stops, targets, sizing,
  approval status, or routing."
- `_redact(...)` strips `api_key`, `Authorization`, and similar
  fields before any error string can be returned to a user.
- `tests/test_llm_integration.py` (28) covers schema validation
  rejection of malformed payloads (e.g. invented symbols, free-form
  approval text).

**Verdict.** ✅ matches.

### 8.2 Options / Crypto Boundary

- Options surfaces are gated to research / paper-only. Paper open
  uses dedicated `paper_option_*` tables and never invokes a broker.
- Manual settlement endpoint exists but requires explicit `SETTLE`
  confirmation and does **not** route to a broker
  (`paper_close.py:94-95`, route in `admin.py`).
- No assignment/exercise automation. No naked-short support
  (`tests/test_options_payoff.py` confirms naked-short is rejected).
- Crypto: `crypto` market mode appears in schemas (`expected_range.method`
  includes `crypto_realized_vol_1sigma`, `domain/schemas.py:1155+`)
  but no crypto persistence, provider, or runtime path exists. A
  research-only crypto setup test exists in `test_strategy_reports.py`.

**Verdict.** ✅ matches.

### 8.3 Auth / Role Boundary

- `src/macmarket_trader/api/deps/auth.py` makes the local DB
  authoritative for `app_role` and `approval_status`. Clerk only
  verifies tokens and (optionally) hydrates email/display name.
- `current_user(...)` upserts identity fields but never role/
  approval. `UserRepository.upsert_from_auth(...)` preserves the
  highest-rank approval and the highest-rank role across duplicate
  candidates (`storage/repositories.py:1877+`).
- `require_approved_user` and `require_admin` dependencies are used
  consistently across admin / user routes; `require_admin` also
  enforces `mfa_enabled` when `settings.require_mfa_for_admin`.
- `tests/test_auth_approval_api.py` (30) and
  `tests/test_user_identity_reconciliation.py` (6) cover invited→
  approved merge, suspended-user blocks, role checks.

**Verdict.** ✅ matches.

### 8.4 Provider / Fallback Truth

- `data/providers/market_data.py` (~2200 lines) implements explicit
  fallback paths. `WORKFLOW_DEMO_FALLBACK` is honored.
- Provider Health surfaces `config_state` vs `probe_state`
  separately (per 2026-05-02 update; see `_config_state(...)` /
  `_readiness_status(...)` in `admin.py`).
- Options marks honor a deterministic precedence and never treat
  zero / null / permission-blocked data as a live mark.
- `tests/test_market_data_service.py` (57) and provider-readiness
  tests cover fallback labeling.

**Verdict.** ✅ matches.

### 8.5 Live Trading / Broker Routing

- `BROKER_PROVIDER=mock` is the production setting. `paper_broker.py`
  is a thin OMS wrapper that fills orders deterministically — **not**
  a broker.
- **NEW (closes prior P1/P2 finding).** `LIVE_TRADING_ALLOWED=false`
  is now the in-process kill switch:
  - `config.py:119-123` sets `live_trading_allowed: bool = False`.
  - `data/providers/registry.py:56-77` raises
    `LiveTradingDisabledError` when `BROKER_PROVIDER != "mock"` and
    the flag is false — *before* any provider object is constructed.
  - `data/providers/broker.py:39-50` adds a defense-in-depth check
    inside `AlpacaBrokerProvider.place_paper_order(...)` that raises
    *before* `_post_json(...)` (i.e. before any HTTP request).
  - `tests/test_phase4_providers.py:404-461` adds 4 tests:
    factory refusal, unknown-provider refusal, defense-in-depth
    method refusal asserting `posted == []`, mock-still-routes
    regression test.
- The CLAUDE.md-advertised `python -m macmarket_trader.cli
  poll-alpaca-fills` command **still does not exist** — `cli.py`
  exposes `health, generate-sample-recommendation, run-sample-replay,
  init-db, seed-demo-data, run-due-strategy-schedules` only. CLAUDE.md
  has been updated to say "A future execution phase will add a
  fill-polling CLI for Alpaca paper. None exists today" — this is
  now an accurate framing.

**Verdict.** ✅ matches. Closes the prior P1/P2 finding.

---

## 9. Runtime Behavior Claims

| Claim | Evidence artifact / script / test | Verified? | Gap |
|---|---|---|---|
| Release gate runs scans + tests + audit + archive + evidence | `scripts/run_release_gate.py`, `scripts/run_release_gate.ps1`, `tests/test_operational_evidence.py` (12) | ✅ structurally; not run live in this audit | No committed evidence in-tree |
| Deployed release gate (`--deployed`) supports non-Git mirrors | Same script | ✅ structurally | Requires running on the deployed host |
| Provider Health probes (auth, email, market data, FRED, news, Alpaca readiness, options_data, index_options_data, indices_data, OpenAI) | `admin.py` provider-health builders for each provider | ✅ structurally | Live probe outcomes depend on real plan/keys |
| OpenAI probe exists and is read-only | `llm/openai_provider.py`, called from provider-health builder | ✅ structurally | Real probe not run here |
| Options data probe prefers discovered sample contract | `data/providers/market_data.py` and provider readiness builder | ✅ structurally | Live discovery not exercised here |
| Index options probe distinguishes ok/warn/degraded/failed_not_entitled/failed_underlying_index_data | `admin.py` index-options readiness | ✅ structurally | |
| FRED + news probes are live-safe single-call probes | Provider-health builder | ✅ structurally | |
| Browser smoke (deployed) writes screenshots + JSON/MD evidence under `.tmp/evidence/deployed-ui-smoke-*` and skips cleanly | `apps/web/tests/e2e/deployed-smoke.spec.ts` | ✅ structurally | ❓ requires CF Access token + Clerk-approved test-user storage state |
| SQLite backup + verify-restore scripts use copies, not source | `scripts/backup_sqlite.py`, `scripts/verify_sqlite_restore.py`, `tests/test_compliance_readiness.py` | ✅ structurally | No restore-drill evidence committed |
| Model validation script writes JSON+MD evidence locally only | `scripts/run_model_validation.py`, `tests/test_model_validation.py` | ✅ structurally | No committed evidence; SPY/QQQ baseline only when `daily_bars` present |
| Clean archive excludes secrets/state/test artifacts/AI worktrees | `scripts/create_clean_release_archive.py`, `scripts/check_release_artifact.py`, `tests/test_compliance_readiness.py` | ✅ structurally | Archive content not inspected here |
| `python -m macmarket_trader.cli poll-alpaca-fills` polls fills | CLAUDE.md (now corrected) | ✅ closed — CLAUDE.md correctly states the command does not exist | None |
| Cloudflare Access invite-only enforces login | Operator runbook + deploy script | ❓ unverifiable | Requires deployed CF Access policy review |
| `MacMarket-Strategy-Reports` vs `MacMarket-StrategyScheduler` task duplication | CLAUDE.md acknowledges as Open Item | ❓ unverifiable here | Requires `schtasks` query on deployed host |

---

## 10. Schema vs Code Drift

- **`apply_schema_updates()` shim** silently adds nullable columns at
  startup. CLAUDE.md now correctly identifies this as "nullable
  runtime drift only" rather than a substitute for migrations. Three
  ORM columns are exclusively added by the shim:
  `paper_positions.opened_qty`, `paper_positions.remaining_qty`,
  `paper_trades.realized_pnl`. **A formal migration should backfill
  these before any acquirer review** — they are real columns the
  ORM relies on and the migration ledger does not describe.
- **Symbol universe parallel rails.** `user_symbol_universe` and
  `watchlist_symbols` exist (migration 0008, models 281+/315+).
  Production schedule + recommendation flows still consume
  `watchlists.symbols` JSON. The selector preview API reads either.
  Documented as intentional.
- **Options leg metadata.** Migration 0010 adds listed-contract
  selection metadata to leg tables. Older saved synthetic structures
  pre-2026-05-03 have no listed-contract metadata; review surfaces
  honor this with `provider_option_snapshot_not_found` + structure-
  level warning. Code path correct; data drift acknowledged.
- **Index risk fields are not persisted.** `IndexRiskSignals` is a
  Pydantic schema returned per request; not directly queryable
  historically. Matches "deterministic derivation."
- **Index gaps on lineage keys.** `paper_positions.replay_run_id`,
  `paper_trades.replay_run_id`, and `paper_trades.position_id` are
  declared as columns in `domain/models.py:402, 421, 424` without
  explicit indexes. Not a correctness issue; flagged for diligence
  / query-performance hygiene.

---

## 11. Test Coverage Reality

| Major claim | Tests that prove it | Gaps |
|---|---|---|
| Local DB authoritative for approval / role | `tests/test_auth_approval_api.py`, `tests/test_user_identity_reconciliation.py` | None |
| LLM cannot set trade levels / sizing / approval | `tests/test_llm_integration.py` (28), guardrail-stripping logic | Real OpenAI not exercised |
| **Live broker routing refused in code** (new) | `tests/test_phase4_providers.py:404-461` (4 tests; `posted == []` asserted) | None within source |
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
| **`display_id` collision-free (within minute)** | `tests/test_display_id_and_user_settings.py:121-227` (frozen-clock test) | None |

Frontend coverage is solid for the critical visible surfaces.
`test_compliance_readiness.py` is mostly source-string assertions
(file existence + keyword presence), not behavior. This is real and
unchanged from the prior audit.

Skipped / xfail / shallow: zero `@pytest.mark.skip`,
`@pytest.mark.xfail`, or `slow` markers in `tests/`. The deployed
Playwright spec self-skips when smoke auth is not configured.

---

## 12. Security / Audit Readiness Reality

- **Auth.** Local DB authoritative; admin gate adds MFA when
  configured. ✅
- **IDOR.** Owner-scoped queries appear consistently in `admin.py`
  user-router routes. `tests/test_security_authorization.py` (6) and
  `tests/test_security_hardening.py` (8) cover the cross-user blocked
  cases. ✅
- **Rate limits.** `src/macmarket_trader/api/security.py` defines
  `HIGH_COST_ROUTE_LIMITS` for provider/LLM/recommendation/replay
  routes. In-memory; per-process. ✅ for current scale; a real reverse
  proxy / API gateway would supersede.
- **Origin / CSRF.** `validate_mutation_origin(...)` checks
  Origin/Referer on browser-originated mutating requests; allows
  server-to-server / local test calls without Origin. Default
  allowed-origins set is hard-coded to `macmarket.io`,
  `www.macmarket.io`, localhost variants. ✅
- **Headers.** `apps/web/next.config.ts` carries security headers
  (CSP report-only, `nosniff`, `DENY`, strict-origin-when-cross-origin
  referrer, `Permissions-Policy`). HSTS correctly delegated to the
  CF/edge layer.
- **Secret scanning.** `scripts/scan_secrets.py` runs in the release
  gate; `tests/test_compliance_readiness.py` exercises redaction.
  Provider Health responses redact secrets via
  `_sanitize_provider_error(...)`. ✅
- **Deployment exclusions.** `scripts/create_clean_release_archive.py`
  excludes `.env`, `.tmp`, `.next`, AI worktrees, runtime DBs. ✅
- **Provider-health redaction.** Confirmed in test +
  `openai_provider._redact(...)` is comprehensive (replaces api_key
  with `[redacted]`, strips `Authorization`).
- **Admin invite tokens.** Masked in admin payloads (per Phase 11
  defensive pass 2 and `admin.py`).
- **FastAPI docs in prod.** Disabled when `environment` is
  `prod`/`production` and `api_docs_enabled=False` (verified at
  `api/main.py:29 _api_docs_kwargs(...)`). ✅
- **Dependency audit.** `npm audit` moderate dev-server vulns are
  acknowledged in CLAUDE.md and roadmap-status.

**Remaining P2/P3.**

- **`paper_positions.opened_qty/remaining_qty` and
  `paper_trades.realized_pnl` columns lack a migration** (P2; runtime
  shim covers it, but the migration ledger lies about the schema).
- **Three lineage indexes missing** (P3; perf/diligence hygiene).
- **Compliance evidence is template-grade only** (P2 for diligence;
  not a user-safety risk; honestly framed in docs now).
- **npm vitest/vite/esbuild moderate vulns deferred** (P3, dev-only).
- **`/account` does not embed Clerk `<UserProfile>` for self-service
  MFA** (P3, paid Clerk feature).
- **`atm_straddle_mid` not yet emitted** (P3; documented).

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
- `tests/test_model_validation.py` (6) verifies the validation
  script's shape but not actual performance.

**Buyer-grade?** No. The current claim ("preliminary internal
validation evidence only") is honest. Acquirer-grade evidence would
require: dated point-in-time validation set, signed walk-forward
split definitions, benchmark capital assumptions, drift monitoring,
and counsel review. The roadmap acknowledges all of this.

---

## 14. Gaps & Overstatements — Ranked

| # | Title | Severity | Doc claim | Evidence | Blast radius | Recommended correction |
|---|---|---|---|---|---|---|
| 1 | Test counts drifted again | P2 | CLAUDE.md and roadmap-status.md state pytest 469 / vitest 243 / Playwright 32 | Actual `pytest --collect-only -q` reports 473 collected | Operator trust | Update counts to 473 (or add a "verified within ±10 of YYYY-MM-DD" tolerance note) |
| 2 | Three ORM columns lack a real migration | P2 | CLAUDE.md "apply_schema_updates handles nullable runtime drift only" | `paper_positions.opened_qty`, `paper_positions.remaining_qty`, `paper_trades.realized_pnl` exist in `domain/models.py:399-400, 418` but in **no** Alembic upgrade body | Acquisition diligence + DB hygiene | Backfill via a new Alembic migration; remove from runtime shim path |
| 3 | Missing indexes on three lineage keys | P3 | None (latent) | `paper_positions.replay_run_id`, `paper_trades.replay_run_id`, `paper_trades.position_id` mapped without `index=True` (`domain/models.py:402, 421, 424`) | Query performance / diligence | Add explicit indexes in next migration |
| 4 | Compliance docs read heavier than evidence supports in places | P2 | `docs/compliance/acquisition-readiness.md`, `docs/compliance/control-matrix.md` self-attest controls without signed evidence | All compliance docs are templates; no `evidence/*` artifacts in-tree | Acquisition diligence | Tighten language to "scaffolding for future audit"; commit first signed evidence |
| 5 | `atm_straddle_mid` allowed by schema but never emitted | P3 | Acknowledged in CLAUDE.md and roadmap-status.md | `domain/schemas.py:679` allows it; no production code emits `method="atm_straddle_mid"` | Operator trust | OK as-is; track as small follow-up |
| 6 | `MacMarket-Strategy-Reports` vs `MacMarket-StrategyScheduler` task duplication | P3 | CLAUDE.md and roadmap "Still Open" both flag | Unverifiable in source | Operator confusion | Verify on deployed host, delete the duplicate |
| 7 | Deployed UI smoke not exercised | P3 | `docs/compliance/deployed-smoke-testing.md` describes the procedure | Spec exists; not run in this audit | Audit confidence | Run the spec, commit a sanitized evidence sample |
| 8 | `/account` page lacks Clerk `<UserProfile>` MFA enrollment | P3 | CLAUDE.md / roadmap "Still Open" | Clerk MFA is a paid feature; Open Item | UX completeness | Either enable Clerk paid plan or admin-enroll path documented |

**Closed by `d86f398`/`fed4b1f` (post-prior-audit pass).**

| # | Title | Severity (prior) | How it was closed |
|---|---|---|---|
| 1 | CLI `poll-alpaca-fills` does not exist | P1 | CLAUDE.md "Test and build commands" section now states the CLI does not exist; the line that advertised the command was removed. CLI verified by `python -m macmarket_trader.cli --help`. |
| 2 | Test counts stale (271/199/31) | P1 | Updated to 469/243/32; this audit catches the smaller drift to 473. |
| 3 | `save_alternative` listed as not implemented | P2 | Removed from "Open Items" in CLAUDE.md and roadmap-status.md. Behavior already covered by `tests/test_recommendations_api.py::test_user_ranked_queue_candidate_can_be_saved_as_alternative`. |
| 4 | Phase 11/11B/12 framing implied audit-readiness | P2 | CLAUDE.md and roadmap-status.md now explicitly self-label as "scaffolding / foundation only — not signed compliance evidence, not certified audit readiness, not buyer-grade diligence packages." |
| 5 | "Expiration settlement remains deferred" wording was partly stale | P2 | Reworded: manual paper-only `settle-expiration` endpoint is live; full settlement automation, broker exercise, assignment automation remain deferred. |
| 6 | Schema source-of-truth split between Alembic and `apply_schema_updates()` | P2 | CLAUDE.md adds explicit note: "`apply_schema_updates()` handles nullable runtime drift only. New tables, non-nullable columns, indexes, and structural schema changes still require an Alembic migration." (Three columns still lack a real migration — see new finding #2.) |
| 7 | "Live trading is not active" was configuration-only | P2/P1 | `LIVE_TRADING_ALLOWED=false` (default) added as in-process kill switch. Registry raises `LiveTradingDisabledError`; method-level defense-in-depth in `AlpacaBrokerProvider.place_paper_order(...)`. 4 new tests assert no HTTP attempted. |
| 8 | `display_id` same-minute collision unmitigated | P3 | `_resolve_display_id_collision(...)` adds deterministic `-2`, `-3`, ... suffix; canonical id unaffected; frozen-clock test added. |
| 9 | Operator runbook predated recent passes | P3 | `docs/private-alpha-operator-runbook.md` extended +142 lines with index-risk, settle-expiration, options review reading guide. |
| 10 | `docs/architecture.md` was thin | P3 | Extended +124 lines with deterministic constraints, LLM boundary, paper-only language. |

---

## 15. Recommended Doc Corrections

For each item, the proposed wording change. **Do not apply** without
review.

1. **CLAUDE.md → "Current Phase Status" test-count line** — Current:
   > `Tests (2026-05-05, audit-fixes pass): pytest **469** collected; vitest **243**; Playwright **32**; tsc clean.`
   Proposed:
   > `Tests (2026-05-07): pytest **473** collected; vitest **243**; Playwright **32**; tsc clean.`
   Reason: actual `pytest --collect-only -q` reports 473.
   Same edit applies to the matching line in
   `docs/roadmap-status.md` 2026-05-05 update.

2. **CLAUDE.md → "Important implementation constraints"** — Add an
   item:
   > `- The ORM declares three columns the Alembic ledger does not add: paper_positions.opened_qty, paper_positions.remaining_qty, paper_trades.realized_pnl. apply_schema_updates() patches them at startup, but a future migration should backfill them so the migration ledger faithfully describes the runtime schema.`
   Reason: documents the residual schema drift; pre-empts diligence
   findings.

3. **`docs/compliance/acquisition-readiness.md`** — Tighten language:
   anywhere the doc reads as "we are SOC-2 / acquirer-ready" it
   should say "scaffolding for future audit / acquirer review;
   signed evidence not yet committed in-tree." (`docs/compliance/README.md`
   already uses this framing — extend it.)

4. **`docs/roadmap-status.md` → Still Open** — Add:
   > `- Three ORM-only columns (paper_positions.opened_qty, paper_positions.remaining_qty, paper_trades.realized_pnl) lack a real Alembic migration; apply_schema_updates() covers them at startup. Backfill before any acquirer review.`

5. **`docs/architecture.md`** — Refresh with: the
   `LIVE_TRADING_ALLOWED` boundary, `apply_schema_updates()` split,
   and a sentence about `paper_option_*` tables.

---

## 16. Recommended Next Work

| Item | Scope | Files likely touched | Tests required | Definition of Done | Priority |
|---|---|---|---|---|---|
| Backfill the three ORM-only columns with a real migration | New Alembic revision after 0010 | `alembic/versions/<new>.py`, no model change | `tests/test_storage.py` (or new schema test) asserts presence | New revision adds `opened_qty`, `remaining_qty`, `realized_pnl`; `apply_schema_updates()` shim becomes a no-op for them | P2 |
| Doc-only correction pass (test counts, drift note, compliance tightening) | Apply §15 edits | `CLAUDE.md`, `docs/roadmap-status.md`, `docs/compliance/acquisition-readiness.md`, `docs/architecture.md` | None new; existing tests still green | Test-count line accurate; schema-drift constraint added; compliance language tightened | P2 |
| Add explicit indexes on three lineage keys | Performance / diligence hygiene | New Alembic revision | New tests are optional | `paper_positions.replay_run_id`, `paper_trades.replay_run_id`, `paper_trades.position_id` indexed | P3 |
| Verify scheduled task duplication | Operator-only check | None in repo; deployed host inspection | None | `MacMarket-Strategy-Reports` removed if duplicate of `MacMarket-StrategyScheduler` | P3 |
| First signed compliance evidence pass | Sign access review, vendor review, restore-drill, model-validation | `docs/compliance/*-evidence-*.md`, `.tmp/evidence/*` (or off-host with reference) | Existing compliance tests | At least one signed end-to-end evidence set committed (or deliberately stored off-host with reference) | P2 |
| Emit `atm_straddle_mid` when ATM mids available | Backend emit path | `src/macmarket_trader/api/routes/admin.py` (`_build_options_expected_range`), `src/macmarket_trader/analysis_packets.py` | Extend `tests/test_strategy_reports.py` with synthetic ATM-mid scenario | Live emit path produces `method="atm_straddle_mid"` when IV missing but ATM mids present | P3 |
| Deployed UI smoke evidence | Run the deployed Playwright spec on a sanitized account; commit redacted artifacts | `apps/web/tests/e2e/deployed-smoke.spec.ts`, `.tmp/evidence/deployed-ui-smoke-*` (or off-host) | Existing | One end-to-end smoke run captured for a release tag | P3 |

No scope creep. No broad rewrites.

---

## 17. Open Questions / Required Manual Evidence

- **Deployed `https://macmarket.io` UI smoke.** Requires Cloudflare
  Access service token *or* a stored Playwright auth state for an
  approved test user. Cannot be run from this audit pass.
- **Real OpenAI / Polygon / FRED / Resend / Alpaca probes.** Not
  exercised here. Provider Health code paths are structurally
  correct; live behavior depends on plan + entitlement.
- **Cloudflare Access policy review.** Whether invite-only
  enforcement is configured correctly cannot be inferred from source.
- **Windows Task Scheduler state.** Whether the suspected
  `MacMarket-Strategy-Reports` task is in fact a duplicate of
  `MacMarket-StrategyScheduler` requires a `schtasks` query on the
  deployed host.
- **DB backup restore drill.** Scripts exist; no committed restore
  evidence. A monthly drill should produce a dated artifact.
- **Counsel review of regulatory boundary memo.** Internal-grade
  only; no signed external review in-tree.
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
