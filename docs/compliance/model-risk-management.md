# Model Risk Management

MacMarket-Trader uses deterministic engines for trade setup, risk, ranking,
sizing, and paper lifecycle decisions. LLMs are explanation-only.

## Deterministic Engines

- Setup/risk/ranking engines produce structured recommendation fields.
- Market Risk Calendar owns warning/restriction/block state.
- Paper lifecycle code owns order, fill, position, trade, P&L, and reset state.
- Active Paper Position Review uses deterministic action classifications.

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

## Preliminary Evidence

- Unit/integration tests for recommendation contracts.
- Replay tests.
- Risk-calendar tests.
- Active Paper Position Review tests.
- Lifecycle integrity test.
- LLM validation and fallback tests.

## Remaining Gaps

- No independently reviewed historical validation pack.
- No formal model-change approval board.
- No recurring drift report.
- No production-grade model inventory.
