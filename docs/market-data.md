# Market Data Setup (Alpaca + deterministic fallback)

MacMarket-Trader v1 supports one real market-data provider: **Alpaca**.

If Alpaca is not configured, disabled, or temporarily unavailable, the backend stays operational in explicit **deterministic fallback** mode.

## Backend `.env` variables (repo root)

```bash
MARKET_DATA_PROVIDER=alpaca
MARKET_DATA_ENABLED=true

# Alpaca credentials (Trading API-style headers)
APCA_API_KEY_ID=...
APCA_API_SECRET_KEY=...

# Optional provider tuning
ALPACA_MARKET_DATA_BASE_URL=https://data.alpaca.markets
ALPACA_MARKET_DATA_FEED=iex        # iex | sip | delayed_sip
MARKET_DATA_REQUEST_TIMEOUT_SECONDS=8
MARKET_DATA_LATEST_CACHE_TTL_SECONDS=10
MARKET_DATA_HISTORICAL_CACHE_TTL_SECONDS=120
```

## Feed selection guidance

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
- Provider-health surfaces a warning and indicates fallback.

## UI indicators (live vs fallback)

Use these operator-console cues:
- **Dashboard top banner**: `Provider summary` is `ok` when Alpaca health probe succeeds, otherwise `degraded`.
- **Dashboard provider-health pane**: `Market data` shows `alpaca` when live, `fallback` when not.
- **HACO workspace**: `Data source` and `(deterministic fallback active)` labeling make source mode explicit.
- **Provider health page**: market-data card includes mode, feed, configured flag, sample symbol, latency, and last-success timestamp.

## Operator-facing provider mode guidance

- Provider health page now summarizes live vs fallback mode, latency, sample symbol, and last successful fetch.
- If provider requests are rejected (for example 403), UI explains that fallback mode is active and advises checking key/plan permissions.
