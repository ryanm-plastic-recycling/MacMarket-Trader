# MacMarket-Trader

MacMarket-Trader is a **research-first, event-driven trading system** for U.S. large-cap equities and liquid sector ETFs.

Its job is not to let an LLM improvise trades.

Its job is to:

1. ingest market, macro, and company news
2. normalize that information into structured events
3. place those events inside a market-regime framework
4. produce **deterministic, auditable trade recommendations**
5. route those recommendations into paper execution first
6. measure outcome, attribution, and model quality over time

## Core design principle

**LLMs explain and extract. Rules and models decide and size.**

LLMs are used for:
- headline and filing summarization
- entity extraction
- event classification
- horizon tagging
- contradiction / counter-scenario generation
- human-readable recommendation explanations

LLMs are **not** the final source of truth for:
- whether a trade exists
- entry levels
- stop levels
- target levels
- position sizing
- portfolio risk decisions
- order routing

Those are handled by deterministic engines with full audit trails.

## Investment mandate

### v1 mandate

- **Tradable universe:** U.S. large-cap equities and liquid sector ETFs only
- **Style:** event-driven swing trading
- **Holding period:** 1 to 5 trading days
- **Session:** regular hours only
- **Execution mode:** paper trading first
- **Directionality:** long and short in research; live deployment gated behind explicit broker and risk approval
- **Recommendation standard:** every recommendation must include thesis, catalyst, regime context, entry plan, invalidation, targets, sizing logic, and evidence bundle

### Explicit non-goals for v1

- crypto
- options execution
- social sentiment as a primary signal
- public consumer app features
- generic LLM trade generation
- static percentage exits like “take profit at 5%” without structure-based support
- UI-heavy work before engine credibility exists

## What the system must produce

Every recommendation must be structured like this:

```json
{
  "symbol": "NVDA",
  "side": "long",
  "thesis": "Post-earnings continuation with sector leadership intact",
  "catalyst": {
    "type": "earnings_guidance",
    "timestamp": "2026-03-31T13:30:00Z",
    "novelty": "high",
    "source_quality": "primary"
  },
  "regime": {
    "market_regime": "risk_on_trend",
    "volatility_regime": "moderate",
    "breadth_state": "supportive"
  },
  "entry": {
    "type": "breakout_pullback",
    "zone_low": 901.25,
    "zone_high": 907.40,
    "trigger": "hold above prior day high with RVOL >= 1.4"
  },
  "invalidation": {
    "price": 886.80,
    "reason": "below event support and 14D ATR buffer"
  },
  "targets": {
    "target_1": 925.50,
    "target_2": 941.20,
    "trailing_rule": "trail below 2-day low after T1"
  },
  "time_stop": {
    "max_holding_days": 5,
    "reason": "event half-life exhausted"
  },
  "sizing": {
    "risk_dollars": 750,
    "stop_distance": 17.10,
    "shares": 43
  },
  "quality": {
    "expected_rr": 1.8,
    "confidence": 0.64,
    "risk_score": 0.37
  },
  "evidence": {
    "headlines": [],
    "filings": [],
    "technical_context": [],
    "historical_analogs": []
  }
}
```

## Entry and exit philosophy

MacMarket-Trader does not use generic fixed exits.

Recommendations are built from market structure and event context, using inputs such as:
- prior day high / low
- event day range
- recent support / resistance
- ATR / realized volatility
- relative volume
- sector ETF relative strength
- gap statistics
- expected event half-life
- later: anchored VWAP and intraday liquidity structure

At launch, if intraday data is unavailable, the system uses a clearly labeled daily-structure approximation and does **not** pretend it has higher precision than the data supports.

## Architecture

```text
Raw data ingestion
    -> point-in-time event store
    -> normalized feature store
    -> event classification layer
    -> regime engine
    -> setup engine
    -> portfolio / risk engine
    -> order intent / OMS
    -> paper broker adapter
    -> attribution / audit trail
```

## Core subsystems

### 1. Event ingestion and normalization

Responsible for ingesting and timestamping:
- market news
- macro calendar events
- earnings and guidance events
- company filings and press releases
- corporate actions
- price bars and reference data

Outputs:
- normalized event records
- source metadata
- entity links
- first-seen timestamps
- provenance references

### 2. Event taxonomy

Initial event taxonomy includes:
- earnings
- guidance
- M&A
- analyst action
- product / launch
- litigation
- regulation / policy
- macro release
- rates / central bank
- geopolitical escalation
- supply chain / commodity shock
- management change
- corporate action

### 3. Regime engine

The regime engine classifies the backdrop before any trade recommendation is allowed.

Required outputs:
- trend vs chop
- high-vol vs low-vol
- risk-on vs risk-off
- breadth state
- sector leadership state
- macro event proximity
- rates / dollar / credit context hooks

### 4. Setup engine

The setup engine translates event + regime + price context into a specific trade plan.

Initial setup families:
- event continuation
- gap-and-go continuation
- post-event pullback continuation
- failed event / fade
- sector sympathy trade
- macro shock index / sector response

### 5. Portfolio and risk engine

The risk engine is deterministic and auditable.

Required controls:
- per-trade dollar risk
- max position size
- max portfolio heat
- sector concentration caps
- factor / correlation caps
- daily loss limit
- no-trade windows around major macro events
- overnight exposure rules
- hard kill switch

### 6. OMS and execution

Execution is paper-only at first.

The OMS must support:
- order intents
- state transitions
- partial fills
- cancel / replace
- dedupe / idempotency
- session rules
- slippage and fee accounting
- portfolio reconciliation

### 7. Research and replay

The same decision logic used in live recommendation generation must also power historical replay.

Required properties:
- point-in-time data access
- walk-forward evaluation
- realistic slippage hooks
- event-time integrity
- performance attribution by setup, regime, and catalyst type

### 8. Audit and governance

Every recommendation and order must be traceable.

Required artifacts:
- model / rules version
- input data timestamps
- recommendation payload
- evidence bundle
- final order and fill state
- post-trade outcome
- attribution notes

## Repository philosophy

The new repository is intentionally narrow.

### What is in scope now

- Python backend only
- typed domain models
- deterministic engines
- mock and paper adapters
- unit tests and contract tests
- CLI and JSON API
- audit-first data model

### What is out of scope now

- React dashboard
- admin portal
- account system
- Discord bot
- SMS/email notification UI
- crypto
- indicator showcase pages
- legacy strategy playgrounds

## Proposed repository layout

```text
macmarket-trader/
  README.md
  pyproject.toml
  .env.example
  src/macmarket_trader/
    api/
    config/
    data/
    domain/
    llm/
    regime/
    setups/
    risk/
    portfolio/
    execution/
    replay/
    audit/
    utils/
  tests/
  docs/
  scripts/
  experimental/
```

## Initial data contracts

The initial codebase should define typed contracts for:
- `NewsEvent`
- `MacroEvent`
- `CorporateEvent`
- `Bar`
- `RegimeState`
- `TechnicalContext`
- `TradeSetup`
- `TradeRecommendation`
- `OrderIntent`
- `OrderRecord`
- `FillRecord`
- `PortfolioSnapshot`
- `BacktestRun`
- `AuditRecord`

## Initial development phases

### Phase 0 — clean scaffold
- repository skeleton
- typed config
- logging
- linting / testing / formatting
- mock providers
- paper broker interface

### Phase 1 — domain model and contracts
- event taxonomy
- regime state model
- recommendation schema
- audit schema
- deterministic risk formulas

### Phase 2 — recommendation engine
- event classification interface
- daily-structure setup logic
- non-generic entry / stop / target calculation
- recommendation explanation generator

### Phase 3 — replay and paper OMS
- replay runner
- paper execution ledger
- position lifecycle
- attribution reports

### Phase 4 — real vendor integrations
- replace mock providers with vetted market/news/broker adapters
- preserve the same interfaces
- keep research/live parity

## Success criteria for v1

MacMarket-Trader v1 is successful only if it can do all of the following:

1. generate recommendations with explicit thesis, entry, stop, and targets
2. explain why the trade exists in the current regime
3. reject low-quality trades instead of forcing output
4. size risk deterministically
5. replay the same logic historically without lookahead bias
6. store every decision with evidence and provenance
7. produce paper-trade attribution by setup and regime

## Legacy code policy

The old MacMarket repository is a **reference archive**, not a base layer.

By default, no old application code is carried into the new system.
Only isolated, testable, non-core research utilities may be imported later under `experimental/`.

## Current status

This repository is a ground-up rebuild.

The first milestone is not a dashboard.
The first milestone is a credible recommendation pipeline.
