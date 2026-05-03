# Model Risk Management

MacMarket-Trader uses deterministic engines for trade setup, risk, ranking,
sizing, and paper lifecycle decisions. LLMs are explanation-only.

## Deterministic Engines

- Setup/risk/ranking engines produce structured recommendation fields.
- Market Risk Calendar owns warning/restriction/block state.
- Paper lifecycle code owns order, fill, position, trade, P&L, and reset state.
- Active Paper Position Review uses deterministic action classifications.
- Options Position Review uses deterministic structure-level classifications
  from persisted lifecycle data and provider-backed option snapshots when
  available. It exposes missing or stale option marks rather than estimating
  them with an unapproved pricing model.

## LLM Boundary

- LLMs may summarize, compare, explain, and draft research prose.
- LLMs cannot alter approval, side, entry, stop, target, sizing, risk-calendar
  decision, order creation, or paper action classification.
- OpenAI output is schema validated and can fall back to deterministic mock.

## Versioning Gap

Current code and payloads include some provenance fields, but there is no
formal model/rules version register yet. Future releases should track:

- setup engine version
- risk engine version
- ranking engine version
- prompt version
- provider/model version
- validation dataset version

## Validation Evidence Needed

- Walk-forward and replay validation by symbol/timeframe/regime.
- Benchmark comparison against simple baselines.
- Attribution by setup, regime, catalyst, and provider/source.
- Drift monitoring for provider changes, model changes, and strategy changes.
- Human approval/sign-off for strategy/ranking changes.

## Phase 12 Validation Foundation

Phase 12 adds a model inventory and validation report template:

- `docs/compliance/model-inventory.md`
- `docs/compliance/model-validation-report-template.md`

It also adds `scripts/run_model_validation.py`, a read-only local evidence
generator that summarizes stored deterministic recommendations, replay runs,
paper trades, attribution slices, and SPY/QQQ baseline data when local
`daily_bars` coverage exists. Missing validation inputs are reported as
`missing_data`; the script does not fabricate performance and does not call
LLMs, live providers, broker APIs, or order-routing paths.

## Preliminary Evidence

- Unit/integration tests for recommendation contracts.
- Replay tests.
- Risk-calendar tests.
- Active Paper Position Review tests.
- Lifecycle integrity test.
- Options Position Review and options lifecycle integrity tests.
- Provider-backed option snapshot mark precedence and Options Position Review
  mark-to-open P&L tests.
- LLM validation and fallback tests.
- Model validation evidence generator tests.

## Remaining Gaps

- No independently reviewed historical validation pack.
- No formal model-change approval board.
- No recurring drift report.
- No approved walk-forward validation dataset/version register.
- No independent review of benchmark methodology.
- No approved options mark/Greeks model validation pack. Current options
  review uses provider-supplied bid/ask, last trade, IV, open interest, and
  Greeks when available, but does not calculate Black-Scholes values or Greeks.
  Missing, stale, or plan-blocked provider marks remain explicit
  `mark_unavailable` evidence.
