# Model Risk Management

MacMarket-Trader uses deterministic engines for trade setup, risk, ranking,
sizing, and paper lifecycle decisions. LLMs are explanation-only.

## Deterministic Engines

- Setup/risk/ranking engines produce structured recommendation fields.
- Market Risk Calendar owns warning/restriction/block state.
- Market Risk Calendar now includes deterministic index-risk signals from
  provider-backed SPX, NDX, RUT, and VIX snapshots when available. VIX level,
  VIX spikes, SPX downside moves, RUT/NDX relative weakness, dispersion, and
  stale/missing index data are surfaced as auditable context. Missing index data
  is a data-quality warning, not fabricated risk input.
- Paper lifecycle code owns order, fill, position, trade, P&L, and reset state.
- Active Paper Position Review uses deterministic action classifications.
- Options Position Review uses deterministic structure-level classifications
  from persisted lifecycle data and provider-backed option snapshots when
  available. It exposes missing or stale option marks rather than estimating
  them with an unapproved pricing model.
- Options research and paper-open persistence resolve target strikes to listed
  provider contracts when provider-backed options data is configured. Original
  theoretical targets, selected listed strikes, provider symbols, and snap
  distances are retained as provenance; unresolvable contracts are blocked
  rather than silently persisted as markable positions.
- Listed-contract options setups are also blocked when the selected strike is
  outside the configured snap-distance allowance. Fresh provider `quote_mid` or
  `last_trade` marks are required for paper-open pricing; theoretical estimates
  and prior-close fallback marks remain labeled context and are not silently
  treated as fresh opening prices.
- Options expiration review uses deterministic intrinsic-value, moneyness,
  assignment-risk, exercise-risk, and paper-only settlement-preview logic.
  Manual expiration settlement requires explicit confirmation and does not
  automate exercise, assignment, rolling, adjustment, or broker routing.
- Analysis Packet context aggregates deterministic setup fields with
  provider-supplied macro/news/options snapshot context for UI and email. FRED
  series, Polygon/Massive news, IV, open interest, Greeks, and option marks are
  displayed only when supplied by configured providers; missing values remain
  explicit `missing_data`.
- Analysis Packet and scheduled strategy-report email output include compact
  index-risk context when present. LLM/Opportunity Intelligence may explain the
  context, but deterministic risk-calendar fields remain authoritative.
- Operator Analysis Packet preview/export exposes the same sanitized packet as
  JSON, Markdown, and email-safe HTML for stored recommendations. The export is
  a context snapshot only; it does not recalculate rankings, alter strategy
  fields, create paper orders, or send broker instructions.

## LLM Boundary

- LLMs may summarize, compare, explain, and draft research prose.
- LLMs cannot alter approval, side, entry, stop, target, sizing, risk-calendar
  decision, order creation, or paper action classification.
- OpenAI output is schema validated and can fall back to deterministic mock.
- LLM summaries may use backend-supplied macro/news context only as
  explanation input. They must not invent headlines, macro values, option
  marks, Greeks, IV, or open interest.

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
- Index-risk signal extraction and risk-calendar integration tests.
- Active Paper Position Review tests.
- Lifecycle integrity test.
- Options Position Review and options lifecycle integrity tests.
- Provider-backed option snapshot mark precedence and Options Position Review
  mark-to-open P&L tests.
- Listed option contract resolution, old synthetic-contract warning, and SPX
  index/cash-settlement review tests.
- Options expiration review and manual paper settlement tests.
- Analysis Packet and email/export context tests for FRED macro summaries,
  Polygon/Massive news mapping, option IV/OI/Greeks display, missing-data
  handling, and paper-only disclaimers.
- Recommendation Analysis Packet preview/export tests for user scoping,
  Markdown/HTML rendering, secret redaction, unavailable provider fields, and
  paper-only/no-routing disclaimers.
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
- No independently reviewed index-regime threshold validation pack. Current
  SPX/NDX/RUT/VIX thresholds are conservative defaults and should be tuned only
  through a documented model-change process.
