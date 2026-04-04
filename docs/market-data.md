# Market Data Setup (Polygon/Alpaca + deterministic fallback)

MacMarket-Trader v1 supports real market-data providers: **Polygon** (preferred) and **Alpaca** (alternate scaffold).

If Alpaca is not configured, disabled, or temporarily unavailable, the backend stays operational in explicit **deterministic fallback** mode.

## Backend `.env` variables (repo root)

```bash
POLYGON_ENABLED=true
POLYGON_API_KEY=...

# Optional Polygon tuning
POLYGON_BASE_URL=https://api.polygon.io
POLYGON_TIMEOUT_SECONDS=8

# Alternate provider scaffold
POLYGON_ENABLED=false
MARKET_DATA_PROVIDER=alpaca
MARKET_DATA_ENABLED=true
APCA_API_KEY_ID=...
APCA_API_SECRET_KEY=...

# Optional provider tuning
ALPACA_MARKET_DATA_BASE_URL=https://data.alpaca.markets
ALPACA_MARKET_DATA_FEED=iex        # iex | sip | delayed_sip
MARKET_DATA_REQUEST_TIMEOUT_SECONDS=8
MARKET_DATA_LATEST_CACHE_TTL_SECONDS=10
MARKET_DATA_HISTORICAL_CACHE_TTL_SECONDS=120
```

## Feed selection guidance (Alpaca)

- `iex` (default): dev-friendly and safest default for paper-first local workflows.
- `sip`: full SIP feed when entitlement is available.
- `delayed_sip`: delayed SIP data for environments without real-time SIP entitlement.

## Fallback behavior

Fallback mode is used when:
- `MARKET_DATA_ENABLED=false`, or
- `MARKET_DATA_PROVIDER` is not `alpaca`, or
- Alpaca credentials are missing, or
- Alpaca fetch/probe calls fail.

In fallback mode:
- HACO chart payloads still render with deterministic bars.
- Dashboard latest snapshot still resolves using deterministic market data.
- Provider-health shows:
  - configured provider (`polygon` or `alpaca`)
  - effective chart/snapshot read mode
  - workflow execution mode (`provider`, `demo_fallback`, or `blocked`)
  - failure reason when probe/dependency checks fail.

## Workflow execution truth

- Healthy provider probe: workflows run on provider-backed bars.
- Degraded provider probe + `WORKFLOW_DEMO_FALLBACK=false`: workflows are **blocked** (no silent fallback execution).
- Degraded provider probe + `WORKFLOW_DEMO_FALLBACK=true` in `dev/local/test`: workflows run on explicit deterministic demo fallback bars.

## UI indicators (live vs fallback)

Use these operator-console cues:
- **Dashboard provider summary**: shows workflow execution mode (`provider`, `demo_fallback`, or `blocked`) plus configured provider + effective read mode.
- **Dashboard alert log**: mirrors provider-health operational impact messaging for blocked-vs-demo-fallback states.
- **HACO workspace**: `Data source` and `(deterministic fallback active)` labeling make source mode explicit.
- **Provider health page**: market-data card includes configured provider, effective read mode, workflow execution mode, feed/configuration details, failure reason, and operational impact text.

## Operator-facing provider mode guidance

- Provider health page now summarizes configured-vs-effective-vs-workflow mode, latency, sample symbol, and last successful fetch.
- If provider requests are rejected (for example 403), UI explains whether workflows are blocked or running on explicit demo fallback based on `WORKFLOW_DEMO_FALLBACK`.

## Workflow source coherence for indicator workbench

Strategy Workbench, Recommendations, and HACO Context now expose operator-selected indicators on a shared canonical time axis. Workflow source badges must continue to show provider vs fallback mode explicitly on each page.
