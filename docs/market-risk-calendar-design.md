# Market Risk Calendar & Sit-Out Guardrails

MacMarket's risk calendar is a paper-only, research-first guardrail layer. It helps the operator identify days or windows where new paper entries should be warned, restricted, or blocked. It does not route orders, automate exits, or create trades.

The governing rule remains unchanged: LLMs explain and extract. Rules and models decide and size. Opportunity Intelligence may summarize why a day is risky, but the deterministic risk gate owns the decision state, confirmation requirement, and block status.

## Scheduled Event Risk

The risk calendar evaluates market, sector, symbol, and portfolio-scoped events:

- macro releases: CPI, PCE, FOMC decision/press conference, nonfarm payrolls, GDP, retail sales, Treasury auctions
- market structure events: holidays, half days, monthly/quarterly options expiration, quad witching, index rebalances
- symbol events: earnings, earnings calls, investor days, product events, regulatory events
- operational events: unscheduled news shocks and provider data issues

The first provider is static/mock by design so local startup and tests require no external event-calendar credentials. Future providers can add live macro calendars, earnings calendars, news calendars, and exchange calendars behind the same provider boundary.

## Decision States

The deterministic gate emits one of:

- `normal`
- `caution`
- `restricted`
- `no_trade`
- `requires_event_evidence`
- `data_quality_block`

Each assessment includes `allow_new_entries`, `requires_confirmation`, `recommended_action`, `risk_level`, `block_reason`, `warning_summary`, `active_events`, `missing_evidence`, `override_allowed`, and `override_reason_required`.

## Earnings And Event-Trade Exceptions

Normal swing setups should be blocked or marked `requires_event_evidence` when the symbol has earnings inside the configured avoidance window and verified context is missing.

Event-trade review is allowed only when current structured evidence exists. Evidence can include expected-move context, earnings history, sector context, or verified alternative data, but those fields must come from a real provider or test fixture. The system must say what is missing; the LLM must not invent credit-card spending trends, options context, or earnings history.

Even with verified event evidence, the state should remain `restricted` / `event_trade_review`, not silently become `normal`.

## Volatility Circuit Breakers

The gate can evaluate measured conditions where data exists:

- VIX above threshold when VIX data is available
- SPY/QQQ gap above threshold
- intraday realized range above threshold
- future breadth/risk-off fields
- stale or degraded provider data

If a required data input is unavailable, the assessment reports missing evidence or data quality limitations instead of fabricating a reading.

## Paper Order Integration

Paper equity order staging re-evaluates the risk gate before staging/filling. `no_trade`, `requires_event_evidence`, and `data_quality_block` block staging. `restricted` requires explicit operator confirmation and a reason. Risk-calendar provenance is recorded in paper-order notes/provenance.

This is not live trading support, broker routing, or automated execution. It is a paper-only sit-out and confirmation layer.

## UI Expectations

Dashboard shows a "Market Risk Today" card with the current state, top reasons, active events, missing evidence, and recommended action.

Recommendations show risk-calendar badges and detail context on stored recommendations.

Orders shows the calendar warning/block context before paper order staging, including explicit "sit this one out" messaging when new entries are blocked and confirmation fields when restricted.

## LLM Role

LLM and Opportunity Intelligence may explain:

- why today is risky
- why a candidate is event-exposed
- what evidence is missing
- why sitting out may be reasonable

LLM output cannot change risk decision fields, create unscanned candidates, change approval, entry, invalidation, targets, shares, sizing, order status, or paper-position status.

## Future Provider Gaps

Open provider work:

- live macro calendar integration
- live earnings calendar integration
- verified options expected-move context
- verified earnings-history and sector context
- verified alternative-data sources such as credit-card trends
- full exchange holiday/half-day calendar source
- richer regular-hours-only intraday volatility aggregation
