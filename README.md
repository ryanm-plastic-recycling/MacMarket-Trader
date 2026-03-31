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
- static percentage exits like "take profit at 5%" without structure-based support
- UI-heavy work before engine credibility exists

## Current repository status

This repository is a **working scaffold**, not a finished trading product.

### Implemented now

- FastAPI service with:
  - `GET /health`
  - `POST /recommendations/generate`
  - `POST /replay/run`
- typed Pydantic contracts for bars, events, regimes, setups, recommendations, orders, fills, replay requests, and audit payloads
- deterministic mock event extractor
- deterministic mock market data provider
- deterministic regime engine
- deterministic setup engine
- deterministic risk engine
- in-memory OMS and paper broker adapter
- replay engine using the same recommendation pipeline as the API
- unit and API contract tests
- SQLite-ready SQLAlchemy models for recommendation and order persistence

### Not implemented yet

- real market/news/broker vendors
- point-in-time raw event store
- normalized feature store
- persistent audit trail wiring
- stateful portfolio ledger in replay/live paths
- sector/factor/correlation caps
- macro blackout windows
- calibration and historical analog scoring
- production-grade OMS controls
- operator dashboard / frontend
- auth, tenancy, billing, or any public SaaS features

## What the system must eventually produce

Every recommendation should move toward this structure:

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

The repository stays intentionally narrow until the engine is credible.

### In scope now

- Python backend only
- typed domain models
- deterministic engines
- mock and paper adapters
- unit tests and contract tests
- JSON API
- audit-first data model

### Out of scope now

- React dashboard
- admin portal
- account system
- Discord bot
- SMS/email notification UI
- crypto
- indicator showcase pages
- legacy strategy playgrounds
- public product polish before model credibility

## Repository layout

```text
macmarket-trader/
  README.md
  pyproject.toml
  .env.example
  src/macmarket_trader/
    api/
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
    storage/
  tests/
  docs/
  scripts/
  experimental/
```

## Quickstart

### Prerequisites

- Python 3.12 or newer
- `git`
- a Unix-like shell for the commands below, or equivalent PowerShell commands on Windows

### 1. Clone the repository

```bash
git clone <YOUR_REPO_URL>
cd MacMarket-Trader
```

### 2. Create and activate a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

### 4. Configure environment

```bash
cp .env.example .env
```

Adjust values in `.env` as needed.

### 5. Optional: initialize the local database

```bash
python -c "from macmarket_trader.storage.db import init_db; init_db()"
```

### 6. Run the test suite

```bash
pytest -q
```

### 7. Start the API server

```bash
uvicorn macmarket_trader.api.main:app --reload
```

### 8. Open the local API docs

- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

## Example API usage

### Health check

```bash
curl http://127.0.0.1:8000/health
```

### Generate a recommendation

```bash
curl -X POST http://127.0.0.1:8000/recommendations/generate \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "AAPL",
    "event_text": "Earnings beat with strong guidance",
    "bars": [
      {"date": "2026-01-01", "open": 100, "high": 101, "low": 99, "close": 100.5, "volume": 1000000, "rel_volume": 1.1},
      {"date": "2026-01-02", "open": 101, "high": 102, "low": 100, "close": 101.5, "volume": 1010000, "rel_volume": 1.1},
      {"date": "2026-01-03", "open": 102, "high": 103, "low": 101, "close": 102.5, "volume": 1020000, "rel_volume": 1.1},
      {"date": "2026-01-04", "open": 103, "high": 104, "low": 102, "close": 103.5, "volume": 1030000, "rel_volume": 1.1},
      {"date": "2026-01-05", "open": 104, "high": 105, "low": 103, "close": 104.5, "volume": 1040000, "rel_volume": 1.1},
      {"date": "2026-01-06", "open": 105, "high": 106, "low": 104, "close": 105.5, "volume": 1050000, "rel_volume": 1.1}
    ]
  }'
```

## Development standards

- strict typing
- deterministic core logic
- mockable provider interfaces
- replay/live parity
- UTC-aware timestamps
- test-first changes for engines and contracts
- no hidden LLM decisioning in order generation

## Immediate next milestone

The next milestone is **not** a dashboard.

The next milestone is to align the current scaffold to the target contract by adding:
- richer recommendation schema
- persistent audit storage
- stateful replay portfolio updates
- improved risk sizing that scales to notional constraints
- expanded OMS states and replay attribution
- CLI entry points for local research runs

## Legacy code policy

The old MacMarket repository is a **reference archive**, not a base layer.

By default, no old application code is carried into the new system.
Only isolated, testable, non-core research utilities may be imported later under `experimental/`.

## Current status

This repository is a ground-up rebuild.

The first milestone is not a dashboard.
The first milestone is a credible recommendation pipeline.
