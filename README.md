# MacMarket-Trader

MacMarket-Trader is a **research-first, event-driven trading system** for U.S. large-cap equities and liquid sector ETFs.

Its job is not to let an LLM improvise trades.

Its job is to:

1. ingest market, macro, and company events,
2. normalize that information into structured records,
3. place those events inside a market-regime framework,
4. produce **deterministic, auditable trade recommendations**,
5. route those recommendations into paper execution first,
6. measure outcome, attribution, and replay/live parity over time.

## Canonical README policy

This root `README.md` is the **canonical architecture charter** for the repository.

- `docs/` may expand on specific topics.
- `docs/` must not replace or materially shrink the root architecture definition.
- Do not auto-condense this README into a status page.
- The root README must remain the main source of truth for mandate, pipeline, constraints, and subsystem design.

## Core design principle

**LLMs explain and extract. Rules and models decide and size.**

LLMs are used for:
- headline and filing summarization,
- entity extraction,
- event classification,
- horizon tagging,
- contradiction / counter-scenario generation,
- human-readable recommendation explanations.

LLMs are **not** the final source of truth for:
- whether a trade exists,
- entry levels,
- stop levels,
- target levels,
- position sizing,
- portfolio risk decisions,
- order routing.

Those are handled by deterministic engines with full audit trails.

## Investment mandate

### v1 mandate

- **Tradable universe:** U.S. large-cap equities and liquid sector ETFs only
- **Style:** event-driven swing trading
- **Holding period:** 1 to 5 trading days
- **Session:** regular hours only
- **Execution mode:** paper trading first
- **Directionality:** long and short in research; deployment gated behind explicit broker and risk approval
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

Every recommendation must be structured like this conceptually:

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
    "reason": "below event support and volatility buffer"
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
    "confidence": 0.67,
    "risk_score": 0.43
  },
  "approved": true,
  "rejection_reason": null,
  "evidence": {
    "headlines": [],
    "filings": [],
    "technical_context": [],
    "historical_analogs": []
  }
}
```

A valid system output must also support a deterministic **no-trade** outcome.

## Entry and exit philosophy

MacMarket-Trader does not use generic fixed exits.

Recommendations are built from market structure and event context, using inputs such as:
- prior day high / low,
- event day range,
- recent support / resistance,
- ATR / realized volatility,
- relative volume,
- sector ETF relative strength,
- gap statistics,
- expected event half-life,
- later: anchored VWAP and intraday liquidity structure.

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
- persisted pre-step and post-step portfolio snapshots for each replay step

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

## HACO and HACOLT policy

HACO is **not** being discarded.

It stays in the new product, but in the correct role.

### What HACO should be in MacMarket-Trader

1. **A charting and operator-visualization primitive**
   - dedicated chart experience with buy/sell flip arrows
   - lower confirmation strip with green/red state bars
   - long-term HACOLT trend strip beneath the main chart

2. **A secondary technical-context feature**
   - current HACO state
   - recent HACO flips
   - HACOLT direction
   - alignment / divergence between event thesis and HACO state

3. **A research strategy family**
   - separate from the core event-driven recommendation engine
   - testable on its own
   - combinable later with event, regime, and sector filters

### What HACO should not be in v1

- the sole trade-approval engine for the main product
- an excuse to bypass event context, regime, or risk rules
- a legacy sidecar UI copied wholesale from the old repo

### Legacy reuse policy for HACO

The following old-repo items are eligible for selective reuse **only after cleanup and re-typing**:
- pure indicator math from old `indicators/haco.py`
- Heikin-Ashi helper logic from old `indicators/common.py` and `indicators/haco_ha.py`
- long-trend helper logic from old `indicators/hacolt.py`
- HACO unit-test cases from old `tests/test_haco.py`
- chart payload ideas from old signal/chart code

The following should **not** be carried over:
- old HACO routes
- old alert workers
- old HTML/JS pages
- old server glue
- old schema tables tied to legacy user settings

### HACO deliverables for the new repo

- typed indicator module under `src/macmarket_trader/indicators/`
- typed chart payload schema for candles, markers, HACO strip, and HACOLT strip
- protected backend API route for HACO chart payload generation
- protected frontend page inside the operator console
- tests for indicator math, state transitions, and API payload shape

## Repository philosophy

The new repository is intentionally narrow.

### What is in scope now

- typed backend domain models
- deterministic engines
- point-in-time data contracts
- paper execution flow
- recommendation audit persistence
- replay/live parity work
- protected operator/admin surfaces
- charting and evidence review for operators

### What is out of scope now

- public consumer growth features
- social/community tooling
- crypto expansion
- options execution
- legacy strategy playground sprawl
- allowing the frontend to outrun the engine

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
    indicators/
    llm/
    regime/
    setups/
    risk/
    portfolio/
    execution/
    replay/
    audit/
  apps/
    web/
  tests/
  docs/
  scripts/
  experimental/
```

## Initial data contracts

The codebase should define typed contracts for:
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
- `ReplayRun`
- `ReplayStep`
- `AuditRecord`
- `HacoChartPayload`
- `HacoSignalPoint`
- `HacoMarker`

## Development phases

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
- explicit no-trade quality gates

### Phase 3 — replay and paper OMS
- replay runner
- paper execution ledger
- position lifecycle
- attribution reports
- per-step snapshot persistence

### Phase 4 — vendor integrations
- replace mock providers with vetted market/news/broker adapters
- preserve the same interfaces
- keep research/live parity

### Phase 5 — operator console
- admin approval views
- recommendation explorer
- replay explorer
- order blotter
- provider health
- HACO chart workspace

## Success criteria for v1

MacMarket-Trader v1 is successful only if it can do all of the following:

1. generate recommendations with explicit thesis, entry, stop, and targets
2. explain why the trade exists in the current regime
3. reject low-quality trades instead of forcing output
4. size risk deterministically
5. replay the same logic historically without lookahead bias
6. store every decision with evidence and provenance
7. produce paper-trade attribution by setup and regime
8. expose HACO/HACOLT as a professional operator chart and a secondary technical feature

## Legacy code policy

The old MacMarket repository is a **reference archive**, not a base layer.

By default, no old application code is carried into the new system.
Only isolated, testable, non-core research utilities may be imported later under `experimental/` or re-homed into typed modules after review.

## Current status

This repository is a ground-up rebuild.

The first milestone is not a flashy dashboard.
The first milestone is a credible recommendation pipeline with a serious operator console built on top of it.
