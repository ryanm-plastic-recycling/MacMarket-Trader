# Architecture Overview

MacMarket-Trader is designed around deterministic research/live parity.

## Pipeline

1. **Ingestion + Extraction**
   - Input can be structured event JSON or raw event text.
   - LLM extractor (mock in v1 scaffold) classifies and structures event metadata.
2. **Regime Classification**
   - Uses deterministic daily-bar context (trend/volatility/participation proxies).
3. **Setup Construction**
   - Generates one of: event continuation, pullback continuation, failed event/fade.
   - Uses daily structure anchors: prior day high/low, 20-day high/low, ATR(14), event-day range.
4. **Risk + Sizing**
   - Position sizing: `floor(risk_dollars / stop_distance)`
   - Applies max portfolio heat and max position notional checks.
5. **Execution Intent + Paper OMS**
   - Produces deterministic order intent and records state transitions/fills.
6. **Audit + Replay**
   - Every recommendation has evidence and version markers.
   - Replay and API call the same setup/risk engines.

## Design constraints

- LLM never decides entry/stop/targets/sizing/order routing.
- No fixed-percentage exits; all exits derive from market structure context.
- Interfaces are provider-based for future real broker/data integrations.
